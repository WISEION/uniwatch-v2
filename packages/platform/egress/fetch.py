"""Validated HTTP fetch (docs/architecture/egress-validator-contract.md
§2 step 6, §3): redirects are followed manually, one hop at a time --
never delegated to an HTTP client's built-in `follow_redirects`, because
each hop is a brand new candidate URL that must pass the full validator
again from scratch (scheme -> registry -> resolve -> IP-range -> connect).

The actual TCP connection is pinned to the specific IP address the
validator just checked (`ValidatedTarget.resolved_ip`), not a fresh
hostname lookup performed later by the HTTP client -- this is what closes
the DNS-rebinding TOCTOU gap (P303). The original hostname is still used
for the `Host` header and TLS SNI/certificate verification, so this is
transparent to the server and to certificate validation."""

from __future__ import annotations

import asyncio
import http.client
import socket
import ssl
from collections.abc import Awaitable, Callable
from urllib.parse import urljoin

from sqlalchemy.ext.asyncio import AsyncConnection

from .validator import EgressRejected, EgressValidator, ValidatedTarget

REDIRECT_STATUSES = {301, 302, 303, 307, 308}
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_TIMEOUT_SECONDS = 15.0


class TooManyRedirects(Exception):
    pass


class _PinnedHTTPConnection(http.client.HTTPConnection):
    """Connects to `resolved_ip` while keeping `host` (used for the `Host`
    header) as the original hostname."""

    def __init__(self, resolved_ip: str, host: str, port: int, timeout: float):
        super().__init__(host, port, timeout=timeout)
        self._resolved_ip = resolved_ip

    def connect(self) -> None:
        self.sock = socket.create_connection((self._resolved_ip, self.port), self.timeout)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Same pinning, plus TLS with SNI/certificate verification against the
    original hostname (`self.host`), not the pinned IP."""

    def __init__(self, resolved_ip: str, host: str, port: int, timeout: float):
        super().__init__(host, port, timeout=timeout)
        self._resolved_ip = resolved_ip

    def connect(self) -> None:
        raw_sock = socket.create_connection((self._resolved_ip, self.port), self.timeout)
        context = ssl.create_default_context()
        self.sock = context.wrap_socket(raw_sock, server_hostname=self.host)


def _fetch_pinned_sync(
    *, resolved_ip: str, host: str, port: int, scheme: str, path_and_query: str, timeout: float
) -> tuple[int, bytes, dict[str, str]]:
    conn: http.client.HTTPConnection
    if scheme == "https":
        conn = _PinnedHTTPSConnection(resolved_ip, host, port, timeout)
    else:
        conn = _PinnedHTTPConnection(resolved_ip, host, port, timeout)
    try:
        conn.request(
            "GET",
            path_and_query,
            headers={"Accept": "application/json", "User-Agent": "uniwatch-v2-egress-validator/1"},
        )
        response = conn.getresponse()
        body = response.read()
        headers = {k.lower(): v for k, v in response.getheaders()}
        return response.status, body, headers
    finally:
        conn.close()


FetchFn = Callable[[ValidatedTarget], Awaitable[tuple[int, bytes, dict[str, str]]]]


async def default_do_fetch(
    target: ValidatedTarget, *, timeout: float = DEFAULT_TIMEOUT_SECONDS
) -> tuple[int, bytes, dict[str, str]]:
    return await asyncio.to_thread(
        _fetch_pinned_sync,
        resolved_ip=target.resolved_ip,
        host=target.host,
        port=target.port,
        scheme=target.scheme,
        path_and_query=target.path_and_query,
        timeout=timeout,
    )


async def fetch_via_validator(
    conn: AsyncConnection,
    validator: EgressValidator,
    url: str,
    *,
    do_fetch: FetchFn | None = None,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> tuple[int, bytes, dict[str, str]]:
    do_fetch = do_fetch or default_do_fetch
    current_url = url

    for _ in range(max_redirects + 1):
        target = await validator.validate(conn, current_url)
        status, body, headers = await do_fetch(target)

        if status not in REDIRECT_STATUSES:
            return status, body, headers

        location = headers.get("location")
        if not location:
            raise EgressRejected("redirect_target_rejected", f"{status} redirect with no Location header from {current_url!r}")
        # Re-validated from scratch on the next loop iteration -- a
        # redirect is never followed on trust of the previous hop's checks.
        current_url = urljoin(current_url, location)

    raise TooManyRedirects(f"exceeded {max_redirects} redirects starting from {url!r}")

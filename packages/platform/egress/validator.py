"""Central egress validator (NFR-SEC-01, NFR-SEC-02, INV-10, P006, P301-P304,
docs/architecture/egress-validator-contract.md §2). No outbound HTTP call
may bypass this: scheme check -> registry check -> DNS resolve (every
returned address, not just the first) -> IP-range check (loopback,
private, link-local/metadata, CGNAT, reserved, multicast, unspecified,
IPv4 and IPv6) -> the caller connects to the checked address, never a
fresh hostname lookup. Every rejection is a typed, logged reason -- never
a silent `None`."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

from sqlalchemy.ext.asyncio import AsyncConnection

from .registry import get_trusted_source

ALLOWED_SCHEMES = {"http", "https"}

# CGNAT (RFC 6598) and the NAT64 well-known prefix (RFC 6052) are not
# reliably flagged by ipaddress's is_private/is_reserved on every address
# in range -- checked explicitly, in addition to (not instead of) the
# built-in loopback/private/link-local/reserved/multicast/unspecified
# checks, which already correctly cover RFC 1918, IPv4-mapped IPv6
# (::ffff:a.b.c.d unwraps to the embedded IPv4 address automatically),
# the metadata range (169.254.0.0/16, via is_link_local), and ULA (fc00::/7).
_EXTRA_BLOCKED_NETWORKS = (
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("64:ff9b::/96"),
)


class EgressRejected(Exception):
    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class ValidatedTarget:
    host: str
    port: int
    scheme: str
    path_and_query: str
    resolved_ip: str


def is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    return any(ip in net for net in _EXTRA_BLOCKED_NETWORKS)


Resolver = Callable[[str], list[str]]


def default_resolver(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise EgressRejected("address_blocked", f"DNS resolution failed for {host!r}: {exc}") from exc
    seen: list[str] = []
    for info in infos:
        ip = str(info[4][0])
        if ip not in seen:
            seen.append(ip)
    return seen


class EgressValidator:
    def __init__(self, *, resolver: Resolver | None = None):
        self._resolver = resolver or default_resolver

    async def validate(self, conn: AsyncConnection, url: str) -> ValidatedTarget:
        parts = urlsplit(url)
        scheme = parts.scheme.lower()
        if scheme not in ALLOWED_SCHEMES:
            raise EgressRejected("scheme_not_allowed", f"{scheme!r} is not http/https ({url!r})")

        host = parts.hostname
        if not host:
            raise EgressRejected("host_not_registered", f"URL has no host: {url!r}")

        source = await get_trusted_source(conn, host)
        if source is None:
            raise EgressRejected("host_not_registered", host)
        if scheme not in source.allowed_schemes:
            raise EgressRejected("scheme_not_allowed", f"{scheme!r} not in allowed_schemes for {host}")

        port = parts.port or (443 if scheme == "https" else 80)

        addresses = self._resolver(host)
        if not addresses:
            raise EgressRejected("address_blocked", f"{host} did not resolve to any address")

        for addr in addresses:
            ip = ipaddress.ip_address(addr)
            if is_blocked_ip(ip):
                raise EgressRejected("address_blocked", f"{host} resolved to blocked address {addr}")

        # Pin the connection to the FIRST validated address -- this, not a
        # fresh hostname lookup, is what the caller connects to. Avoids the
        # DNS-rebinding TOCTOU gap (a low-TTL record safe at check-time and
        # private at connect-time) -- P303.
        resolved_ip = addresses[0]

        path_and_query = parts.path or "/"
        if parts.query:
            path_and_query += "?" + parts.query

        return ValidatedTarget(host=host, port=port, scheme=scheme, path_and_query=path_and_query, resolved_ip=resolved_ip)

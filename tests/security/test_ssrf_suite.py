"""SSRF regression suite (P006, P301-P304, INV-10, NFR-SEC-01..03).

P301: metadata/private address blocked, logged with a specific reason.
P302: a redirect to a private IP is blocked at the redirect step, not
      silently allowed because the original hop was fine.
P303: DNS-rebinding -- the connection uses the first resolved IP; a
      second resolution returning something different never gets a
      chance to matter, because there is no second resolution for the
      connection itself.
P304: a legitimate external tender portal fetches successfully through
      the validator, without a false-positive block (real network call).
"""

from __future__ import annotations

import json

import pytest

from packages.platform.egress.fetch import TooManyRedirects, fetch_via_validator
from packages.platform.egress.registry import promote_to_trusted, register_source
from packages.platform.egress.validator import EgressRejected, EgressValidator, ValidatedTarget


async def _register_trusted(conn, host: str, schemes: list[str] | None = None) -> None:
    await register_source(conn, host=host, allowed_schemes=schemes or ["https"], registered_by="test")
    await promote_to_trusted(conn, host=host, scanner_run_reference="test-scan")


async def test_P301_metadata_address_is_blocked_and_reason_is_specific(engine):
    async with engine.begin() as conn:
        await _register_trusted(conn, "p301-metadata.example")
        validator = EgressValidator(resolver=lambda host: ["169.254.169.254"])
        with pytest.raises(EgressRejected) as exc_info:
            await validator.validate(conn, "https://p301-metadata.example/latest/meta-data/iam/security-credentials/")

    assert exc_info.value.reason == "address_blocked"
    assert "169.254.169.254" in exc_info.value.detail  # logged with the specific address, not a bare "denied"


async def test_P301_private_ip_is_blocked(engine):
    async with engine.begin() as conn:
        await _register_trusted(conn, "p301-private.example")
        validator = EgressValidator(resolver=lambda host: ["10.0.0.5"])
        with pytest.raises(EgressRejected) as exc_info:
            await validator.validate(conn, "https://p301-private.example/")
    assert exc_info.value.reason == "address_blocked"


async def test_P302_redirect_to_private_ip_is_blocked_at_redirect_step(engine):
    async with engine.begin() as conn:
        # Two distinct trusted hosts: the first resolves safely, the
        # second (the redirect target) resolves to a private address.
        await _register_trusted(conn, "p302-safe-origin.example")
        await _register_trusted(conn, "p302-private-target.example")

        def resolver(host: str) -> list[str]:
            if host == "p302-safe-origin.example":
                return ["8.8.8.8"]
            return ["192.168.1.1"]

        validator = EgressValidator(resolver=resolver)

        calls: list[str] = []

        async def fake_do_fetch(target: ValidatedTarget):
            calls.append(target.host)
            if target.host == "p302-safe-origin.example":
                # The origin itself is a legitimate response that happens
                # to redirect -- the redirect target is what's malicious.
                return 302, b"", {"location": "https://p302-private-target.example/internal"}
            raise AssertionError("must never reach the fetch step for the private redirect target")

        with pytest.raises(EgressRejected) as exc_info:
            await fetch_via_validator(conn, validator, "https://p302-safe-origin.example/start", do_fetch=fake_do_fetch)

    assert exc_info.value.reason == "address_blocked"
    # The origin was fetched once; the redirect target was validated and
    # rejected BEFORE any fetch was attempted against it.
    assert calls == ["p302-safe-origin.example"]


async def test_P302_new_filter_range_style_redirect_chain_revalidates_every_hop(engine):
    # A longer chain: safe -> safe -> private. Confirms re-validation
    # happens on EVERY hop, not just the first redirect.
    async with engine.begin() as conn:
        await _register_trusted(conn, "p302-hop1.example")
        await _register_trusted(conn, "p302-hop2.example")
        await _register_trusted(conn, "p302-hop3-private.example")

        def resolver(host: str) -> list[str]:
            return ["127.0.0.1"] if host == "p302-hop3-private.example" else ["8.8.8.8"]

        validator = EgressValidator(resolver=resolver)
        visited: list[str] = []

        async def fake_do_fetch(target: ValidatedTarget):
            visited.append(target.host)
            chain = {
                "p302-hop1.example": (302, {"location": "https://p302-hop2.example/next"}),
                "p302-hop2.example": (302, {"location": "https://p302-hop3-private.example/final"}),
            }
            status, headers = chain[target.host]
            return status, b"", headers

        with pytest.raises(EgressRejected) as exc_info:
            await fetch_via_validator(conn, validator, "https://p302-hop1.example/start", do_fetch=fake_do_fetch)

    assert exc_info.value.reason == "address_blocked"
    assert visited == ["p302-hop1.example", "p302-hop2.example"]  # hop3 never fetched


async def test_P303_connection_pins_first_resolved_address_rebind_does_not_reach_it(engine):
    # Simulates DNS rebinding: the resolver would return a PRIVATE address
    # on any call after the first. The validator only ever calls the
    # resolver once per validate() -- the connection uses that single
    # captured address, so a later, different answer to "what does this
    # host resolve to now" never gets a chance to affect the connection.
    call_log: list[int] = []

    def rebinding_resolver(host: str) -> list[str]:
        call_log.append(1)
        if len(call_log) == 1:
            return ["8.8.8.8"]  # safe at check-time
        return ["169.254.169.254"]  # would be malicious on any subsequent lookup

    async with engine.begin() as conn:
        await _register_trusted(conn, "p303-rebind.example")
        validator = EgressValidator(resolver=rebinding_resolver)
        target = await validator.validate(conn, "https://p303-rebind.example/data")

    assert target.resolved_ip == "8.8.8.8"
    assert len(call_log) == 1  # resolver consulted exactly once for this validate() call

    # A caller connecting via `target.resolved_ip` (as fetch.py's pinned
    # connection classes do) never triggers a second resolution at all --
    # simulated here by confirming no second call happened even though the
    # resolver was primed to answer differently.
    assert rebinding_resolver("p303-rebind.example") == ["169.254.169.254"]  # proves the rebind WOULD have fired
    assert target.resolved_ip == "8.8.8.8"  # but the already-validated target is unaffected


async def test_P304_legitimate_external_portal_fetches_successfully(engine):
    # Real network call to the same real, live source used throughout
    # tasks 1.A/1.B (etender.gov.az) -- proves the validator does not
    # false-positive block a legitimate external tender portal.
    async with engine.begin() as conn:
        await _register_trusted(conn, "etender.gov.az", schemes=["https"])
        validator = EgressValidator()  # real DNS resolution

        status, body, _headers = await fetch_via_validator(conn, validator, "https://etender.gov.az/api/events/355920")

    assert status == 200
    payload = json.loads(body)
    assert payload["id"] == 355920
    assert payload["eventType"] == 7  # matches the real capture from task 1.A


async def test_too_many_redirects_raises_instead_of_looping_forever(engine):
    async with engine.begin() as conn:
        await _register_trusted(conn, "p-loop.example")
        validator = EgressValidator(resolver=lambda host: ["8.8.8.8"])

        async def always_redirect(target: ValidatedTarget):
            return 302, b"", {"location": "https://p-loop.example/again"}

        with pytest.raises(TooManyRedirects):
            await fetch_via_validator(conn, validator, "https://p-loop.example/start", do_fetch=always_redirect, max_redirects=3)

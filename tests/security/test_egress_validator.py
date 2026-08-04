"""NFR-SEC-01, NFR-SEC-02, INV-10, P006, P301: the validator's decision
logic end to end (registry + injected resolver, real DB, no real network)."""

from __future__ import annotations

import pytest

from packages.platform.egress.registry import promote_to_trusted, register_source
from packages.platform.egress.validator import EgressRejected, EgressValidator


async def _register_trusted(conn, host: str, schemes: list[str] | None = None) -> None:
    await register_source(conn, host=host, allowed_schemes=schemes or ["https"], registered_by="test")
    await promote_to_trusted(conn, host=host, scanner_run_reference="test-scan")


async def test_rejects_disallowed_scheme(engine):
    async with engine.begin() as conn:
        await _register_trusted(conn, "scheme-test.example")
        validator = EgressValidator(resolver=lambda host: ["8.8.8.8"])
        with pytest.raises(EgressRejected) as exc_info:
            await validator.validate(conn, "ftp://scheme-test.example/x")
    assert exc_info.value.reason == "scheme_not_allowed"


async def test_rejects_unregistered_host(engine):
    async with engine.begin() as conn:
        validator = EgressValidator(resolver=lambda host: ["8.8.8.8"])
        with pytest.raises(EgressRejected) as exc_info:
            await validator.validate(conn, "https://never-registered.example/x")
    assert exc_info.value.reason == "host_not_registered"


async def test_rejects_scheme_not_in_hosts_allowed_schemes(engine):
    async with engine.begin() as conn:
        await _register_trusted(conn, "https-only.example", schemes=["https"])
        validator = EgressValidator(resolver=lambda host: ["8.8.8.8"])
        with pytest.raises(EgressRejected) as exc_info:
            await validator.validate(conn, "http://https-only.example/x")
    assert exc_info.value.reason == "scheme_not_allowed"


async def test_rejects_when_resolved_address_is_private(engine):
    # P301: a registered, trusted host that resolves to a private/metadata
    # address is still blocked -- registration trusts the HOST, not
    # whatever address it happens to resolve to right now.
    async with engine.begin() as conn:
        await _register_trusted(conn, "rebinds-to-metadata.example")
        validator = EgressValidator(resolver=lambda host: ["169.254.169.254"])
        with pytest.raises(EgressRejected) as exc_info:
            await validator.validate(conn, "https://rebinds-to-metadata.example/latest/meta-data/")
    assert exc_info.value.reason == "address_blocked"


async def test_rejects_when_any_resolved_address_is_blocked(engine):
    # Multiple A/AAAA records: even one blocked address in the set fails
    # the whole check, not just "the first one checked".
    async with engine.begin() as conn:
        await _register_trusted(conn, "multi-address.example")
        validator = EgressValidator(resolver=lambda host: ["8.8.8.8", "127.0.0.1"])
        with pytest.raises(EgressRejected) as exc_info:
            await validator.validate(conn, "https://multi-address.example/")
    assert exc_info.value.reason == "address_blocked"


async def test_accepts_and_pins_first_resolved_address_for_public_host(engine):
    async with engine.begin() as conn:
        await _register_trusted(conn, "public-host.example")
        validator = EgressValidator(resolver=lambda host: ["8.8.8.8", "1.1.1.1"])
        target = await validator.validate(conn, "https://public-host.example/api/events?x=1")

    assert target.host == "public-host.example"
    assert target.resolved_ip == "8.8.8.8"
    assert target.port == 443
    assert target.path_and_query == "/api/events?x=1"


async def test_dns_resolution_failure_is_rejected_not_silently_swallowed(engine):
    async with engine.begin() as conn:
        await _register_trusted(conn, "unresolvable.example")

        def failing_resolver(host):
            return []

        validator = EgressValidator(resolver=failing_resolver)
        with pytest.raises(EgressRejected) as exc_info:
            await validator.validate(conn, "https://unresolvable.example/")
    assert exc_info.value.reason == "address_blocked"

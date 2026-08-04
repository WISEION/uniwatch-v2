"""NFR-SEC-03: a host is never trusted on creation; only an explicit
promotion (representing a real scanner run) makes it usable, and revocation
is append-only, not a delete."""

from __future__ import annotations

from packages.platform.egress.registry import (
    get_trusted_source,
    promote_to_trusted,
    register_source,
    revoke_source,
)


async def test_newly_registered_source_is_not_trusted_yet(engine):
    async with engine.begin() as conn:
        await register_source(conn, host="example-tender-portal.test", allowed_schemes=["https"], registered_by="owner")
        found = await get_trusted_source(conn, "example-tender-portal.test")
    assert found is None  # pending_scan is not trusted


async def test_promoted_source_is_trusted(engine):
    async with engine.begin() as conn:
        await register_source(conn, host="example-tender-portal2.test", allowed_schemes=["https"], registered_by="owner")
        await promote_to_trusted(conn, host="example-tender-portal2.test", scanner_run_reference="scan-run-1")
        found = await get_trusted_source(conn, "example-tender-portal2.test")
    assert found is not None
    assert found.status == "trusted"
    assert found.allowed_schemes == ("https",)


async def test_revoked_source_is_not_trusted_and_row_survives(engine):
    async with engine.begin() as conn:
        await register_source(conn, host="example-tender-portal3.test", allowed_schemes=["https"], registered_by="owner")
        await promote_to_trusted(conn, host="example-tender-portal3.test", scanner_run_reference="scan-run-2")
        revoked = await revoke_source(conn, host="example-tender-portal3.test", reason="rotated to a new domain")
        found = await get_trusted_source(conn, "example-tender-portal3.test")

    assert found is None  # revoked is not trusted
    assert revoked.status == "revoked"
    assert revoked.revoked_reason == "rotated to a new domain"


async def test_unregistered_host_is_not_trusted(engine):
    async with engine.begin() as conn:
        found = await get_trusted_source(conn, "never-registered.test")
    assert found is None

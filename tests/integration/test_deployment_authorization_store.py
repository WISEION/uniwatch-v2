"""Integration test over a real DB: deployment_authorizations is append-only
evidence (Phase 6, task 6.B, Gate 4 -- FR-AUT-06/INV-14)."""

from __future__ import annotations

from packages.platform.deployment_authorization import (
    get_authorization,
    latest_authorization_for_commit,
    record_authorization,
)


async def test_record_and_read_back_an_authorization(engine):
    async with engine.begin() as conn:
        authorization_id = await record_authorization(
            conn,
            commit_sha="abc123",
            image_digests={"api_tender": "sha256:deadbeef"},
            initiator="accessunico",
            approver="WISEION",
            db_schema_version_at_authorization=22,
            notes="test authorization",
        )

    async with engine.connect() as conn:
        row = await get_authorization(conn, authorization_id)

    assert row is not None
    assert row["commit_sha"] == "abc123"
    assert row["image_digests"] == {"api_tender": "sha256:deadbeef"}
    assert row["initiator"] == "accessunico"
    assert row["approver"] == "WISEION"
    assert row["db_schema_version_at_authorization"] == 22
    assert row["notes"] == "test authorization"


async def test_latest_authorization_for_commit_returns_the_most_recent_one(engine):
    async with engine.begin() as conn:
        await record_authorization(
            conn,
            commit_sha="same-commit",
            image_digests={},
            initiator="alice",
            approver="bob",
            db_schema_version_at_authorization=22,
        )
        second_id = await record_authorization(
            conn,
            commit_sha="same-commit",
            image_digests={},
            initiator="alice",
            approver="carol",
            db_schema_version_at_authorization=22,
        )

    async with engine.connect() as conn:
        latest = await latest_authorization_for_commit(conn, "same-commit")

    assert latest is not None
    assert latest["id"] == second_id
    assert latest["approver"] == "carol"


async def test_latest_authorization_for_commit_returns_none_when_unauthorized(engine):
    async with engine.connect() as conn:
        result = await latest_authorization_for_commit(conn, "never-authorized-commit")
    assert result is None

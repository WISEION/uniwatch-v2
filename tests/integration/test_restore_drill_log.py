"""Restore-drill evidence log (Phase 6, task 6.C, NFR-REL-01)."""

from __future__ import annotations

from packages.platform.restore_drill import latest_passing_drill, record_restore_drill


async def test_latest_passing_drill_returns_none_when_no_drill_recorded(engine):
    async with engine.connect() as conn:
        result = await latest_passing_drill(conn)
    assert result is None


async def test_record_and_read_back_a_passing_drill(engine):
    async with engine.begin() as conn:
        drill_id = await record_restore_drill(
            conn,
            backup_filename="backup_20260817T000000Z.dump",
            target_database="uniwatch_drill",
            passed=True,
            detail="restored cleanly",
        )

    async with engine.connect() as conn:
        latest = await latest_passing_drill(conn)

    assert latest is not None
    assert latest["id"] == drill_id
    assert latest["backup_filename"] == "backup_20260817T000000Z.dump"
    assert latest["target_database"] == "uniwatch_drill"
    assert latest["passed"] is True
    assert latest["detail"] == "restored cleanly"


async def test_latest_passing_drill_ignores_failed_drills(engine):
    async with engine.begin() as conn:
        await record_restore_drill(
            conn,
            backup_filename="backup_20260817T010000Z.dump",
            target_database="uniwatch_drill",
            passed=False,
            detail="pg_restore exited 1",
        )

    async with engine.connect() as conn:
        result = await latest_passing_drill(conn)
    assert result is None


async def test_latest_passing_drill_returns_the_most_recent_pass(engine):
    async with engine.begin() as conn:
        await record_restore_drill(
            conn,
            backup_filename="backup_20260817T020000Z.dump",
            target_database="uniwatch_drill",
            passed=True,
            detail="first pass",
        )
        second_id = await record_restore_drill(
            conn,
            backup_filename="backup_20260817T030000Z.dump",
            target_database="uniwatch_drill",
            passed=True,
            detail="second pass",
        )

    async with engine.connect() as conn:
        latest = await latest_passing_drill(conn)

    assert latest is not None
    assert latest["id"] == second_id
    assert latest["detail"] == "second pass"

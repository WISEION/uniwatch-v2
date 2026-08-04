"""FR-TND-*, P308: boq_lines table exists with the expected shape and
uniqueness guard (one row per real source line id, never a silent
duplicate on reprocessing)."""

from __future__ import annotations

from sqlalchemy import text


async def test_boq_lines_table_has_expected_columns(engine):
    async with engine.begin() as conn:
        columns = (
            (
                await conn.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_name = 'boq_lines' ORDER BY column_name")
                )
            )
            .scalars()
            .all()
        )
    expected = {
        "id",
        "source",
        "event_id",
        "page_number",
        "tender_version_id",
        "raw_snapshot_id",
        "source_line_id",
        "section",
        "category_code",
        "description",
        "unit_raw",
        "unit_canonical",
        "unit_status",
        "qty",
        "line_type",
        "spec_requirements",
        "rate",
        "amount",
        "created_at",
    }
    assert expected.issubset(set(columns))


async def test_boq_lines_rejects_duplicate_source_line_id_for_same_event(engine):
    async with engine.begin() as conn:
        tender_id = (
            await conn.execute(text("INSERT INTO tenders (source, identity_key) VALUES ('etender', 'x') RETURNING id"))
        ).scalar_one()
        version_id = (
            await conn.execute(
                text(
                    "INSERT INTO tender_versions (tender_id, version_number, raw_snapshot_id, parser_version, normalized_fields) "
                    "VALUES (:tid, 1, :rsid, 'etender-v1', '{}'::jsonb) RETURNING id"
                ),
                {"tid": tender_id, "rsid": await _insert_raw_snapshot(conn)},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO boq_lines (source, event_id, page_number, tender_version_id, raw_snapshot_id, "
                "source_line_id, description, unit_raw, unit_status, qty) "
                "VALUES ('etender', 1, 1, :vid, :vid, 999, 'a line', 'ədəd', 'mapped', 1)"
            ),
            {"vid": version_id},
        )
        raised = False
        try:
            await conn.execute(
                text(
                    "INSERT INTO boq_lines (source, event_id, page_number, tender_version_id, raw_snapshot_id, "
                    "source_line_id, description, unit_raw, unit_status, qty) "
                    "VALUES ('etender', 1, 1, :vid, :vid, 999, 'a duplicate line', 'ədəd', 'mapped', 1)"
                ),
                {"vid": version_id},
            )
        except Exception:
            raised = True
        assert raised is True


async def _insert_raw_snapshot(conn) -> int:
    return (
        await conn.execute(
            text(
                "INSERT INTO raw_snapshots (source, resource_type, identity_key, checksum, "
                "body, contract_version, correlation_id) "
                "VALUES ('etender', 'etender.bom_lines_page', 'k', 'c', '{}'::jsonb, 'v', 'corr') RETURNING id"
            )
        )
    ).scalar_one()

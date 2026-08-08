"""FR-TND-*, P308: atomic BOQ lines persisted with unit/type/spec metadata,
traceable back to the exact raw snapshot and normalized version they came
from (same traceability discipline as tender_versions -> raw_snapshots)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

from packages.tender.boq_line_model import BoqLine, build_boq_lines
from packages.tender.boq_lines_store import list_boq_lines_by_tender_version, store_boq_lines
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


async def _setup_version(conn, *, correlation_id: str) -> tuple[int, int]:
    raw_body = (FIXTURES / "event_355920_bomlines_page1.raw.json").read_bytes()
    snapshot_id = await save_raw_snapshot(
        conn,
        source="etender",
        resource_type="etender.bom_lines_page",
        identity_key="etender.bom_lines_page|event_id=355920&PageNumber=1",
        raw_body=raw_body,
        contract_version="etender.bom_lines_page",
        correlation_id=correlation_id,
    )
    tender_id = await get_or_create_tender(conn, source="etender", identity_key=f"boq-lines-test|{correlation_id}")
    version = await create_normalized_version(
        conn,
        tender_id=tender_id,
        raw_snapshot_id=snapshot_id,
        parser_version="etender-v1",
        normalized_fields={},
    )
    return version.id, snapshot_id


async def test_stores_all_lines_from_real_page_1(engine):
    raw_body = (FIXTURES / "event_355920_bomlines_page1.raw.json").read_bytes()
    payload = json.loads(raw_body)
    lines = build_boq_lines(page_number=1, items=payload["items"])

    async with engine.begin() as conn:
        version_id, snapshot_id = await _setup_version(conn, correlation_id="corr-store-1")
        inserted = await store_boq_lines(
            conn,
            source="etender",
            event_id=355920,
            tender_version_id=version_id,
            raw_snapshot_id=snapshot_id,
            lines=lines,
        )

    assert inserted == 100

    async with engine.begin() as conn:
        row = (
            (
                await conn.execute(
                    text(
                        "SELECT description, unit_raw, unit_canonical, unit_status, qty, line_type, category_code "
                        "FROM boq_lines WHERE source_line_id = 5131448 AND event_id = 355920"
                    )
                )
            )
            .mappings()
            .one()
        )
    assert row["unit_raw"] == "ədəd"
    assert row["unit_canonical"] == "pcs"
    assert row["unit_status"] == "mapped"
    assert row["qty"] == Decimal("1")
    assert row["line_type"] == "normal"
    assert row["category_code"] == "72121403"


async def test_stored_lines_trace_back_to_their_raw_snapshot_and_version(engine):
    raw_body = (FIXTURES / "event_355920_bomlines_page1.raw.json").read_bytes()
    payload = json.loads(raw_body)
    lines = build_boq_lines(page_number=1, items=payload["items"])[:1]

    async with engine.begin() as conn:
        version_id, snapshot_id = await _setup_version(conn, correlation_id="corr-store-2")
        await store_boq_lines(
            conn,
            source="etender",
            event_id=355920,
            tender_version_id=version_id,
            raw_snapshot_id=snapshot_id,
            lines=lines,
        )

    async with engine.begin() as conn:
        row = (
            (await conn.execute(text("SELECT tender_version_id, raw_snapshot_id FROM boq_lines WHERE event_id = 355920")))
            .mappings()
            .one()
        )
    assert row["tender_version_id"] == version_id
    assert row["raw_snapshot_id"] == snapshot_id


async def test_list_boq_lines_by_tender_version_returns_stored_lines(engine):
    line = BoqLine(
        source_line_id=501,
        page_number=1,
        section="Section A",
        category_code=None,
        description="rebar-12mm reinforcement steel",
        unit_raw="t",
        unit_canonical="t",
        unit_status="mapped",
        qty=Decimal("10"),
        line_type="normal",
        spec_requirements=(),
        rate=Decimal("850"),
        amount=Decimal("8500"),
    )

    async with engine.begin() as conn:
        raw_snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="event_details",
            identity_key="test-event-4a",
            raw_body=b'{"eventId": 999001}',
            contract_version="v1",
            correlation_id="test-4a",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-event-4a")
        version = await create_normalized_version(
            conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={}
        )
        await store_boq_lines(
            conn,
            source="etender",
            event_id=999001,
            tender_version_id=version.id,
            raw_snapshot_id=raw_snapshot_id,
            lines=[line],
        )
        result = await list_boq_lines_by_tender_version(conn, tender_version_id=version.id)

    assert len(result) == 1
    assert result[0].source_line_id == 501
    assert result[0].description == "rebar-12mm reinforcement steel"
    assert result[0].qty == Decimal("10")
    assert result[0].amount == Decimal("8500")

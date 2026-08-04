"""FR-TND-10, INT-02: an item-level shape change (not just a page-level
one) must still block normalization while keeping the already-saved raw
evidence -- same contract as
test_etender_connector.py::test_schema_drift_blocks_normalization_but_still_saves_raw_evidence,
but for a drift inside `items` rather than at the page's top level."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from packages.tender.etender_connector import SchemaDriftDetected, ingest_bom_lines_page

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


def _load(name: str) -> tuple[bytes, dict]:
    raw_body = (FIXTURES / name).read_bytes()
    return raw_body, json.loads(raw_body)


async def test_real_page_1_has_no_item_level_drift(engine):
    raw_body, payload = _load("event_355920_bomlines_page1.raw.json")
    async with engine.begin() as conn:
        version = await ingest_bom_lines_page(
            conn,
            event_id=355920,
            raw_body=raw_body,
            payload=payload,
            correlation_id="corr-item-drift-1",
        )
    assert version.normalized_fields["event_id"] == 355920


async def test_item_level_type_change_raises_and_still_saves_raw_evidence(engine):
    raw_body, payload = _load("event_355920_bomlines_page1.raw.json")
    drifted_payload = {
        **payload,
        "items": [{**payload["items"][0], "quantity": str(payload["items"][0]["quantity"])}, *payload["items"][1:]],
    }

    async with engine.begin() as conn:
        try:
            await ingest_bom_lines_page(
                conn,
                event_id=355920,
                raw_body=raw_body,
                payload=drifted_payload,
                correlation_id="corr-item-drift-2",
            )
            raised = False
        except SchemaDriftDetected as exc:
            raised = True
            assert exc.contract_name == "etender.bom_lines_page.item"

    assert raised is True

    async with engine.begin() as conn:
        snapshot_count = (
            (await conn.execute(text("SELECT count(*) AS n FROM raw_snapshots WHERE correlation_id = 'corr-item-drift-2'")))
            .mappings()
            .one()["n"]
        )
        assert snapshot_count == 1  # raw evidence saved even though normalization was blocked

        drift_events = (
            (await conn.execute(text("SELECT payload FROM outbox WHERE event_type = 'schema_drift_event'"))).mappings().all()
        )
        assert any(e["payload"]["contract"] == "etender.bom_lines_page.item" for e in drift_events)

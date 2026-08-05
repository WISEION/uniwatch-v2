"""World Bank Projects API donor-pipeline ingestion (INT-01, INT-02,
FR-TND-10, TENDER_INTELLIGENCE_SPEC.md §5.2, P309). Raw evidence is captured
unconditionally, before the drift check -- the shared discipline in
evidence_gate.py. Unlike etender_connector.py, a successful
ingest here produces *N* signal rows (one per project in the page), not
one normalized version, because a signal is an independent fact per
project, not a single versioned entity."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.egress.json_fetch import fetch_json
from packages.platform.egress.validator import EgressValidator

from .evidence_gate import capture_and_gate
from .signal_model import build_donor_pipeline_signal
from .signals_store import build_and_store_signals
from .worldbank_contract import DONOR_PIPELINE_PAGE_CONTRACT, DONOR_PIPELINE_PROJECT_CONTRACT


async def ingest_donor_pipeline_page(
    conn: AsyncConnection,
    *,
    raw_body: bytes,
    payload: dict[str, Any],
    os_: int,
    correlation_id: str,
    observed_at: str,
) -> list[int]:
    snapshot_id, _identity_key = await capture_and_gate(
        conn,
        source="worldbank_projects_api",
        contract=DONOR_PIPELINE_PAGE_CONTRACT,
        identity_params={"countrycode_exact": "AZ", "os": str(os_)},
        raw_body=raw_body,
        payload=payload,
        correlation_id=correlation_id,
        outbox_aggregate_type="signal_source_contract",
        item_contract=DONOR_PIPELINE_PROJECT_CONTRACT,
        items_extractor=lambda p: list(p["projects"].values()),
    )

    return await build_and_store_signals(
        conn,
        list(payload["projects"].values()),
        build_donor_pipeline_signal,
        raw_snapshot_id=snapshot_id,
        observed_at=observed_at,
        correlation_id=correlation_id,
    )


async def fetch_donor_pipeline_page_live(
    conn: AsyncConnection,
    validator: EgressValidator,
    *,
    countrycode_exact: str,
    rows: int,
    os_: int,
) -> tuple[bytes, dict[str, Any]]:
    url = f"https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact={countrycode_exact}&rows={rows}&os={os_}"
    return await fetch_json(conn, validator, url, source_label="World Bank Projects API")

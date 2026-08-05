"""World Bank Projects API donor-pipeline ingestion (INT-01, INT-02,
FR-TND-10, TENDER_INTELLIGENCE_SPEC.md §5.2, P309). Raw evidence is captured
unconditionally, before the drift check -- same discipline as
etender_connector.py's `_ingest`. Unlike that connector, a successful
ingest here produces *N* signal rows (one per project in the page), not
one normalized version, because a signal is an independent fact per
project, not a single versioned entity."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform import outbox
from packages.platform.egress.fetch import fetch_via_validator
from packages.platform.egress.validator import EgressValidator

from .raw_snapshot import save_raw_snapshot
from .schema_drift import SchemaDriftDetected, detect_schema_drift, detect_schema_drift_over_items
from .signal_model import build_donor_pipeline_signal
from .signals_store import store_signal
from .source_contract import canonical_identity
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
    identity_key = canonical_identity(DONOR_PIPELINE_PAGE_CONTRACT, {"countrycode_exact": "AZ", "os": str(os_)})

    snapshot_id = await save_raw_snapshot(
        conn,
        source="worldbank_projects_api",
        resource_type=DONOR_PIPELINE_PAGE_CONTRACT.name,
        identity_key=identity_key,
        raw_body=raw_body,
        contract_version=DONOR_PIPELINE_PAGE_CONTRACT.name,
        correlation_id=correlation_id,
    )

    projects = list(payload["projects"].values())
    drift = detect_schema_drift(DONOR_PIPELINE_PAGE_CONTRACT, payload)
    drifted_contract_name = DONOR_PIPELINE_PAGE_CONTRACT.name
    if not drift.has_drift:
        drift = detect_schema_drift_over_items(DONOR_PIPELINE_PROJECT_CONTRACT, projects)
        drifted_contract_name = DONOR_PIPELINE_PROJECT_CONTRACT.name

    if drift.has_drift:
        await outbox.enqueue(
            conn,
            aggregate_type="signal_source_contract",
            aggregate_id=drifted_contract_name,
            event_type="schema_drift_event",
            payload={
                "contract": drifted_contract_name,
                "identity_key": identity_key,
                "added_fields": list(drift.added_fields),
                "removed_fields": list(drift.removed_fields),
                "type_changed_fields": list(drift.type_changed_fields),
            },
            correlation_id=correlation_id,
        )
        raise SchemaDriftDetected(drift, contract_name=drifted_contract_name, raw_snapshot_id=snapshot_id)

    signal_ids = []
    for project in projects:
        signal = build_donor_pipeline_signal(
            project, raw_snapshot_id=snapshot_id, observed_at=observed_at, correlation_id=correlation_id
        )
        signal_ids.append(await store_signal(conn, signal))
    return signal_ids


class UnexpectedResponseStatus(Exception):
    pass


async def fetch_donor_pipeline_page_live(
    conn: AsyncConnection,
    validator: EgressValidator,
    *,
    countrycode_exact: str,
    rows: int,
    os_: int,
) -> tuple[bytes, dict[str, Any]]:
    url = f"https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact={countrycode_exact}&rows={rows}&os={os_}"
    status, body, _headers = await fetch_via_validator(conn, validator, url)
    if status != 200:
        raise UnexpectedResponseStatus(f"World Bank Projects API returned HTTP {status} for {url!r}")
    return body, json.loads(body)

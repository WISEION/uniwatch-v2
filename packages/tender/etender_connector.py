"""eTender empirical-contract ingestion (INT-01, INT-02, FR-TND-10). Raw
evidence is captured unconditionally, before the drift check — evidence
capture must never depend on whether the connector currently understands
the shape it received. Only a drift-free response is normalized; a
drifted one is reported via the existing transactional outbox
(schema_drift_event) and raises, so nothing gets silently mapped against
a contract it no longer matches.

`_ingest` is the shared mechanism; `ingest_event_details`,
`ingest_bom_lines_page`, and `ingest_events_list_page` are thin,
resource-specific wrappers around it — one per contract this task has a
real captured fixture for. None of them do resumable pagination or BOQ
completeness reconciliation (task 1.B); each call here ingests exactly
one already-fetched page/response."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform import outbox
from packages.platform.egress.fetch import fetch_via_validator
from packages.platform.egress.validator import EgressValidator

from .design_tender_signal import build_design_tender_signal, classify_design_tender
from .etender_contract import (
    APP_ITEM_CONTRACT,
    APP_LIST_PAGE_CONTRACT,
    BOM_LINE_ITEM_CONTRACT,
    BOM_LINES_PAGE_CONTRACT,
    EVENT_DETAILS_CONTRACT,
    EVENTS_LIST_PAGE_CONTRACT,
)
from .normalized import TenderVersion, create_normalized_version, get_or_create_tender
from .procurement_plan_signal import build_procurement_plan_signal
from .raw_snapshot import save_raw_snapshot
from .schema_drift import SchemaDriftDetected, detect_schema_drift, detect_schema_drift_over_items
from .signals_store import store_signal
from .source_contract import SourceContract, canonical_identity

PARSER_VERSION = "etender-v1"


async def _ingest(
    conn: AsyncConnection,
    *,
    contract: SourceContract,
    identity_params: dict[str, Any],
    raw_body: bytes,
    payload: dict[str, Any],
    normalize_fields: Callable[[dict[str, Any]], dict[str, Any]],
    correlation_id: str,
    item_contract: SourceContract | None = None,
    items_extractor: Callable[[dict[str, Any]], list[dict[str, Any]]] | None = None,
) -> TenderVersion:
    identity_key = canonical_identity(contract, identity_params)

    snapshot_id = await save_raw_snapshot(
        conn,
        source="etender",
        resource_type=contract.name,
        identity_key=identity_key,
        raw_body=raw_body,
        contract_version=contract.name,
        correlation_id=correlation_id,
    )

    drift = detect_schema_drift(contract, payload)
    if not drift.has_drift and item_contract is not None and items_extractor is not None:
        drift = detect_schema_drift_over_items(item_contract, items_extractor(payload))
        drifted_contract_name = item_contract.name
    else:
        drifted_contract_name = contract.name

    if drift.has_drift:
        await outbox.enqueue(
            conn,
            aggregate_type="tender_source_contract",
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

    tender_id = await get_or_create_tender(conn, source="etender", identity_key=identity_key)

    return await create_normalized_version(
        conn,
        tender_id=tender_id,
        raw_snapshot_id=snapshot_id,
        parser_version=PARSER_VERSION,
        normalized_fields=normalize_fields(payload),
    )


async def ingest_event_details(
    conn: AsyncConnection,
    *,
    raw_body: bytes,
    payload: dict[str, Any],
    correlation_id: str,
) -> TenderVersion:
    def normalize_fields(p: dict[str, Any]) -> dict[str, Any]:
        return {
            "tender_name": p["tenderName"],
            "organization_name": p["organizationName"],
            "organization_voen": p.get("organizationVoen"),
            # FR-TND-10 / INT-01: the actual returned value decides — this
            # connector never receives or trusts a requested EventType
            # filter value, only the eventType field the source actually
            # returned.
            "event_type_actual": p["eventType"],
            "estimated_amount": p.get("estimatedAmount"),
            "document_number": p["documentNumber"],
        }

    return await _ingest(
        conn,
        contract=EVENT_DETAILS_CONTRACT,
        identity_params={"id": payload["id"]},
        raw_body=raw_body,
        payload=payload,
        normalize_fields=normalize_fields,
        correlation_id=correlation_id,
    )


async def ingest_bom_lines_page(
    conn: AsyncConnection,
    *,
    event_id: int,
    raw_body: bytes,
    payload: dict[str, Any],
    correlation_id: str,
) -> TenderVersion:
    def normalize_fields(p: dict[str, Any]) -> dict[str, Any]:
        return {
            "event_id": event_id,
            "current_page": p["currentPage"],
            "total_pages": p["totalPages"],
            "total_items": p["totalItems"],
            "items_in_page": p["itemsInPage"],
            # Full page/row reconciliation against total_items across all
            # pages is task 1.B (FR-DQ-01/02, P001) — this only records
            # what one already-fetched page actually contained.
            "line_ids": [item["id"] for item in p["items"]],
        }

    return await _ingest(
        conn,
        contract=BOM_LINES_PAGE_CONTRACT,
        identity_params={"event_id": event_id, "PageNumber": payload["currentPage"]},
        raw_body=raw_body,
        payload=payload,
        normalize_fields=normalize_fields,
        correlation_id=correlation_id,
        item_contract=BOM_LINE_ITEM_CONTRACT,
        items_extractor=lambda p: p["items"],
    )


async def ingest_events_list_page(
    conn: AsyncConnection,
    *,
    raw_body: bytes,
    payload: dict[str, Any],
    query_params: dict[str, Any],
    correlation_id: str,
) -> TenderVersion:
    def normalize_fields(p: dict[str, Any]) -> dict[str, Any]:
        return {
            "current_page": p["currentPage"],
            "total_pages": p["totalPages"],
            "total_items": p["totalItems"],
            "event_ids_in_page": [item["eventId"] for item in p["items"]],
        }

    return await _ingest(
        conn,
        contract=EVENTS_LIST_PAGE_CONTRACT,
        identity_params={**query_params, "PageNumber": payload["currentPage"]},
        raw_body=raw_body,
        payload=payload,
        normalize_fields=normalize_fields,
        correlation_id=correlation_id,
    )


async def ingest_design_tender_signals_page(
    conn: AsyncConnection,
    *,
    raw_body: bytes,
    payload: dict[str, Any],
    query_params: dict[str, Any],
    correlation_id: str,
    observed_at: str,
) -> list[int]:
    version = await ingest_events_list_page(
        conn, raw_body=raw_body, payload=payload, query_params=query_params, correlation_id=correlation_id
    )

    signal_ids = []
    for item in payload["items"]:
        if not classify_design_tender(item["eventName"]):
            continue
        signal = build_design_tender_signal(
            item, raw_snapshot_id=version.raw_snapshot_id, observed_at=observed_at, correlation_id=correlation_id
        )
        signal_ids.append(await store_signal(conn, signal))
    return signal_ids


async def ingest_procurement_plan_page(
    conn: AsyncConnection,
    *,
    raw_body: bytes,
    payload: dict[str, Any],
    year: int,
    page_number: int,
    buyer_organization_name: str,
    correlation_id: str,
    observed_at: str,
) -> list[int]:
    identity_key = canonical_identity(
        APP_LIST_PAGE_CONTRACT,
        {"Year": str(year), "PageNumber": str(page_number), "BuyerOrganizationName": buyer_organization_name},
    )

    snapshot_id = await save_raw_snapshot(
        conn,
        source="etender",
        resource_type=APP_LIST_PAGE_CONTRACT.name,
        identity_key=identity_key,
        raw_body=raw_body,
        contract_version=APP_LIST_PAGE_CONTRACT.name,
        correlation_id=correlation_id,
    )

    drift = detect_schema_drift(APP_LIST_PAGE_CONTRACT, payload)
    drifted_contract_name = APP_LIST_PAGE_CONTRACT.name
    if not drift.has_drift:
        drift = detect_schema_drift_over_items(APP_ITEM_CONTRACT, payload["items"])
        drifted_contract_name = APP_ITEM_CONTRACT.name

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
    for item in payload["items"]:
        signal = build_procurement_plan_signal(
            item, raw_snapshot_id=snapshot_id, observed_at=observed_at, correlation_id=correlation_id
        )
        signal_ids.append(await store_signal(conn, signal))
    return signal_ids


class UnexpectedResponseStatus(Exception):
    pass


async def fetch_design_tender_page_live(
    conn: AsyncConnection,
    validator: EgressValidator,
    *,
    query_params: dict[str, Any],
    page_number: int,
) -> tuple[bytes, dict[str, Any]]:
    params = {**query_params, "PageNumber": page_number}
    url = f"https://etender.gov.az/api/events?{urlencode(params)}"
    status, body, _headers = await fetch_via_validator(conn, validator, url)
    if status != 200:
        raise UnexpectedResponseStatus(f"eTender events search returned HTTP {status} for {url!r}")
    return body, json.loads(body)

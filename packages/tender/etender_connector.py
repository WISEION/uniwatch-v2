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

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform import outbox

from .etender_contract import BOM_LINES_PAGE_CONTRACT, EVENT_DETAILS_CONTRACT, EVENTS_LIST_PAGE_CONTRACT
from .normalized import TenderVersion, create_normalized_version, get_or_create_tender
from .raw_snapshot import save_raw_snapshot
from .schema_drift import SchemaDrift, detect_schema_drift
from .source_contract import SourceContract, canonical_identity

PARSER_VERSION = "etender-v1"


@dataclass
class SchemaDriftDetected(Exception):
    drift: SchemaDrift
    contract_name: str
    raw_snapshot_id: int

    def __str__(self) -> str:
        return f"schema drift detected: {self.drift}"


async def _ingest(
    conn: AsyncConnection,
    *,
    contract: SourceContract,
    identity_params: dict[str, Any],
    raw_body: bytes,
    payload: dict[str, Any],
    normalize_fields: Callable[[dict[str, Any]], dict[str, Any]],
    correlation_id: str,
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
    if drift.has_drift:
        await outbox.enqueue(
            conn,
            aggregate_type="tender_source_contract",
            aggregate_id=contract.name,
            event_type="schema_drift_event",
            payload={
                "contract": contract.name,
                "identity_key": identity_key,
                "added_fields": list(drift.added_fields),
                "removed_fields": list(drift.removed_fields),
                "type_changed_fields": list(drift.type_changed_fields),
            },
            correlation_id=correlation_id,
        )
        raise SchemaDriftDetected(drift, contract_name=contract.name, raw_snapshot_id=snapshot_id)

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
    )


async def ingest_events_list_page(
    conn: AsyncConnection,
    *,
    raw_body: bytes,
    payload: dict[str, Any],
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
        identity_params={"PageNumber": payload["currentPage"]},
        raw_body=raw_body,
        payload=payload,
        normalize_fields=normalize_fields,
        correlation_id=correlation_id,
    )

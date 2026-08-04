"""eTender empirical-contract ingestion (INT-01, INT-02, FR-TND-10). Raw
evidence is captured unconditionally, before the drift check — evidence
capture must never depend on whether the connector currently understands
the shape it received. Only a drift-free response is normalized; a
drifted one is reported via the existing transactional outbox
(schema_drift_event) and raises, so nothing gets silently mapped against
a contract it no longer matches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform import outbox

from .normalized import TenderVersion, create_normalized_version, get_or_create_tender
from .raw_snapshot import save_raw_snapshot
from .schema_drift import SchemaDrift, detect_schema_drift
from .source_contract import SourceContract, canonical_identity

PARSER_VERSION = "etender-v1"


@dataclass
class SchemaDriftDetected(Exception):
    drift: SchemaDrift

    def __str__(self) -> str:
        return f"schema drift detected: {self.drift}"


async def ingest_event_details(
    conn: AsyncConnection,
    *,
    contract: SourceContract,
    raw_body: bytes,
    payload: dict[str, Any],
    correlation_id: str,
) -> TenderVersion:
    identity_key = canonical_identity(contract, {"id": payload["id"]})

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
        raise SchemaDriftDetected(drift)

    tender_id = await get_or_create_tender(conn, source="etender", identity_key=identity_key)

    normalized_fields = {
        "tender_name": payload["tenderName"],
        "organization_name": payload["organizationName"],
        "organization_voen": payload.get("organizationVoen"),
        # FR-TND-10 / INT-01: the actual returned value decides — this
        # connector never receives or trusts a requested EventType filter
        # value, only the eventType field the source actually returned.
        "event_type_actual": payload["eventType"],
        "estimated_amount": payload.get("estimatedAmount"),
        "document_number": payload["documentNumber"],
    }

    return await create_normalized_version(
        conn,
        tender_id=tender_id,
        raw_snapshot_id=snapshot_id,
        parser_version=PARSER_VERSION,
        normalized_fields=normalized_fields,
    )

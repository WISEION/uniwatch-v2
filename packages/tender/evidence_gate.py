"""Shared "capture evidence, then gate on the contract" mechanism every
source connector needs (INT-01, INT-02, FR-TND-10).

The order is the invariant: the raw body is saved unconditionally *before*
the drift check, so evidence capture never depends on whether the
connector currently understands the shape it received. Only a drift-free
payload is returned to the caller for normalization; a drifted one is
reported on the transactional outbox (`schema_drift_event`) and raises
`SchemaDriftDetected`, carrying the snapshot that was already saved."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform import outbox

from .raw_snapshot import save_raw_snapshot
from .schema_drift import SchemaDriftDetected, detect_schema_drift, detect_schema_drift_over_items
from .source_contract import SourceContract, canonical_identity


async def capture_and_gate(
    conn: AsyncConnection,
    *,
    source: str,
    contract: SourceContract,
    identity_params: dict[str, Any],
    raw_body: bytes,
    payload: dict[str, Any],
    correlation_id: str,
    outbox_aggregate_type: str,
    item_contract: SourceContract | None = None,
    items_extractor: Callable[[dict[str, Any]], list[dict[str, Any]]] | None = None,
) -> tuple[int, str]:
    """Saves the raw snapshot, then checks the payload (and, when an
    `item_contract` is given, every item `items_extractor` pulls out of it)
    against the frozen contract. Returns `(raw_snapshot_id, identity_key)`
    for a drift-free response; raises `SchemaDriftDetected` otherwise.

    `items_extractor` runs only once the page-level shape is known to be
    drift-free, so a page missing its items key is reported as drift, not
    raised as a `KeyError` from inside the check."""
    identity_key = canonical_identity(contract, identity_params)

    snapshot_id = await save_raw_snapshot(
        conn,
        source=source,
        resource_type=contract.name,
        identity_key=identity_key,
        raw_body=raw_body,
        contract_version=contract.name,
        correlation_id=correlation_id,
    )

    drift = detect_schema_drift(contract, payload)
    drifted_contract_name = contract.name
    if not drift.has_drift and item_contract is not None and items_extractor is not None:
        drift = detect_schema_drift_over_items(item_contract, items_extractor(payload))
        drifted_contract_name = item_contract.name

    if drift.has_drift:
        await outbox.enqueue(
            conn,
            aggregate_type=outbox_aggregate_type,
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

    return snapshot_id, identity_key

"""Annual procurement-plan signal (TENDER_INTELLIGENCE_SPEC.md §5.2, P309,
third signal source/category). List-endpoint slice only -- one Signal per
plan *submission*; the plan's own version/amendment history ("changes to
them", GET /api/app/{id}/versions) and line items (GET
/api/app-version/{id}/items) are real, confirmed-working eTender
endpoints but are deliberately not consumed here (each needs a per-plan
follow-up call -- a real scale concern for 1413+ plans/year, scoped to a
future task, not silently skipped)."""

from __future__ import annotations

from typing import Any

from .az_region_identity import canonicalize_region
from .signal_model import Signal


def build_procurement_plan_signal(
    item: dict[str, Any],
    *,
    raw_snapshot_id: int,
    observed_at: str,
    correlation_id: str,
) -> Signal:
    return Signal(
        signal_type="procurement_plan",
        source="etender",
        raw_snapshot_id=raw_snapshot_id,
        value={
            "app_id": item["id"],
            "organization_name": item["organizationName"],
            "year": item["year"],
            "create_date": item["createDate"],
        },
        observed_at=observed_at,
        # A budget/planning-cycle signal -- distinct from the World Bank
        # slice's "funding_decision" and the design-tender slice's
        # "design_phase_tender". Exact duration remains TBD-TIS-01.
        ttl_class="procurement_plan",
        # eTender is Azerbaijan's own official e-procurement portal --
        # same first-party-official tier as the other two eTender-derived
        # and World Bank signal types.
        confidence="official_source",
        object_customer=item["organizationName"],
        object_region=canonicalize_region(item["organizationName"]),
        object_project_type=None,
        correlation_id=correlation_id,
    )

"""Signal fact model (INV-15, INV-16, INV-17, TENDER_INTELLIGENCE_SPEC.md
§5.2, P309): pure assembly, no DB, no network -- mirrors
boq_line_model.py's "pure model assembly" shape from
task 2.A. `build_donor_pipeline_signal` is the one concrete builder this
task needs; a future signal source gets its own builder function, not a
change to this one (each source's fields differ too much for one generic
mapper to stay honest)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Signal:
    signal_type: str
    source: str
    raw_snapshot_id: int
    value: dict[str, Any]
    # INV-15: when this fact was actually observed (the raw snapshot's own
    # fetch time) -- not the source's self-reported update timestamp,
    # which is only present on some records (p2a_updated_date, 24/79 in
    # the real capture) and would make observed_at non-deterministic
    # depending on which records happen to carry it.
    observed_at: str
    ttl_class: str
    confidence: str
    object_customer: str | None
    object_region: str | None
    object_project_type: str | None
    correlation_id: str


def build_donor_pipeline_signal(
    project: dict[str, Any],
    *,
    raw_snapshot_id: int,
    observed_at: str,
    correlation_id: str,
) -> Signal:
    theme_name = None
    theme_namecode = project.get("mjtheme_namecode") or []
    if theme_namecode and theme_namecode[0].get("name"):
        theme_name = theme_namecode[0]["name"]

    return Signal(
        signal_type="donor_pipeline_project",
        source="worldbank_projects_api",
        raw_snapshot_id=raw_snapshot_id,
        value={
            "project_id": project["id"],
            "project_name": project["project_name"],
            "status": project["status"],
            # Kept as the source's own formatted string ("250,000,000") --
            # parsing to a numeric type is not needed by anything in this
            # task and is not invented speculatively (YAGNI).
            "total_amount_usd_text": project["totalamt"],
            "board_approval_date": project.get("boardapprovaldate"),
            "closing_date": project.get("closingdate"),
            "lending_instrument": project["lendinginstr"],
            "url": project["url"],
        },
        observed_at=observed_at,
        # INV-17: label only -- a donor-financed pipeline entry is the same
        # TTL *class* as TENDER_INTELLIGENCE_SPEC.md §2's own worked example
        # of a funding decision/decree. Exact duration remains TBD-TIS-01.
        ttl_class="funding_decision",
        # INV-15: World Bank publishing its own project pipeline is a
        # first-party official source -- the highest structural-reliability
        # tier this task defines. Not a calibrated probability (TBD-TIS-02).
        confidence="official_source",
        # impagency (implementing agency) is preferred over borrower when
        # both are present -- it is the entity that will actually run
        # procurement, closer to a real tender's buyer than the sovereign
        # borrower. Both are honestly None for a Pipeline-stage project
        # that has neither key at all (see P505208 in the test above).
        object_customer=project.get("impagency") or project.get("borrower"),
        # This source gives country-level geography only -- no
        # sub-national region field exists on this API's project records.
        object_region=project["countryname"][0] if project.get("countryname") else None,
        object_project_type=theme_name or project["mjthemecode"],
        correlation_id=correlation_id,
    )

"""Design/TEO-tender signal detection (TENDER_INTELLIGENCE_SPEC.md §5.2,
P309, second signal source/category after the World Bank donor-pipeline
slice). A derived signal over eTender events-list items eTender's own
existing empirical-contract connector (etender_connector.py) already
fetches and normalizes -- no new external host, no new raw-ingestion
contract.

`classify_design_tender` is a real, bounded keyword classifier, not an
exhaustive NLP model: `layihə` alone means "project" generically in
Azerbaijani (false positives exist, see the rejects-real-false-positives
test) as well as "design" in the construction-industry sense
(`layihə-smeta` = "design + estimate documents", the real, specific term).
Azerbaijani morphology matters here: the *verb* stem for "to design" is
`layihələn-`/`layihələm-` (the latter a real observed typo for the
former), while the *plural noun* "projects" is `layihələr-` -- both share
the first 8 characters (`layihələ`) but diverge at the 9th (`n`/`m` vs
`r`), so the stem list below uses the full 9-character verb forms, not
the shorter, ambiguous 8-character prefix. This trades some recall (an
eventName phrased in a way this classifier has not seen) for real
precision against every case captured so far -- same honest tradeoff
task 2.A recorded for its own English-only line-type keywords."""

from __future__ import annotations

from typing import Any

from .az_region_identity import canonicalize_region
from .signal_model import Signal

_DESIGN_TENDER_STEMS = ("layihə-smeta", "layihə smeta", "layihəsmeta", "layihələn", "layihələm")


def classify_design_tender(event_name: str) -> bool:
    normalized = event_name.lower()
    return any(stem in normalized for stem in _DESIGN_TENDER_STEMS)


def build_design_tender_signal(
    item: dict[str, Any],
    *,
    raw_snapshot_id: int,
    observed_at: str,
    correlation_id: str,
) -> Signal:
    return Signal(
        signal_type="design_tender",
        source="etender",
        raw_snapshot_id=raw_snapshot_id,
        value={
            "event_id": item["eventId"],
            "event_name": item["eventName"],
            "publish_date": item.get("publishDate"),
            # Only ever observed False under the EventStatus=1 (open) filter
            # this task's job uses (see docs/decisions/OPEN-QUESTIONS.md) --
            # kept as a real fact, not a fabricated True case, ready for
            # whichever EventStatus value means "awarded" once decoded.
            "is_awarded": item.get("awardedParticipantName") is not None,
            "awarded_participant_name": item.get("awardedParticipantName"),
        },
        observed_at=observed_at,
        # A distinct ttl_class from the World Bank slice's "funding_decision"
        # -- a published design/TEO tender is a shorter-horizon, later-stage
        # signal than a funding decree. Exact duration remains TBD-TIS-01.
        ttl_class="design_phase_tender",
        # eTender is Azerbaijan's own official e-procurement portal -- same
        # first-party-official tier as the World Bank's own project API.
        confidence="official_source",
        object_customer=item.get("buyerOrganizationName"),
        # eTender's events-list item has no structured region field --
        # canonicalize_region() extracts one from the buyer name when it
        # names a region this task has actually observed (e.g. a rayon
        # executive authority); still honestly None for buyers that don't
        # (e.g. a national utility) or that name an unobserved region --
        # see az_region_identity.py's own docstring for why the list isn't
        # exhaustive. object_project_type would need a separate real
        # category-keyword taxonomy, not attempted here.
        object_region=canonicalize_region(item.get("buyerOrganizationName", "")),
        object_project_type=None,
        correlation_id=correlation_id,
    )

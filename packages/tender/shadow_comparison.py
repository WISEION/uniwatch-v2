"""Shadow-comparison harness (FR-MIG-03, master plan Section24.4, Phase 6
task 6.A): compares a bounded, human-exported v1 snapshot against v2's own
already-fetched records for the same source+date range -- count, IDs,
status, key details, BOQ presence/completeness. Pure assembly, no DB, no
network, same shape as object_intersection.py/matching.py: the caller (a
future job in apps/worker, not built yet) is responsible for producing both
lists and for supplying whatever scope evidence it has; this module never
reaches into v1 itself (CLAUDE.md/AGENTS.md hard ban #1 -- v1 is permanently
off-limits to any code in this repo) and never reaches into a live v2
database either.

Record contract (both `v1_snapshot` and `v2_records` entries use this same
shape -- documented for real exporters in fixtures/legacy-snapshots/README.md):

    {
        "source_record_id": str,       # required; identity key comparable
                                        # across v1 and v2 for one bounded
                                        # source+date range
        "record_kind": str | None,     # optional sub-type label (e.g.
                                        # "design_tender", "procurement_plan")
                                        # when the source distinguishes one
        "status": str | None,
        "key_details": dict[str, Any], # flat scalar fields both sides are
                                        # expected to describe the same way
        "captured_at": str | None,     # ISO-8601; used only to judge whether
                                        # a field difference is plausibly a
                                        # real source change (never compared
                                        # as a key detail itself)
        "boq": {
            "present": bool,
            "completeness_status": str | None,  # None = this side has no
                                                 # completeness concept for
                                                 # this record at all
            "line_count": int | None,
        } | None,   # None entirely = this record kind has no BOQ concept
                    # on this side
    }

Every discrepancy is classified into exactly one of the four buckets
master plan Section24.4 names (`v1_loss`, `v2_defect`, `source_drift`,
`expected_semantic_difference`) -- OR, when neither side's own evidence in
the record resolves which bucket applies, `Discrepancy.bucket` is `None`
and `Discrepancy.reason` says exactly what evidence is missing. This is the
same "never silently fold an ambiguous case into a verdict" discipline
packages/tender/boq_summary.py's traffic-light logic and
packages/decision/matching.py's volume_status already apply (AGENTS.md
hard ban #3) -- a mismatch this module cannot honestly classify is
surfaced as unresolved, never guessed into one of the four buckets to make
the report look more complete than the evidence supports.

Classification rules, by discrepancy kind:

- ID present on only one side (`missing_from_v1` / `missing_from_v2`) and
  BOQ presence mismatches on a shared record: resolved via the optional
  `v1_covers_record_kinds` / `v2_covers_record_kinds` scope sets the caller
  may supply (built from that side's own known ingestion contract/audit --
  e.g. packages/tender/source_contract.py's identity/coverage for v2, or a
  human note about what v1 ever tracked). A record whose `record_kind` is
  outside the relevant side's declared scope is `expected_semantic_difference`
  (that side was never meant to carry it); inside scope but still absent is
  `v2_defect` (missing from v2) or `v1_loss` (missing from v1, proven real
  by v2 having ingested it). Without both a `record_kind` and the matching
  scope set, this module has no evidence either way and reports unresolved.

- Field mismatches (`status`, or a `key_details` key present on both
  sides with different values): `expected_semantic_difference` when the
  caller's `expected_field_differences` names that field as a known,
  intentional representation difference; `source_drift` when both records
  carry a parseable `captured_at` and v2's is strictly later than v1's
  (the underlying source plausibly changed between the two captures);
  otherwise unresolved -- a bare value difference does not by itself say
  whether the source changed, v1's export is stale, or v2 mis-parsed.

- A `key_details` key present on only one side is always
  `expected_semantic_difference` -- a field that does not exist on the
  other side at all is a structural schema difference, not a value drift,
  and needs no further evidence to say so.

- BOQ completeness mismatches (both sides show `boq.present = True` but
  different `completeness_status`): `expected_semantic_difference` when one
  side's status is `None` (that side has no completeness concept for this
  record at all); `v2_defect` when v1 reached `"complete"` and v2 did not
  reach further than `"incomplete"`; `v1_loss` when v2 reached `"complete"`
  and v1's own status never did; any other combination (e.g. one side
  `"in_progress"` against the other `"source_exhausted_unverified"`) is
  unresolved -- neither status is the source itself proven at fault.

Duplicate `source_record_id`s within one side's own list are a same-side
data-quality problem, not a v1-vs-v2 discrepancy, so they are reported
separately (`duplicate_source_record_ids_v1`/`_v2`) rather than folded into
the discrepancy list or silently resolved by "last one wins"."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

BUCKETS = frozenset({"v1_loss", "v2_defect", "source_drift", "expected_semantic_difference"})


@dataclass(frozen=True)
class Discrepancy:
    source_record_id: str
    kind: str  # "missing_from_v1" | "missing_from_v2" | "field_mismatch"
    # | "boq_presence_mismatch" | "boq_completeness_mismatch"
    field: str | None  # populated for "field_mismatch"/"boq_completeness_mismatch"; None otherwise
    v1_value: Any
    v2_value: Any
    bucket: str | None  # one of BUCKETS, or None when this module cannot honestly classify it
    reason: str  # always populated: explains the classification, or exactly what evidence is missing


@dataclass(frozen=True)
class ShadowComparisonReport:
    v1_count: int
    v2_count: int
    matched_count: int
    duplicate_source_record_ids_v1: tuple[str, ...]
    duplicate_source_record_ids_v2: tuple[str, ...]
    discrepancies: tuple[Discrepancy, ...]
    bucket_counts: dict[str, int]  # keys: the four buckets in BUCKETS, plus "unresolved"


def _index_by_id(records: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], tuple[str, ...]]:
    index: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for record in records:
        rid = record["source_record_id"]
        if rid in index:
            duplicates.append(rid)
        else:
            index[rid] = record
    return index, tuple(duplicates)


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _drift_plausible(v1_record: dict[str, Any], v2_record: dict[str, Any]) -> bool:
    v1_ts = _parse_timestamp(v1_record.get("captured_at"))
    v2_ts = _parse_timestamp(v2_record.get("captured_at"))
    if v1_ts is None or v2_ts is None:
        return False
    return v2_ts > v1_ts


def _classify_scoped_absence(
    *,
    rid: str,
    kind: str,
    record_kind: str | None,
    covers_record_kinds: frozenset[str] | None,
    missing_side: str,  # "v1" | "v2"
    defect_bucket: str,  # "v1_loss" | "v2_defect"
    v1_value: Any,
    v2_value: Any,
) -> Discrepancy:
    if covers_record_kinds is not None and record_kind is not None:
        if record_kind in covers_record_kinds:
            bucket: str | None = defect_bucket
            reason = (
                f"record_kind {record_kind!r} is inside the supplied in-scope set for {missing_side}'s own "
                "ingestion contract; its absence is not explained by scope"
            )
        else:
            bucket = "expected_semantic_difference"
            reason = (
                f"record_kind {record_kind!r} is outside the supplied in-scope set for {missing_side}; "
                f"this side was never meant to carry it"
            )
    else:
        bucket = None
        scope_param = "v2_covers_record_kinds" if missing_side == "v2" else "v1_covers_record_kinds"
        reason = (
            f"cannot determine whether this record's kind is in scope for {missing_side}'s ingestion contract "
            f"-- supply record_kind and {scope_param} to classify"
        )
    return Discrepancy(
        source_record_id=rid,
        kind=kind,
        field=None,
        v1_value=v1_value,
        v2_value=v2_value,
        bucket=bucket,
        reason=reason,
    )


def _classify_field_mismatch(
    *,
    rid: str,
    field: str,
    v1_value: Any,
    v2_value: Any,
    v1_record: dict[str, Any],
    v2_record: dict[str, Any],
    expected_field_differences: frozenset[str] | None,
) -> Discrepancy:
    if expected_field_differences is not None and field in expected_field_differences:
        bucket: str | None = "expected_semantic_difference"
        reason = (
            f"field {field!r} is in the supplied expected-field-differences set (known intentional representation difference)"
        )
    elif _drift_plausible(v1_record, v2_record):
        bucket = "source_drift"
        reason = "captured_at shows v2 observed this record after v1; the underlying source value plausibly changed in between"
    else:
        bucket = None
        reason = (
            f"field {field!r} differs ({v1_value!r} vs {v2_value!r}) but neither an expected-field-differences "
            "declaration nor a captured_at ordering explains whether this is a genuine source change or a defect"
        )
    return Discrepancy(
        source_record_id=rid,
        kind="field_mismatch",
        field=field,
        v1_value=v1_value,
        v2_value=v2_value,
        bucket=bucket,
        reason=reason,
    )


def _classify_boq_completeness_mismatch(*, rid: str, v1_status: str | None, v2_status: str | None) -> Discrepancy:
    if v1_status is None:
        bucket: str | None = "expected_semantic_difference"
        reason = (
            "v1 side carries no BOQ completeness concept for this record "
            "(completeness_status is None); v2 introduces one by design"
        )
    elif v2_status is None:
        bucket = "expected_semantic_difference"
        reason = "v2 side carries no BOQ completeness concept for this record (completeness_status is None)"
    elif v1_status == "complete" and v2_status == "incomplete":
        bucket = "v2_defect"
        reason = "v1 reconciled this BOQ to complete; v2's own reconciliation ended incomplete for the same record"
    elif v2_status == "complete" and v1_status != "complete":
        bucket = "v1_loss"
        reason = "v2 reconciled this BOQ to complete; v1's own status never reached complete for the same record"
    else:
        bucket = None
        reason = (
            f"BOQ completeness status differs ({v1_status!r} vs {v2_status!r}) but neither value is the "
            "unambiguous complete/incomplete pair that would identify which side is at fault"
        )
    return Discrepancy(
        source_record_id=rid,
        kind="boq_completeness_mismatch",
        field="completeness_status",
        v1_value=v1_status,
        v2_value=v2_status,
        bucket=bucket,
        reason=reason,
    )


def compare_snapshots(
    v1_snapshot: list[dict[str, Any]],
    v2_records: list[dict[str, Any]],
    *,
    v1_covers_record_kinds: frozenset[str] | None = None,
    v2_covers_record_kinds: frozenset[str] | None = None,
    expected_field_differences: frozenset[str] | None = None,
) -> ShadowComparisonReport:
    """Compare a bounded v1 export against v2's own records for the same
    source+date range. Both lists use the record contract documented in
    this module's docstring. `v1_covers_record_kinds`/`v2_covers_record_kinds`
    and `expected_field_differences` are optional scope evidence only the
    caller can supply (from a side's own ingestion contract/audit) -- omit
    them and the affected discrepancies are honestly reported as
    unresolved rather than guessed."""
    v1_index, duplicate_v1 = _index_by_id(v1_snapshot)
    v2_index, duplicate_v2 = _index_by_id(v2_records)

    v1_ids = set(v1_index)
    v2_ids = set(v2_index)
    common_ids = v1_ids & v2_ids

    discrepancies: list[Discrepancy] = []

    for rid in sorted(v1_ids - v2_ids):
        v1_record = v1_index[rid]
        discrepancies.append(
            _classify_scoped_absence(
                rid=rid,
                kind="missing_from_v2",
                record_kind=v1_record.get("record_kind"),
                covers_record_kinds=v2_covers_record_kinds,
                missing_side="v2",
                defect_bucket="v2_defect",
                v1_value=True,
                v2_value=False,
            )
        )

    for rid in sorted(v2_ids - v1_ids):
        v2_record = v2_index[rid]
        discrepancies.append(
            _classify_scoped_absence(
                rid=rid,
                kind="missing_from_v1",
                record_kind=v2_record.get("record_kind"),
                covers_record_kinds=v1_covers_record_kinds,
                missing_side="v1",
                defect_bucket="v1_loss",
                v1_value=False,
                v2_value=True,
            )
        )

    for rid in sorted(common_ids):
        v1_record = v1_index[rid]
        v2_record = v2_index[rid]

        v1_status = v1_record.get("status")
        v2_status = v2_record.get("status")
        if v1_status != v2_status:
            discrepancies.append(
                _classify_field_mismatch(
                    rid=rid,
                    field="status",
                    v1_value=v1_status,
                    v2_value=v2_status,
                    v1_record=v1_record,
                    v2_record=v2_record,
                    expected_field_differences=expected_field_differences,
                )
            )

        v1_details: dict[str, Any] = v1_record.get("key_details") or {}
        v2_details: dict[str, Any] = v2_record.get("key_details") or {}

        for key in sorted(set(v1_details) & set(v2_details)):
            v1_value = v1_details[key]
            v2_value = v2_details[key]
            if v1_value != v2_value:
                discrepancies.append(
                    _classify_field_mismatch(
                        rid=rid,
                        field=key,
                        v1_value=v1_value,
                        v2_value=v2_value,
                        v1_record=v1_record,
                        v2_record=v2_record,
                        expected_field_differences=expected_field_differences,
                    )
                )

        for key in sorted(set(v1_details) - set(v2_details)):
            discrepancies.append(
                Discrepancy(
                    source_record_id=rid,
                    kind="field_mismatch",
                    field=key,
                    v1_value=v1_details[key],
                    v2_value=None,
                    bucket="expected_semantic_difference",
                    reason=(
                        f"key_details field {key!r} does not exist on the v2 side at all "
                        "-- a structural schema difference, not a value drift"
                    ),
                )
            )

        for key in sorted(set(v2_details) - set(v1_details)):
            discrepancies.append(
                Discrepancy(
                    source_record_id=rid,
                    kind="field_mismatch",
                    field=key,
                    v1_value=None,
                    v2_value=v2_details[key],
                    bucket="expected_semantic_difference",
                    reason=(
                        f"key_details field {key!r} does not exist on the v1 side at all "
                        "-- a structural schema difference, not a value drift"
                    ),
                )
            )

        v1_boq = v1_record.get("boq")
        v2_boq = v2_record.get("boq")
        v1_present = bool(v1_boq and v1_boq.get("present"))
        v2_present = bool(v2_boq and v2_boq.get("present"))

        if v1_present and not v2_present:
            discrepancies.append(
                _classify_scoped_absence(
                    rid=rid,
                    kind="boq_presence_mismatch",
                    record_kind=v1_record.get("record_kind"),
                    covers_record_kinds=v2_covers_record_kinds,
                    missing_side="v2",
                    defect_bucket="v2_defect",
                    v1_value=True,
                    v2_value=False,
                )
            )
        elif v2_present and not v1_present:
            discrepancies.append(
                _classify_scoped_absence(
                    rid=rid,
                    kind="boq_presence_mismatch",
                    record_kind=v2_record.get("record_kind"),
                    covers_record_kinds=v1_covers_record_kinds,
                    missing_side="v1",
                    defect_bucket="v1_loss",
                    v1_value=False,
                    v2_value=True,
                )
            )
        elif v1_present and v2_present:
            v1_completeness = v1_boq.get("completeness_status") if v1_boq else None
            v2_completeness = v2_boq.get("completeness_status") if v2_boq else None
            if v1_completeness != v2_completeness:
                discrepancies.append(
                    _classify_boq_completeness_mismatch(
                        rid=rid,
                        v1_status=v1_completeness,
                        v2_status=v2_completeness,
                    )
                )

    bucket_counts: dict[str, int] = dict.fromkeys(BUCKETS, 0)
    bucket_counts["unresolved"] = 0
    for discrepancy in discrepancies:
        if discrepancy.bucket is None:
            bucket_counts["unresolved"] += 1
        else:
            bucket_counts[discrepancy.bucket] += 1

    return ShadowComparisonReport(
        v1_count=len(v1_snapshot),
        v2_count=len(v2_records),
        matched_count=len(common_ids),
        duplicate_source_record_ids_v1=duplicate_v1,
        duplicate_source_record_ids_v2=duplicate_v2,
        discrepancies=tuple(discrepancies),
        bucket_counts=bucket_counts,
    )

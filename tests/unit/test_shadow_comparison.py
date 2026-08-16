"""Unit tests for packages/tender/shadow_comparison.py (FR-MIG-03, master
plan Section24.4, Phase 6 task 6.A shadow-comparison harness).

Covers all four Section24.4 buckets (`v1_loss`, `v2_defect`, `source_drift`,
`expected_semantic_difference`) plus the honest "cannot classify" report
case (AGENTS.md hard ban #3: no silent fallback verdict)."""

from __future__ import annotations

from packages.tender.shadow_comparison import compare_snapshots


def _record(rid: str, **overrides):
    base = {
        "source_record_id": rid,
        "record_kind": None,
        "status": "open",
        "key_details": {},
        "captured_at": None,
        "boq": None,
    }
    base.update(overrides)
    return base


def test_identical_snapshots_produce_no_discrepancies():
    v1 = [_record("T-1"), _record("T-2")]
    v2 = [_record("T-1"), _record("T-2")]

    report = compare_snapshots(v1, v2)

    assert report.v1_count == 2
    assert report.v2_count == 2
    assert report.matched_count == 2
    assert report.discrepancies == ()
    assert report.bucket_counts == {
        "v1_loss": 0,
        "v2_defect": 0,
        "source_drift": 0,
        "expected_semantic_difference": 0,
        "unresolved": 0,
    }


def test_missing_from_v2_in_scope_is_v2_defect():
    v1 = [_record("T-1", record_kind="design_tender")]
    v2: list[dict] = []

    report = compare_snapshots(v1, v2, v2_covers_record_kinds=frozenset({"design_tender"}))

    assert len(report.discrepancies) == 1
    d = report.discrepancies[0]
    assert d.kind == "missing_from_v2"
    assert d.bucket == "v2_defect"
    assert report.bucket_counts["v2_defect"] == 1


def test_missing_from_v2_out_of_scope_is_expected_semantic_difference():
    v1 = [_record("T-1", record_kind="procurement_plan")]
    v2: list[dict] = []

    report = compare_snapshots(v1, v2, v2_covers_record_kinds=frozenset({"design_tender"}))

    d = report.discrepancies[0]
    assert d.kind == "missing_from_v2"
    assert d.bucket == "expected_semantic_difference"


def test_missing_from_v2_without_scope_evidence_is_unresolved():
    v1 = [_record("T-1", record_kind="design_tender")]
    v2: list[dict] = []

    report = compare_snapshots(v1, v2)  # no v2_covers_record_kinds supplied

    d = report.discrepancies[0]
    assert d.kind == "missing_from_v2"
    assert d.bucket is None
    assert "record_kind" in d.reason
    assert report.bucket_counts["unresolved"] == 1


def test_missing_from_v1_in_scope_is_v1_loss():
    v1: list[dict] = []
    v2 = [_record("T-1", record_kind="design_tender")]

    report = compare_snapshots(v1, v2, v1_covers_record_kinds=frozenset({"design_tender"}))

    d = report.discrepancies[0]
    assert d.kind == "missing_from_v1"
    assert d.bucket == "v1_loss"


def test_missing_from_v1_out_of_scope_is_expected_semantic_difference():
    v1: list[dict] = []
    v2 = [_record("T-1", record_kind="worldbank_pipeline")]

    report = compare_snapshots(v1, v2, v1_covers_record_kinds=frozenset({"design_tender"}))

    d = report.discrepancies[0]
    assert d.kind == "missing_from_v1"
    assert d.bucket == "expected_semantic_difference"


def test_status_mismatch_with_captured_at_ordering_is_source_drift():
    v1 = [_record("T-1", status="open", captured_at="2026-08-01T00:00:00")]
    v2 = [_record("T-1", status="closed", captured_at="2026-08-10T00:00:00")]

    report = compare_snapshots(v1, v2)

    assert len(report.discrepancies) == 1
    d = report.discrepancies[0]
    assert d.kind == "field_mismatch"
    assert d.field == "status"
    assert d.bucket == "source_drift"


def test_status_mismatch_without_timestamps_is_unresolved():
    v1 = [_record("T-1", status="open")]
    v2 = [_record("T-1", status="closed")]

    report = compare_snapshots(v1, v2)

    d = report.discrepancies[0]
    assert d.bucket is None
    assert report.bucket_counts["unresolved"] == 1


def test_key_detail_mismatch_declared_as_expected_difference():
    v1 = [_record("T-1", key_details={"title": "Foo LLC"})]
    v2 = [_record("T-1", key_details={"title": "FOO LLC"})]

    report = compare_snapshots(v1, v2, expected_field_differences=frozenset({"title"}))

    d = report.discrepancies[0]
    assert d.field == "title"
    assert d.bucket == "expected_semantic_difference"


def test_key_detail_present_only_on_one_side_is_expected_semantic_difference():
    v1 = [_record("T-1", key_details={"region": "Baku"})]
    v2 = [_record("T-1", key_details={})]

    report = compare_snapshots(v1, v2)

    d = report.discrepancies[0]
    assert d.field == "region"
    assert d.v1_value == "Baku"
    assert d.v2_value is None
    assert d.bucket == "expected_semantic_difference"


def test_boq_present_in_v1_missing_in_v2_in_scope_is_v2_defect():
    v1 = [_record("T-1", record_kind="design_tender", boq={"present": True, "completeness_status": "complete", "line_count": 10})]
    v2 = [_record("T-1", record_kind="design_tender", boq=None)]

    report = compare_snapshots(v1, v2, v2_covers_record_kinds=frozenset({"design_tender"}))

    d = report.discrepancies[0]
    assert d.kind == "boq_presence_mismatch"
    assert d.bucket == "v2_defect"


def test_boq_present_in_v2_missing_in_v1_in_scope_is_v1_loss():
    v1 = [_record("T-1", record_kind="design_tender", boq=None)]
    v2 = [_record("T-1", record_kind="design_tender", boq={"present": True, "completeness_status": "complete", "line_count": 5})]

    report = compare_snapshots(v1, v2, v1_covers_record_kinds=frozenset({"design_tender"}))

    d = report.discrepancies[0]
    assert d.kind == "boq_presence_mismatch"
    assert d.bucket == "v1_loss"


def test_boq_completeness_v1_complete_v2_incomplete_is_v2_defect():
    v1 = [_record("T-1", boq={"present": True, "completeness_status": "complete", "line_count": 10})]
    v2 = [_record("T-1", boq={"present": True, "completeness_status": "incomplete", "line_count": 7})]

    report = compare_snapshots(v1, v2)

    d = report.discrepancies[0]
    assert d.kind == "boq_completeness_mismatch"
    assert d.bucket == "v2_defect"


def test_boq_completeness_v2_complete_v1_not_is_v1_loss():
    v1 = [_record("T-1", boq={"present": True, "completeness_status": "in_progress", "line_count": 3})]
    v2 = [_record("T-1", boq={"present": True, "completeness_status": "complete", "line_count": 10})]

    report = compare_snapshots(v1, v2)

    d = report.discrepancies[0]
    assert d.kind == "boq_completeness_mismatch"
    assert d.bucket == "v1_loss"


def test_boq_completeness_v1_has_no_concept_is_expected_semantic_difference():
    v1 = [_record("T-1", boq={"present": True, "completeness_status": None, "line_count": None})]
    v2 = [_record("T-1", boq={"present": True, "completeness_status": "complete", "line_count": 10})]

    report = compare_snapshots(v1, v2)

    d = report.discrepancies[0]
    assert d.kind == "boq_completeness_mismatch"
    assert d.bucket == "expected_semantic_difference"


def test_boq_completeness_ambiguous_combination_is_unresolved():
    v1 = [_record("T-1", boq={"present": True, "completeness_status": "in_progress", "line_count": 3})]
    v2 = [_record("T-1", boq={"present": True, "completeness_status": "source_exhausted_unverified", "line_count": 3})]

    report = compare_snapshots(v1, v2)

    d = report.discrepancies[0]
    assert d.kind == "boq_completeness_mismatch"
    assert d.bucket is None
    assert report.bucket_counts["unresolved"] == 1


def test_duplicate_ids_are_reported_separately_not_folded_into_discrepancies():
    v1 = [_record("T-1"), _record("T-1")]
    v2 = [_record("T-1")]

    report = compare_snapshots(v1, v2)

    assert report.duplicate_source_record_ids_v1 == ("T-1",)
    assert report.duplicate_source_record_ids_v2 == ()
    assert report.discrepancies == ()

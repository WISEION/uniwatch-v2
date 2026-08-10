from __future__ import annotations

from packages.tender.tender_change_detection import (
    DEADLINE_FIELDS,
    TenderFieldChange,
    classify_change_type,
    diff_normalized_fields,
)


def test_diff_normalized_fields_returns_empty_for_identical_dicts():
    old = {"id": 355920, "end_date": 1788354059, "document_number": "DOC-1"}
    new = dict(old)
    assert diff_normalized_fields(old, new) == ()


def test_diff_normalized_fields_reports_a_changed_value():
    old = {"id": 355920, "end_date": 1788354059}
    new = {"id": 355920, "end_date": 1790000000}
    result = diff_normalized_fields(old, new)
    assert result == (TenderFieldChange(field="end_date", old_value=1788354059, new_value=1790000000),)


def test_diff_normalized_fields_reports_a_key_added_in_new():
    old = {"id": 355920}
    new = {"id": 355920, "document_number": "DOC-2"}
    result = diff_normalized_fields(old, new)
    assert result == (TenderFieldChange(field="document_number", old_value=None, new_value="DOC-2"),)


def test_diff_normalized_fields_reports_a_key_removed_in_new():
    old = {"id": 355920, "document_number": "DOC-1"}
    new = {"id": 355920}
    result = diff_normalized_fields(old, new)
    assert result == (TenderFieldChange(field="document_number", old_value="DOC-1", new_value=None),)


def test_diff_normalized_fields_ignores_the_id_field():
    # "id" is the bridge key added for C1 (Task 4.A) -- it never legitimately
    # "changes" for the same tender and must never itself trigger a
    # tender_change_event.
    old = {"id": 355920, "document_number": "DOC-1"}
    new = {"id": 999999, "document_number": "DOC-1"}
    assert diff_normalized_fields(old, new) == ()


def test_classify_change_type_deadline_shift_when_a_deadline_field_changed():
    changes = (TenderFieldChange(field="end_date", old_value=1, new_value=2),)
    assert classify_change_type(changes) == "deadline_shift"


def test_classify_change_type_document_changed_for_a_non_deadline_field():
    changes = (TenderFieldChange(field="document_number", old_value="A", new_value="B"),)
    assert classify_change_type(changes) == "document_changed"


def test_classify_change_type_deadline_shift_wins_when_both_kinds_changed():
    changes = (
        TenderFieldChange(field="document_number", old_value="A", new_value="B"),
        TenderFieldChange(field="end_date", old_value=1, new_value=2),
    )
    assert classify_change_type(changes) == "deadline_shift"


def test_deadline_fields_are_exactly_the_three_date_fields():
    assert DEADLINE_FIELDS == frozenset({"end_date", "envelope_date", "start_date"})

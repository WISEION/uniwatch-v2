"""FR-TND-10 / INT-02: a response-shape change must produce a detectable
drift event, never a silent field loss."""

from __future__ import annotations

from packages.tender.schema_drift import detect_schema_drift
from packages.tender.source_contract import FieldSpec, SourceContract

CONTRACT = SourceContract(
    name="etender.event_details",
    identity_query_keys=("id",),
    fields=(
        FieldSpec("id", "number"),
        FieldSpec("eventType", "number"),
        FieldSpec("cpvCode", "null"),
    ),
)

GOOD_PAYLOAD = {"id": 355920, "eventType": 7, "cpvCode": None}


def test_no_drift_on_matching_fixture():
    drift = detect_schema_drift(CONTRACT, GOOD_PAYLOAD)
    assert drift.has_drift is False


def test_detects_added_field():
    payload = {**GOOD_PAYLOAD, "newField": "surprise"}
    drift = detect_schema_drift(CONTRACT, payload)
    assert drift.has_drift is True
    assert drift.added_fields == ("newField",)


def test_detects_removed_field():
    payload = {"id": 355920, "eventType": 7}  # cpvCode missing entirely
    drift = detect_schema_drift(CONTRACT, payload)
    assert drift.has_drift is True
    assert drift.removed_fields == ("cpvCode",)


def test_detects_type_changed_field():
    payload = {**GOOD_PAYLOAD, "eventType": "7"}  # number -> string
    drift = detect_schema_drift(CONTRACT, payload)
    assert drift.has_drift is True
    assert drift.type_changed_fields == ("eventType",)


def test_null_value_does_not_count_as_drift_for_a_typed_field():
    # A field that is normally a number can legitimately be null on some
    # records (e.g. an unpriced tender) — that is data variation, not
    # schema drift, and must not be flagged.
    payload = {**GOOD_PAYLOAD, "eventType": None}
    drift = detect_schema_drift(CONTRACT, payload)
    assert drift.has_drift is False


def test_optional_field_absent_is_not_drift():
    contract = SourceContract(
        name="test.optional",
        identity_query_keys=("id",),
        fields=(
            FieldSpec("id", "number"),
            FieldSpec("nickname", "string", optional=True),
        ),
    )
    drift = detect_schema_drift(contract, {"id": 1})
    assert not drift.has_drift


def test_required_field_absent_is_still_drift():
    contract = SourceContract(
        name="test.required",
        identity_query_keys=("id",),
        fields=(
            FieldSpec("id", "number"),
            FieldSpec("nickname", "string"),
        ),
    )
    drift = detect_schema_drift(contract, {"id": 1})
    assert drift.has_drift
    assert drift.removed_fields == ("nickname",)


def test_optional_field_present_with_wrong_type_is_still_drift():
    contract = SourceContract(
        name="test.optional_type",
        identity_query_keys=("id",),
        fields=(
            FieldSpec("id", "number"),
            FieldSpec("nickname", "string", optional=True),
        ),
    )
    drift = detect_schema_drift(contract, {"id": 1, "nickname": 42})
    assert drift.has_drift
    assert drift.type_changed_fields == ("nickname",)

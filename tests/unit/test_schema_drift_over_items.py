"""FR-TND-10, INT-02: item-level drift inside a page's `items` array must
be detectable too -- today's page-level-only check would silently miss a
per-item field being added/removed/retyped, since `items` itself is just
declared as an opaque 'array' field."""

from __future__ import annotations

from packages.tender.schema_drift import detect_schema_drift_over_items
from packages.tender.source_contract import FieldSpec, SourceContract

ITEM_CONTRACT = SourceContract(
    name="etender.bom_lines_page.item",
    identity_query_keys=("id",),
    fields=(
        FieldSpec("id", "number"),
        FieldSpec("description", "string"),
        FieldSpec("quantity", "number"),
    ),
)


def test_no_drift_when_every_item_matches():
    items = [{"id": 1, "description": "a", "quantity": 1}, {"id": 2, "description": "b", "quantity": 2}]
    drift = detect_schema_drift_over_items(ITEM_CONTRACT, items)
    assert drift.has_drift is False


def test_detects_drift_on_a_single_item_among_many_clean_ones():
    items = [
        {"id": 1, "description": "a", "quantity": 1},
        {"id": 2, "description": "b", "quantity": "2"},  # type changed on this one item only
        {"id": 3, "description": "c", "quantity": 3},
    ]
    drift = detect_schema_drift_over_items(ITEM_CONTRACT, items)
    assert drift.has_drift is True
    assert drift.type_changed_fields == ("quantity",)


def test_aggregates_distinct_drift_kinds_across_different_items_without_duplicates():
    items = [
        {"id": 1, "description": "a", "quantity": 1, "extra": "x"},  # added field
        {"id": 2, "quantity": 2},  # removed field (description)
        {"id": 3, "description": "c", "quantity": 3, "extra": "y"},  # same added field again
    ]
    drift = detect_schema_drift_over_items(ITEM_CONTRACT, items)
    assert drift.added_fields == ("extra",)
    assert drift.removed_fields == ("description",)


def test_empty_items_list_has_no_drift():
    drift = detect_schema_drift_over_items(ITEM_CONTRACT, [])
    assert drift.has_drift is False

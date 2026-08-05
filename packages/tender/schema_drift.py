"""Schema-drift detector (FR-TND-10, INT-02): compares an actual response
payload's shape against its frozen SourceContract. Any added field,
removed field, or incompatible type change is reported — never silently
absorbed. A field going to `null` is data variation, not drift, and is
deliberately not flagged (a genuinely incompatible type, e.g. a number
field turning into a string, still is)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .source_contract import SourceContract


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise TypeError(f"unsupported JSON value type: {type(value)!r}")


@dataclass(frozen=True)
class SchemaDrift:
    added_fields: tuple[str, ...]
    removed_fields: tuple[str, ...]
    type_changed_fields: tuple[str, ...]

    @property
    def has_drift(self) -> bool:
        return bool(self.added_fields or self.removed_fields or self.type_changed_fields)


def detect_schema_drift(contract: SourceContract, actual_payload: dict) -> SchemaDrift:
    declared = {field.name: field for field in contract.fields}
    declared_keys = set(declared.keys())
    actual_keys = set(actual_payload.keys())

    missing_keys = declared_keys - actual_keys
    removed = tuple(sorted(key for key in missing_keys if not declared[key].optional))
    added = tuple(sorted(actual_keys - declared_keys))

    type_changed = []
    for name in sorted(declared_keys & actual_keys):
        actual_value = actual_payload[name]
        if actual_value is None:
            continue
        if _json_type(actual_value) != declared[name].type:
            type_changed.append(name)

    return SchemaDrift(added_fields=added, removed_fields=removed, type_changed_fields=tuple(type_changed))


def detect_schema_drift_over_items(item_contract: SourceContract, items: list[dict]) -> SchemaDrift:
    """Runs detect_schema_drift once per item and unions the results --
    one drifted item among thousands of clean ones must still be reported,
    not averaged away."""
    added: set[str] = set()
    removed: set[str] = set()
    type_changed: set[str] = set()
    for item in items:
        item_drift = detect_schema_drift(item_contract, item)
        added.update(item_drift.added_fields)
        removed.update(item_drift.removed_fields)
        type_changed.update(item_drift.type_changed_fields)
    return SchemaDrift(
        added_fields=tuple(sorted(added)),
        removed_fields=tuple(sorted(removed)),
        type_changed_fields=tuple(sorted(type_changed)),
    )

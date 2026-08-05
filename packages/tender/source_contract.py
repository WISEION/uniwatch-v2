"""Source contract for an empirical (undocumented-API) connector (INT-01,
INT-02, FR-TND-10). `identity_query_keys` fixes exactly which parameters
define a record's identity for this contract, so identity is never lost to
a generic URL/query canonicalizer that doesn't know which params matter
(RN-06)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str  # "string" | "number" | "boolean" | "null" | "array" | "object"
    optional: bool = False  # True: the source is known to sometimes omit this key entirely
    # (not the same as a present key whose value is null — see schema_drift.py's null-value rule).


@dataclass(frozen=True)
class SourceContract:
    name: str
    identity_query_keys: tuple[str, ...]
    fields: tuple[FieldSpec, ...]


def canonical_identity(contract: SourceContract, params: dict) -> str:
    parts = [f"{key}={params[key]}" for key in contract.identity_query_keys]
    return contract.name + "|" + "&".join(parts)

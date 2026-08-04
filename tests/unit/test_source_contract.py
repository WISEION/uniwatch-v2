"""INT-02: identity_query_keys — a record's identity must not be lost to
naive URL/param canonicalization (RN-06: `?newsID=N` dropped by a
canonicalizer that discarded the whole query string)."""

from __future__ import annotations

import pytest

from packages.tender.source_contract import FieldSpec, SourceContract, canonical_identity

CONTRACT = SourceContract(
    name="etender.event_details",
    identity_query_keys=("id",),
    fields=(FieldSpec("id", "number"),),
)

PAGED_CONTRACT = SourceContract(
    name="etender.bom_lines_page",
    identity_query_keys=("event_id", "PageNumber"),
    fields=(FieldSpec("currentPage", "number"),),
)


def test_canonical_identity_uses_only_declared_keys():
    identity = canonical_identity(CONTRACT, {"id": 355920})
    assert identity == "etender.event_details|id=355920"


def test_canonical_identity_distinguishes_records_a_naive_canonicalizer_would_merge():
    # RN-06: dropping the query string entirely would merge these two.
    a = canonical_identity(CONTRACT, {"id": 355920})
    b = canonical_identity(CONTRACT, {"id": 355921})
    assert a != b


def test_canonical_identity_uses_all_identity_query_keys_for_paged_resources():
    page1 = canonical_identity(PAGED_CONTRACT, {"event_id": 355920, "PageNumber": 1})
    page2 = canonical_identity(PAGED_CONTRACT, {"event_id": 355920, "PageNumber": 2})
    assert page1 != page2


def test_canonical_identity_raises_on_missing_identity_key():
    with pytest.raises(KeyError):
        canonical_identity(CONTRACT, {})

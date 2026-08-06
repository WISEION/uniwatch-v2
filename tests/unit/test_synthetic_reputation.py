"""Unit tests for the deterministic synthetic reputation-fact generator
(task 3.B). Same seed-determinism discipline as
tests/unit/test_synthetic_provider.py -- real reputation facts are
supposed to come from Phase 4's Execution Ledger (not built yet), so
this generator proves the ReputationFact mechanism on a synthetic mix of
reliable/unreliable vendor histories, not real vendor outcomes."""

from __future__ import annotations

from packages.vendor.reputation_model import NEGATIVE_EVENT_TYPES, POSITIVE_EVENT_TYPES
from packages.vendor.synthetic_reputation import generate_reputation_facts

AS_OF = "2026-08-06T00:00:00+00:00"
VENDOR_NAMES = ["Vendor A", "Vendor B", "Vendor C", "Vendor D"]


def test_same_seed_and_as_of_produce_identical_output():
    first = generate_reputation_facts(VENDOR_NAMES, seed=42, as_of=AS_OF)
    second = generate_reputation_facts(VENDOR_NAMES, seed=42, as_of=AS_OF)
    assert first == second


def test_different_seeds_produce_different_output():
    first = generate_reputation_facts(VENDOR_NAMES, seed=42, as_of=AS_OF)
    second = generate_reputation_facts(VENDOR_NAMES, seed=43, as_of=AS_OF)
    assert first != second


def test_produces_a_mix_of_reliable_and_unreliable_vendor_histories():
    facts = generate_reputation_facts(VENDOR_NAMES, seed=42, as_of=AS_OF)
    by_vendor: dict[str, list[str]] = {}
    for fact in facts:
        by_vendor.setdefault(fact.vendor_name, []).append(fact.event_type)

    assert len(by_vendor) == len(VENDOR_NAMES)
    has_a_reliable_vendor = any(all(event_type in POSITIVE_EVENT_TYPES for event_type in events) for events in by_vendor.values())
    has_an_unreliable_vendor = any(
        all(event_type in NEGATIVE_EVENT_TYPES for event_type in events) for events in by_vendor.values()
    )
    assert has_a_reliable_vendor
    assert has_an_unreliable_vendor


def test_every_fact_is_sandbox_realm_and_synthetic_watermarked():
    facts = generate_reputation_facts(VENDOR_NAMES, seed=42, as_of=AS_OF)
    assert all(fact.data_realm == "vendor-sandbox" and fact.watermark == "SYNTHETIC" for fact in facts)


def test_every_fact_carries_a_mandatory_source_ref():
    facts = generate_reputation_facts(VENDOR_NAMES, seed=42, as_of=AS_OF)
    assert all(fact.source_ref for fact in facts)

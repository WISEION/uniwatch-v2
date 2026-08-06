"""Deterministic synthetic reputation-fact generator (task 3.B, same
seed-determinism discipline as synthetic_provider.py). Real reputation
facts are supposed to come from Phase 4's Execution Ledger, market data,
and courts/debt records (TENDER_INTELLIGENCE_SPEC.md Section6.2) -- none
of which exist yet, so this generator produces a synthetic mix of
reliable/unreliable vendor histories to prove the ReputationFact
mechanism, not real vendor outcomes."""

from __future__ import annotations

import random

from .reputation_model import NEGATIVE_EVENT_TYPES, POSITIVE_EVENT_TYPES, ReputationFact


def generate_reputation_facts(vendor_names: list[str], *, seed: int, as_of: str) -> list[ReputationFact]:
    rng = random.Random(seed)
    facts: list[ReputationFact] = []
    for index, vendor_name in enumerate(vendor_names):
        # Deterministic split by input position, not a per-vendor random
        # draw -- keeps reproducibility independent of dict/set ordering.
        # Every third vendor gets an unreliable (negative-only) history;
        # the rest get a reliable (positive-only) one.
        reliable = index % 3 != 0
        event_pool = POSITIVE_EVENT_TYPES if reliable else NEGATIVE_EVENT_TYPES
        fact_count = rng.randint(1, 3)
        for _ in range(fact_count):
            facts.append(
                ReputationFact(
                    data_realm="vendor-sandbox",
                    watermark="SYNTHETIC",
                    vendor_name=vendor_name,
                    event_type=rng.choice(event_pool),
                    project_ref=None,
                    source_ref="synthetic-reputation-generator",
                    observed_at=as_of,
                    ttl_days=rng.choice([30, 90, 180]),
                )
            )
    return facts

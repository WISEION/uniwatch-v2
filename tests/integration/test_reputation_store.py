"""Integration tests for reputation-fact persistence and TTL expiry
(task 3.B, TENDER_INTELLIGENCE_SPEC.md Section6.2). TTL here is a plain
observed_at + ttl_days expiry -- NOT the ownership-aware reset Section6.2
describes ("TTL: обнуляется при смене владельца вендора"), since
packages/vendor has no vendor-ownership concept yet. Recorded as a real
gap in docs/decisions/OPEN-QUESTIONS.md, not implemented as if it were
the same thing."""

from __future__ import annotations

from packages.vendor.reputation_model import ReputationFact
from packages.vendor.reputation_store import list_active_reputation_facts, store_reputation_fact
from packages.vendor.synthetic_reputation import generate_reputation_facts
from packages.vendor.vendor_model import Vendor
from packages.vendor.vendor_store import store_vendor


async def test_a_stored_fact_round_trips(engine):
    vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Rep Vendor", provider_type="synthetic", seed=1)
    fact = ReputationFact(
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        vendor_name="Rep Vendor",
        event_type="missed_deadline",
        project_ref="project-x",
        source_ref="voice-note-2026-08-06",
        observed_at="2026-08-06T00:00:00+00:00",
        ttl_days=90,
    )

    async with engine.begin() as conn:
        vendor_id, _api_key = await store_vendor(conn, vendor)
        await store_reputation_fact(conn, vendor_id, fact)
        active = await list_active_reputation_facts(conn, vendor_id=vendor_id, as_of="2026-08-10T00:00:00+00:00")

    assert len(active) == 1
    assert active[0]["event_type"] == "missed_deadline"
    assert active[0]["project_ref"] == "project-x"
    assert active[0]["source_ref"] == "voice-note-2026-08-06"


async def test_a_fact_past_its_ttl_is_excluded(engine):
    vendor = Vendor(
        data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Stale Rep Vendor", provider_type="synthetic", seed=2
    )
    fact = ReputationFact(
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        vendor_name="Stale Rep Vendor",
        event_type="quality_complaint",
        project_ref=None,
        source_ref="test",
        observed_at="2026-01-01T00:00:00+00:00",
        ttl_days=30,
    )

    async with engine.begin() as conn:
        vendor_id, _api_key = await store_vendor(conn, vendor)
        await store_reputation_fact(conn, vendor_id, fact)
        # 2026-08-06 is far past 2026-01-01 + 30 days.
        active = await list_active_reputation_facts(conn, vendor_id=vendor_id, as_of="2026-08-06T00:00:00+00:00")

    assert active == []


async def test_a_fact_exactly_at_its_ttl_boundary_is_excluded(engine):
    vendor = Vendor(
        data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Boundary Rep Vendor", provider_type="synthetic", seed=3
    )
    fact = ReputationFact(
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        vendor_name="Boundary Rep Vendor",
        event_type="delivered_on_time",
        project_ref=None,
        source_ref="test",
        observed_at="2026-08-01T00:00:00+00:00",
        ttl_days=5,
    )

    async with engine.begin() as conn:
        vendor_id, _api_key = await store_vendor(conn, vendor)
        await store_reputation_fact(conn, vendor_id, fact)
        # observed_at + ttl_days lands exactly on 2026-08-06T00:00:00 --
        # the boundary itself is not "still active" (strict >, not >=).
        active = await list_active_reputation_facts(conn, vendor_id=vendor_id, as_of="2026-08-06T00:00:00+00:00")

    assert active == []


async def test_facts_never_leak_across_vendors(engine):
    facts_by_vendor: dict[str, list[ReputationFact]] = {}
    vendor_names = ["Cross Rep A", "Cross Rep B", "Cross Rep C"]
    generated = generate_reputation_facts(vendor_names, seed=7, as_of="2026-08-06T00:00:00+00:00")
    for name in vendor_names:
        facts_by_vendor[name] = [f for f in generated if f.vendor_name == name]

    async with engine.begin() as conn:
        vendor_ids: dict[str, int] = {}
        for name in vendor_names:
            vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name=name, provider_type="synthetic", seed=1)
            vendor_ids[name], _api_key = await store_vendor(conn, vendor)
        for name, facts in facts_by_vendor.items():
            for fact in facts:
                await store_reputation_fact(conn, vendor_ids[name], fact)

        one_vendor_id = vendor_ids[vendor_names[0]]
        active = await list_active_reputation_facts(conn, vendor_id=one_vendor_id, as_of="2026-08-06T00:00:00+00:00")

    assert all(row["vendor_id"] == one_vendor_id for row in active)

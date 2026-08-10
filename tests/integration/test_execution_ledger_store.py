from __future__ import annotations

from decimal import Decimal

from packages.decision.execution_fact_model import ExecutionFact
from packages.decision.execution_ledger_store import list_execution_facts_by_tender, store_execution_fact
from packages.tender.normalized import get_or_create_tender


def _fact(tender_id: int, **overrides) -> ExecutionFact:
    defaults = dict(
        tender_id=tender_id,
        boqline_source_line_id=501,
        planned_qty=Decimal("10"),
        actual_qty=Decimal("15"),
        deviation_reason="crane did not arrive, half-day idle",
        deviation_category="downtime",
        culprit_type="vendor",
        culprit_vendor_name="Acme Crane Co",
        culprit_vendor_id=42,
        evidence_source="napkin-ocr:1",
        observed_at="2026-08-10T00:00:00+00:00",
    )
    defaults.update(overrides)
    return ExecutionFact(**defaults)


async def test_store_and_list_a_fact(engine):
    async with engine.begin() as conn:
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-store-1")
        fact_id = await store_execution_fact(conn, _fact(tender_id))
        facts = await list_execution_facts_by_tender(conn, tender_id=tender_id)

    assert len(facts) == 1
    assert facts[0]["id"] == fact_id
    assert facts[0]["boqline_source_line_id"] == 501
    assert facts[0]["planned_qty"] == Decimal("10")
    assert facts[0]["actual_qty"] == Decimal("15")
    assert facts[0]["culprit_vendor_id"] == 42


async def test_list_execution_facts_is_scoped_to_the_tender(engine):
    async with engine.begin() as conn:
        tender_a = await get_or_create_tender(conn, source="etender", identity_key="test-4c-store-2a")
        tender_b = await get_or_create_tender(conn, source="etender", identity_key="test-4c-store-2b")
        await store_execution_fact(conn, _fact(tender_a))

        facts_b = await list_execution_facts_by_tender(conn, tender_id=tender_b)
    assert facts_b == []


async def test_a_fact_with_no_boqline_reference_is_allowed(engine):
    # A site-wide observation (e.g. "preliminaries" overhead) is not tied to
    # any one priced BOQ line -- boqline_source_line_id must be nullable.
    async with engine.begin() as conn:
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-store-3")
        await store_execution_fact(
            conn,
            _fact(
                tender_id,
                boqline_source_line_id=None,
                planned_qty=None,
                actual_qty=None,
                culprit_type="internal",
                culprit_vendor_name=None,
                culprit_vendor_id=None,
                deviation_category="preliminaries",
            ),
        )
        facts = await list_execution_facts_by_tender(conn, tender_id=tender_id)
    assert facts[0]["boqline_source_line_id"] is None

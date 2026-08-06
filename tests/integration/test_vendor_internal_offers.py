"""Integration test for GET /internal/offers (task 3.D prep): the Vendor
service's service-to-service endpoint that packages/decision's matching
logic (via packages/contracts) will consume. Deliberately unauthenticated,
same documented gap as GET /internal/ping (docs/decisions/OPEN-QUESTIONS.md)."""

from __future__ import annotations

import httpx

from apps.api_vendor.main import create_app as create_vendor_app
from packages.platform.settings import Settings
from packages.vendor.reputation_model import ReputationFact
from packages.vendor.reputation_store import store_reputation_fact
from packages.vendor.vendor_model import Offer, Vendor
from packages.vendor.vendor_store import store_offer, store_vendor


async def test_internal_offers_reports_positive_reputation_flag(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=11)
    vendor_app = create_vendor_app(settings)
    vendor_app.state.engine = engine

    async with engine.begin() as conn:
        vendor = Vendor(
            data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Reliable Vendor", provider_type="synthetic", seed=1
        )
        vendor_id, _api_key = await store_vendor(conn, vendor)
        offer = Offer(
            vendor_name="Reliable Vendor",
            data_realm="vendor-sandbox",
            watermark="SYNTHETIC",
            material="cement M400",
            price=120.0,
            currency="AZN",
            vat_rate=0.18,
            uom="t",
            uom_canonical_qty=1.0,
            moq=1.0,
            capacity=100.0,
            inventory=40.0,
            valid_from="2026-08-01T00:00:00+00:00",
            valid_until="2026-09-01T00:00:00+00:00",
            evidence_source="test",
            observed_at="2026-08-06T00:00:00+00:00",
            adverse_case=None,
        )
        await store_offer(conn, vendor_id, offer)
        fact = ReputationFact(
            data_realm="vendor-sandbox",
            watermark="SYNTHETIC",
            vendor_name="Reliable Vendor",
            event_type="delivered_on_time",
            project_ref="project-y",
            source_ref="test",
            observed_at="2026-08-01T00:00:00+00:00",
            ttl_days=90,
        )
        await store_reputation_fact(conn, vendor_id, fact)

    transport = httpx.ASGITransport(app=vendor_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        response = await client.get(
            "/internal/offers",
            params={"data_realm": "vendor-sandbox", "as_of": "2026-08-06T00:00:00+00:00"},
        )

    assert response.status_code == 200
    items = response.json()["items"]
    matching = [i for i in items if i["vendor_id"] == vendor_id]
    assert len(matching) == 1
    assert matching[0]["vendor_name"] == "Reliable Vendor"
    assert matching[0]["has_positive_reputation"] is True
    assert matching[0]["has_negative_reputation"] is False


async def test_internal_offers_reports_no_reputation_flags_when_no_facts_exist(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=11)
    vendor_app = create_vendor_app(settings)
    vendor_app.state.engine = engine

    async with engine.begin() as conn:
        vendor = Vendor(
            data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Unknown History Vendor", provider_type="synthetic", seed=2
        )
        vendor_id, _api_key = await store_vendor(conn, vendor)
        offer = Offer(
            vendor_name="Unknown History Vendor",
            data_realm="vendor-sandbox",
            watermark="SYNTHETIC",
            material="cement M400",
            price=115.0,
            currency="AZN",
            vat_rate=0.18,
            uom="t",
            uom_canonical_qty=1.0,
            moq=1.0,
            capacity=80.0,
            inventory=30.0,
            valid_from="2026-08-01T00:00:00+00:00",
            valid_until="2026-09-01T00:00:00+00:00",
            evidence_source="test",
            observed_at="2026-08-06T00:00:00+00:00",
            adverse_case=None,
        )
        await store_offer(conn, vendor_id, offer)

    transport = httpx.ASGITransport(app=vendor_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        response = await client.get(
            "/internal/offers",
            params={"data_realm": "vendor-sandbox", "as_of": "2026-08-06T00:00:00+00:00"},
        )

    items = response.json()["items"]
    matching = [i for i in items if i["vendor_id"] == vendor_id]
    assert matching[0]["has_positive_reputation"] is False
    assert matching[0]["has_negative_reputation"] is False


async def test_internal_offers_reports_negative_reputation_flag(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=11)
    vendor_app = create_vendor_app(settings)
    vendor_app.state.engine = engine

    async with engine.begin() as conn:
        vendor = Vendor(
            data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Unreliable Vendor", provider_type="synthetic", seed=3
        )
        vendor_id, _api_key = await store_vendor(conn, vendor)
        offer = Offer(
            vendor_name="Unreliable Vendor",
            data_realm="vendor-sandbox",
            watermark="SYNTHETIC",
            material="cement M400",
            price=110.0,
            currency="AZN",
            vat_rate=0.18,
            uom="t",
            uom_canonical_qty=1.0,
            moq=1.0,
            capacity=60.0,
            inventory=20.0,
            valid_from="2026-08-01T00:00:00+00:00",
            valid_until="2026-09-01T00:00:00+00:00",
            evidence_source="test",
            observed_at="2026-08-06T00:00:00+00:00",
            adverse_case=None,
        )
        await store_offer(conn, vendor_id, offer)
        fact = ReputationFact(
            data_realm="vendor-sandbox",
            watermark="SYNTHETIC",
            vendor_name="Unreliable Vendor",
            event_type="missed_deadline",
            project_ref="project-z",
            source_ref="test",
            observed_at="2026-08-01T00:00:00+00:00",
            ttl_days=90,
        )
        await store_reputation_fact(conn, vendor_id, fact)

    transport = httpx.ASGITransport(app=vendor_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        response = await client.get(
            "/internal/offers",
            params={"data_realm": "vendor-sandbox", "as_of": "2026-08-06T00:00:00+00:00"},
        )

    items = response.json()["items"]
    matching = [i for i in items if i["vendor_id"] == vendor_id]
    assert matching[0]["has_negative_reputation"] is True
    assert matching[0]["has_positive_reputation"] is False

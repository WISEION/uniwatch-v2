from __future__ import annotations

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api_vendor.main import create_app
from packages.platform.settings import Settings
from packages.vendor.vendor_model import Vendor
from packages.vendor.vendor_store import store_vendor


@pytest_asyncio.fixture
async def app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=16)
    application = create_app(settings)
    application.state.engine = engine
    return application


@pytest_asyncio.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as c:
        yield c


async def test_post_reputation_fact_persists_it(client, engine):
    async with engine.begin() as conn:
        vendor_id, _api_key = await store_vendor(
            conn, Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Acme Crane Co", provider_type="test", seed=1)
        )

    response = await client.post(
        "/internal/reputation-facts",
        json={
            "vendor_id": vendor_id,
            "event_type": "missed_deadline",
            "project_ref": "99",
            "source_ref": "napkin-ocr:1",
            "observed_at": "2026-08-10T00:00:00+00:00",
            "ttl_days": 365,
        },
    )
    assert response.status_code == 201

    async with engine.begin() as conn:
        row = (
            (
                await conn.execute(
                    text("SELECT event_type, project_ref FROM vendor_reputation_facts WHERE vendor_id = :v"),
                    {"v": vendor_id},
                )
            )
            .mappings()
            .one()
        )
    assert row["event_type"] == "missed_deadline"
    assert row["project_ref"] == "99"


async def test_post_reputation_fact_rejects_unknown_event_type(client, engine):
    async with engine.begin() as conn:
        vendor_id, _api_key = await store_vendor(
            conn, Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Beta Co", provider_type="test", seed=2)
        )

    response = await client.post(
        "/internal/reputation-facts",
        json={
            "vendor_id": vendor_id,
            "event_type": "not_a_real_event_type",
            "project_ref": "99",
            "source_ref": "napkin-ocr:1",
            "observed_at": "2026-08-10T00:00:00+00:00",
            "ttl_days": 365,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unknown_event_type"

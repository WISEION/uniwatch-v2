"""End-to-end over real HTTP for task 4.B's one new read route,
`GET /tenders/{tender_id}/recalc-flags`. Follows
tests/integration/test_decision_api.py's exact fixture pattern (tender_app,
client, pm_user, tender_with_boq) rather than reinventing it -- this route
never talks to the Vendor service, so the vendor-app half of that pattern
is not needed here."""

from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api_tender.main import create_app as create_tender_app
from packages.platform.auth.password_hashing import hash_password
from packages.platform.settings import Settings
from packages.tender.boq_line_model import BoqLine
from packages.tender.boq_lines_store import store_boq_lines
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot

RECALC_FLAGS_PERMISSIONS = ("decision.recalc_flags.read",)

# Phase 6 task 6.A (D-IDP): a fixed, arbitrary test password shared by every
# user this file seeds.
TEST_PASSWORD = "test-password-123"


async def _login(client: httpx.AsyncClient, username: str) -> None:
    response = await client.post("/auth/login", json={"username": username, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text


@pytest_asyncio.fixture
async def tender_app(engine, _database_url):
    settings = Settings(database_url=_database_url)
    app = create_tender_app(settings)
    app.state.engine = engine
    return app


@pytest_asyncio.fixture
async def client(tender_app):
    tender_transport = httpx.ASGITransport(app=tender_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=tender_transport, base_url="http://tender-test") as c:
        yield c


@pytest_asyncio.fixture
async def pm_user(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('pm') RETURNING id"))).scalar()
        for perm in RECALC_FLAGS_PERMISSIONS:
            perm_id = (
                await conn.execute(text("INSERT INTO permissions (name) VALUES (:name) RETURNING id"), {"name": perm})
            ).scalar()
            await conn.execute(
                text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
                {"r": role_id, "p": perm_id},
            )
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id, password_hash) VALUES ('pm-1', 'PM One', :r, :ph)"),
            {"r": role_id, "ph": hash_password(TEST_PASSWORD)},
        )
    return "pm-1"


@pytest_asyncio.fixture
async def tender_with_boq(engine):
    line = BoqLine(
        source_line_id=1,
        page_number=1,
        section=None,
        category_code=None,
        description="Supply of rebar-12mm reinforcement steel",
        unit_raw="t",
        unit_canonical="t",
        unit_status="mapped",
        qty=Decimal("10"),
        line_type="normal",
        spec_requirements=(),
        rate=Decimal("850"),
        amount=Decimal("8500"),
    )
    async with engine.begin() as conn:
        raw_snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="event_details",
            identity_key="test-tender-tracking-api-tender",
            raw_body=json.dumps({"eventId": 42}).encode("utf-8"),
            contract_version="v1",
            correlation_id="test-tender-tracking-api",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-tender-tracking-api-tender")
        version = await create_normalized_version(
            conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={"id": 42}
        )
        await store_boq_lines(
            conn, source="etender", event_id=42, tender_version_id=version.id, raw_snapshot_id=raw_snapshot_id, lines=[line]
        )
    return tender_id


async def test_recalc_flags_requires_auth(client, tender_with_boq):
    response = await client.get(f"/tenders/{tender_with_boq}/recalc-flags")
    assert response.status_code == 401


async def test_recalc_flags_returns_empty_list_when_none_flagged(client, pm_user, tender_with_boq):
    await _login(client, pm_user)
    response = await client.get(f"/tenders/{tender_with_boq}/recalc-flags")
    assert response.status_code == 200
    assert response.json() == []


async def test_recalc_flags_returns_a_flag_after_one_is_stored(client, pm_user, tender_with_boq, engine):
    from packages.tender.change_tracking_store import store_boq_line_recalc_flag, store_tender_change_event
    from packages.tender.tender_change_detection import TenderFieldChange

    async with engine.begin() as conn:
        change_event_id = await store_tender_change_event(
            conn,
            tender_id=tender_with_boq,
            change_type="deadline_shift",
            changed_fields=(TenderFieldChange(field="end_date", old_value=1, new_value=2),),
            detected_at="2026-08-09T12:00:00+00:00",
            raw_snapshot_id=1,
        )
        await store_boq_line_recalc_flag(
            conn,
            tender_id=tender_with_boq,
            boqline_source_line_id=1,
            change_event_id=change_event_id,
            flagged_at="2026-08-09T12:00:00+00:00",
        )

    await _login(client, pm_user)
    response = await client.get(f"/tenders/{tender_with_boq}/recalc-flags")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["boqline_source_line_id"] == 1

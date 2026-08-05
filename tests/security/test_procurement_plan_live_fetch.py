"""Real network proof, same precedent as the World Bank and design-tender
slices' live-fetch tests: a live fetch against the real eTender
procurement-plan endpoint through the full validate-then-pinned-connect
egress pipeline. No new host -- etender.gov.az is already used elsewhere
in this suite."""

from __future__ import annotations

import pytest

from packages.platform.egress.registry import promote_to_trusted, register_source
from packages.platform.egress.validator import EgressValidator
from packages.tender.etender_connector import fetch_procurement_plan_page_live


async def _trust(conn, host: str) -> None:
    await register_source(conn, host=host, allowed_schemes=["https"], registered_by="test")
    await promote_to_trusted(conn, host=host, scanner_run_reference="test-scan")


@pytest.mark.live_network
async def test_live_fetch_against_real_etender_procurement_plan_search(engine):
    async with engine.begin() as conn:
        await _trust(conn, "etender.gov.az")
        validator = EgressValidator()
        _raw_body, payload = await fetch_procurement_plan_page_live(
            conn, validator, year=2026, page_number=1, buyer_organization_name="ZAQATALA"
        )
        assert payload["items"]
        assert int(payload["totalItems"]) >= 1

"""Real network proof, same precedent as test_ssrf_suite.py's P304 and the
World Bank slice's test_worldbank_live_fetch.py: a live fetch against the
real eTender search endpoint through the full validate-then-pinned-connect
egress pipeline. No new host -- etender.gov.az is already used elsewhere
in this suite; trust registration here is test-scoped, same pattern."""

from __future__ import annotations

import pytest
from source_fixtures import DESIGN_TENDER_QUERY_PARAMS

from packages.platform.egress.registry import promote_to_trusted, register_source
from packages.platform.egress.validator import EgressValidator
from packages.tender.etender_connector import fetch_design_tender_page_live


async def _trust(conn, host: str) -> None:
    await register_source(conn, host=host, allowed_schemes=["https"], registered_by="test")
    await promote_to_trusted(conn, host=host, scanner_run_reference="test-scan")


@pytest.mark.live_network
async def test_live_fetch_against_real_etender_design_search(engine):
    async with engine.begin() as conn:
        await _trust(conn, "etender.gov.az")
        validator = EgressValidator()
        _raw_body, payload = await fetch_design_tender_page_live(
            conn, validator, query_params=DESIGN_TENDER_QUERY_PARAMS, page_number=1
        )
        assert payload["items"]
        assert int(payload["totalItems"]) >= 1

"""Real network proof, same precedent as test_ssrf_suite.py's P304: a live
fetch against the actual World Bank Projects API through the full
validate-then-pinned-connect egress pipeline. Trust registration here is
test-scoped (scanner_run_reference="test-scan") -- production trust for
this host is a separate, still-open operational decision, same category
as etender.gov.az's own real-scan status (see docs/decisions/OPEN-QUESTIONS.md)."""

from __future__ import annotations

from packages.platform.egress.registry import promote_to_trusted, register_source
from packages.platform.egress.validator import EgressValidator
from packages.tender.worldbank_connector import fetch_donor_pipeline_page_live


async def _trust(conn, host: str, schemes=None) -> None:
    await register_source(conn, host=host, allowed_schemes=schemes or ["https"], registered_by="test")
    await promote_to_trusted(conn, host=host, scanner_run_reference="test-scan")


async def test_live_fetch_against_real_worldbank_api(engine):
    async with engine.begin() as conn:
        await _trust(conn, "search.worldbank.org")
        validator = EgressValidator()
        _raw_body, payload = await fetch_donor_pipeline_page_live(conn, validator, countrycode_exact="AZ", rows=1, os_=0)
        assert payload["projects"]
        assert int(payload["total"]) >= 1

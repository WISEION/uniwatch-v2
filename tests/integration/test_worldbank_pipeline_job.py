"""INV-03, FR-JOB-04, FR-JOB-05, FR-JOB-06, P305: a page fetch failure
resumes the same page, never skips ahead; a schema-drifted page advances
past itself (recorded needs_human) instead of stalling the rest of the
pagination."""

from __future__ import annotations

import json
from pathlib import Path

from packages.platform.jobs import Job
from packages.tender.worldbank_pipeline_job import process_worldbank_pipeline_page

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "worldbank"


def _make_job(checkpoint: dict) -> Job:
    return Job(
        id=1,
        job_type="worldbank_donor_pipeline_page_fetch",
        params={"countrycode_exact": "AZ", "rows": 10},
        source="worldbank_projects_api",
        range_start=None,
        range_end=None,
        contract_version="worldbank.donor_pipeline_page",
        correlation_id="corr-wb-job-1",
        status="running",
        lease_owner="test-worker",
        attempt=1,
        max_attempts=5,
        checkpoint=checkpoint,
        last_error=None,
    )


async def test_page_fetch_failure_resumes_same_page_not_next(engine):
    real_page_os0 = json.loads((FIXTURES / "az_donor_pipeline_page_os0.raw.json").read_bytes())
    real_page_os10 = json.loads((FIXTURES / "az_donor_pipeline_page_os10.raw.json").read_bytes())
    attempts = []

    async def fetch_page(countrycode, rows, os_):
        attempts.append(os_)
        if os_ == 0 and attempts.count(0) == 1:
            raise ConnectionError("simulated transient failure on first page")
        raw = (FIXTURES / f"az_donor_pipeline_page_os{os_}.raw.json").read_bytes()
        return raw, json.loads(raw)

    async with engine.begin() as conn:
        job = _make_job(checkpoint={})
        try:
            await process_worldbank_pipeline_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
            raised = False
        except ConnectionError:
            raised = True
        assert raised
        assert attempts == [0]

        # Retry: same job identity, checkpoint never advanced past the failure.
        job = _make_job(checkpoint={})
        result = await process_worldbank_pipeline_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_os"] == 10
        assert not result["done"]  # total=79, next_os=10 < 79
        assert len(result["signal_ids"]) == len(real_page_os0["projects"])

        # Next page.
        job = _make_job(checkpoint={"next_os": 10})
        result = await process_worldbank_pipeline_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_os"] == 20
        assert len(result["signal_ids"]) == len(real_page_os10["projects"])

        assert attempts == [0, 0, 10]  # first page fetched twice (failed, then succeeded), never skipped to os=10 early


async def test_schema_drift_on_one_page_does_not_stall_pagination(engine):
    real_page_os0 = json.loads((FIXTURES / "az_donor_pipeline_page_os0.raw.json").read_bytes())
    drifted_page_os0 = {**real_page_os0, "unexpected_new_field": "drift"}

    async def fetch_page(countrycode, rows, os_):
        if os_ == 0:
            return json.dumps(drifted_page_os0).encode(), drifted_page_os0
        raw = (FIXTURES / f"az_donor_pipeline_page_os{os_}.raw.json").read_bytes()
        return raw, json.loads(raw)

    async with engine.begin() as conn:
        job = _make_job(checkpoint={})
        result = await process_worldbank_pipeline_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_os"] == 10  # advanced past the drifted page, did not stall
        assert result["signal_ids"] == []
        assert result["exception_queue_id"] is not None

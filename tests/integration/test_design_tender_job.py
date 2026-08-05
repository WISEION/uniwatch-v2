"""INV-03, FR-JOB-04, FR-JOB-05, FR-JOB-06, P305: a page fetch failure
resumes the same page, never skips ahead; a schema-drifted page advances
past itself (recorded needs_human) instead of stalling the rest of the
pagination."""

from __future__ import annotations

import json

from source_fixtures import DESIGN_TENDER_QUERY_PARAMS, ETENDER_FIXTURES

from packages.platform.jobs import Job
from packages.tender.design_tender_job import process_design_tender_page


def _make_job(checkpoint: dict) -> Job:
    return Job(
        id=1,
        job_type="etender_design_tender_page_fetch",
        params={"query_params": DESIGN_TENDER_QUERY_PARAMS},
        source="etender",
        range_start=None,
        range_end=None,
        contract_version="etender.events_list_page",
        correlation_id="corr-design-job-1",
        status="running",
        lease_owner="test-worker",
        attempt=1,
        max_attempts=5,
        checkpoint=checkpoint,
        last_error=None,
    )


async def test_page_fetch_failure_resumes_same_page_not_next(engine):
    real_page1 = json.loads((ETENDER_FIXTURES / "design_tender_search_page1.raw.json").read_bytes())
    attempts = []

    async def fetch_page(query_params, page_number):
        attempts.append(page_number)
        if page_number == 1 and attempts.count(1) == 1:
            raise ConnectionError("simulated transient failure on first page")
        raw = (ETENDER_FIXTURES / f"design_tender_search_page{page_number}.raw.json").read_bytes()
        return raw, json.loads(raw)

    async with engine.begin() as conn:
        job = _make_job(checkpoint={})
        try:
            await process_design_tender_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
            raised = False
        except ConnectionError:
            raised = True
        assert raised
        assert attempts == [1]

        job = _make_job(checkpoint={})
        result = await process_design_tender_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_page"] == 2
        assert not result["done"]  # totalPages=15, page 1 of 15
        assert len(result["signal_ids"]) == len(real_page1["items"])

        job = _make_job(checkpoint={"next_page": 2})
        result = await process_design_tender_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_page"] == 3
        assert len(result["signal_ids"]) == 6  # 4 real true negatives on this page correctly excluded

        assert attempts == [1, 1, 2]  # page 1 fetched twice (failed, then succeeded), never skipped to page 2 early


async def test_schema_drift_on_one_page_does_not_stall_pagination(engine):
    real_page1 = json.loads((ETENDER_FIXTURES / "design_tender_search_page1.raw.json").read_bytes())
    drifted_page1 = {**real_page1, "unexpected_new_field": "drift"}

    async def fetch_page(query_params, page_number):
        if page_number == 1:
            return json.dumps(drifted_page1).encode(), drifted_page1
        raw = (ETENDER_FIXTURES / f"design_tender_search_page{page_number}.raw.json").read_bytes()
        return raw, json.loads(raw)

    async with engine.begin() as conn:
        job = _make_job(checkpoint={})
        result = await process_design_tender_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_page"] == 2  # advanced past the drifted page, did not stall
        assert result["signal_ids"] == []
        assert result["exception_queue_id"] is not None

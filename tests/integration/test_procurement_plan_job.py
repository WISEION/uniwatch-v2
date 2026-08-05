"""INV-03, FR-JOB-04, FR-JOB-05, FR-JOB-06, P305: a page fetch failure
resumes the same page, never skips ahead; a schema-drifted page advances
past itself (recorded needs_human) instead of stalling the rest of the
pagination."""

from __future__ import annotations

import json

from source_fixtures import ETENDER_FIXTURES

from packages.platform.jobs import Job
from packages.tender.procurement_plan_job import process_procurement_plan_page


def _make_job(checkpoint: dict) -> Job:
    return Job(
        id=1,
        job_type="etender_procurement_plan_page_fetch",
        params={"year": 2026, "buyer_organization_name": "ZAQATALA"},
        source="etender",
        range_start=None,
        range_end=None,
        contract_version="etender.app_list_page",
        correlation_id="corr-app-job-1",
        status="running",
        lease_owner="test-worker",
        attempt=1,
        max_attempts=5,
        checkpoint=checkpoint,
        last_error=None,
    )


async def test_page_fetch_failure_resumes_same_page_not_next(engine):
    real_page = json.loads((ETENDER_FIXTURES / "app_list_zaqatala_2026.raw.json").read_bytes())
    attempts = []

    async def fetch_page(year, page_number, buyer_organization_name):
        attempts.append(page_number)
        if page_number == 1 and attempts.count(1) == 1:
            raise ConnectionError("simulated transient failure")
        raw = (ETENDER_FIXTURES / "app_list_zaqatala_2026.raw.json").read_bytes()
        return raw, json.loads(raw)

    async with engine.begin() as conn:
        job = _make_job(checkpoint={})
        try:
            await process_procurement_plan_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
            raised = False
        except ConnectionError:
            raised = True
        assert raised
        assert attempts == [1]

        job = _make_job(checkpoint={})
        result = await process_procurement_plan_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_page"] == 2
        assert not result["done"]  # totalItems=33, pageSize=10 -> totalPages=4
        assert len(result["signal_ids"]) == len(real_page["items"])
        assert attempts == [1, 1]


async def test_schema_drift_on_one_page_does_not_stall_pagination(engine):
    real_page = json.loads((ETENDER_FIXTURES / "app_list_zaqatala_2026.raw.json").read_bytes())
    drifted_page = {**real_page, "unexpected_new_field": "drift"}

    async def fetch_page(year, page_number, buyer_organization_name):
        if page_number == 1:
            return json.dumps(drifted_page).encode(), drifted_page
        raw = (ETENDER_FIXTURES / "app_list_zaqatala_2026.raw.json").read_bytes()
        return raw, json.loads(raw)

    async with engine.begin() as conn:
        job = _make_job(checkpoint={})
        result = await process_procurement_plan_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_page"] == 2  # advanced past the drifted page, did not stall
        assert result["signal_ids"] == []
        assert result["exception_queue_id"] is not None

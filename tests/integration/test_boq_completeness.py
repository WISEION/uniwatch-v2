"""FR-DQ-01, FR-DQ-02, FR-TND-04, INV-04, P001: BOQ is `complete` only after
proven page/row reconciliation; absence of a source total is
`source_exhausted_unverified`, never `complete`; a stalled import lists its
exact missing pages instead of looking ambiguously unfinished."""

from __future__ import annotations

import json
from pathlib import Path

from packages.tender.boq_completeness import (
    get_or_create_boq_import,
    mark_import_stalled,
    record_page_fetched,
)
from packages.tender.raw_snapshot import checksum_of

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_bytes())


async def test_real_pages_accumulate_counts_and_stay_in_progress(engine):
    # 3 real pages of a real 42-page BOQ -- correctly NOT complete, no
    # fabricated totals needed to prove this.
    async with engine.begin() as conn:
        status = None
        for n in (1, 2, 3):
            payload = _load(f"event_355920_bomlines_page{n}.raw.json")
            raw_body = (FIXTURES / f"event_355920_bomlines_page{n}.raw.json").read_bytes()
            status = await record_page_fetched(
                conn,
                source="etender",
                event_id=355920,
                page_number=n,
                lines_on_page=payload["itemsInPage"],
                expected_total=payload["totalItems"],
                expected_pages=payload["totalPages"],
                page_checksum=checksum_of(raw_body),
            )

    assert status.fetched_pages == 3
    assert status.stored_lines == 300  # 100 items/page x 3 real pages
    assert status.expected_total == 4135
    assert status.expected_pages == 42
    assert status.status == "in_progress"
    assert status.page_checksums["1"] == checksum_of((FIXTURES / "event_355920_bomlines_page1.raw.json").read_bytes())


async def test_status_becomes_complete_when_reconciliation_proven(engine):
    async with engine.begin() as conn:
        await record_page_fetched(
            conn,
            source="etender",
            event_id=999001,
            page_number=1,
            lines_on_page=2,
            expected_total=2,
            expected_pages=1,
            page_checksum="deadbeef",
        )
        status = await get_or_create_boq_import(conn, source="etender", event_id=999001)

    assert status.status == "complete"
    assert status.fetched_pages == 1
    assert status.stored_lines == 2


async def test_status_is_source_exhausted_unverified_when_no_total_reported(engine):
    async with engine.begin() as conn:
        status = await record_page_fetched(
            conn,
            source="etender",
            event_id=999002,
            page_number=1,
            lines_on_page=5,
            expected_total=None,
            expected_pages=None,
            page_checksum="deadbeef",
        )

    assert status.status == "source_exhausted_unverified"


async def test_stalled_import_lists_exact_missing_pages_not_marked_complete(engine):
    async with engine.begin() as conn:
        # 5 expected pages, only page 1 and page 3 ever fetched before the
        # job gave up (terminal failure/cancel).
        await record_page_fetched(
            conn,
            source="etender",
            event_id=999003,
            page_number=1,
            lines_on_page=10,
            expected_total=50,
            expected_pages=5,
            page_checksum="p1",
        )
        await record_page_fetched(
            conn,
            source="etender",
            event_id=999003,
            page_number=3,
            lines_on_page=10,
            expected_total=50,
            expected_pages=5,
            page_checksum="p3",
        )
        status = await mark_import_stalled(conn, source="etender", event_id=999003)

    assert status.status == "incomplete"
    assert status.missing_pages == [2, 4, 5]
    assert status.status != "complete"

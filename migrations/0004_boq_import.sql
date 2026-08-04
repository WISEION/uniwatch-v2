-- BOQ completeness contract (FR-DQ-01, FR-DQ-02, FR-TND-04, INV-04, P001):
-- a BOQ is `complete` only after every expected page has been fetched and
-- the summed line count matches the source's own claimed total. Absence of
-- a source-provided total is `source_exhausted_unverified`, never
-- `complete` -- there is no ground truth to reconcile against in that case.

CREATE TABLE boq_import (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    event_id BIGINT NOT NULL,
    expected_total INTEGER,
    expected_pages INTEGER,
    fetched_pages INTEGER NOT NULL DEFAULT 0,
    stored_lines INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'complete', 'incomplete', 'source_exhausted_unverified')),
    missing_pages JSONB NOT NULL DEFAULT '[]'::jsonb,
    -- page_number (as text key) -> raw_snapshot checksum for that page,
    -- the "checksum per page" proof the plan requires.
    page_checksums JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, event_id)
);

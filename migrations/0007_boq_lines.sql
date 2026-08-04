-- Atomic BOQ line rows (FR-TND-*, TENDER_INTELLIGENCE_SPEC.md §5.1, P308):
-- one row per source BOQ item, with unit canonicalization status, line-type
-- classification, and extracted hidden spec requirements attached. A page
-- that fails item-level schema drift never reaches this table (see
-- etender_connector.py) -- there is no partial/guessed row for a page whose
-- item shape the connector doesn't recognize.

CREATE TABLE boq_lines (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    event_id BIGINT NOT NULL,
    page_number INTEGER NOT NULL,
    tender_version_id BIGINT NOT NULL REFERENCES tender_versions (id),
    raw_snapshot_id BIGINT NOT NULL REFERENCES raw_snapshots (id),
    source_line_id BIGINT NOT NULL,
    section TEXT,
    category_code TEXT,
    description TEXT NOT NULL,
    unit_raw TEXT NOT NULL,
    unit_canonical TEXT,
    unit_status TEXT NOT NULL CHECK (unit_status IN ('mapped', 'unmapped')),
    qty NUMERIC NOT NULL,
    line_type TEXT NOT NULL DEFAULT 'normal'
        CHECK (line_type IN ('normal', 'preliminaries', 'provisional_sum', 'prime_cost')),
    spec_requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
    rate NUMERIC,
    amount NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, event_id, source_line_id)
);

CREATE INDEX boq_lines_event_idx ON boq_lines (source, event_id);

-- Signal facts (INV-15, INV-16, INV-17, TENDER_INTELLIGENCE_SPEC.md §5.2, P309):
-- append-only atoms, never updated in place -- a re-observation of the same
-- underlying real-world fact is a new row, matching raw_snapshots' own
-- append-only design. object_customer/object_region/object_project_type are
-- a minimal binding (INV-15 "not floating unattached"), not the full object
-- graph (that is task 2.C).

CREATE TABLE signals (
    id BIGSERIAL PRIMARY KEY,
    signal_type TEXT NOT NULL,
    source TEXT NOT NULL,
    raw_snapshot_id BIGINT NOT NULL REFERENCES raw_snapshots (id),
    value JSONB NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    -- INV-17: a TTL *class* label (e.g. 'funding_decision'), never a
    -- resolved duration or expiry -- exact numbers are TBD-TIS-01.
    ttl_class TEXT NOT NULL,
    -- INV-15: a qualitative provenance tier (e.g. 'official_source'),
    -- fixed per connector -- never a calibrated forecast probability
    -- (that is TBD-TIS-02 / task 2.C, built from multiple signals).
    confidence TEXT NOT NULL,
    object_customer TEXT,
    object_region TEXT,
    object_project_type TEXT,
    correlation_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX signals_type_observed_idx ON signals (signal_type, observed_at);
CREATE INDEX signals_object_idx ON signals (object_customer, object_region, object_project_type);

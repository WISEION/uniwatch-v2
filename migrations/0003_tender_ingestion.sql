-- Tender ingestion: raw snapshots (DM-02/DM-03), tender identity anchor, and
-- normalized immutable versions (FR-TND-02, P108).
-- FR-TND-02, FR-TND-10, INT-01, INT-02, DM-02, DM-03, P108

CREATE TABLE raw_snapshots (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    identity_key TEXT NOT NULL,
    checksum TEXT NOT NULL,
    body JSONB NOT NULL,
    contract_version TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A re-fetch always inserts a new row (DM-02) — application code never issues
-- an UPDATE against this table; there is no key to upsert on, by design.
CREATE INDEX raw_snapshots_lookup_idx ON raw_snapshots (source, resource_type, identity_key, fetched_at);

-- One authoritative identity per (source, identity_key) — DM-01.
CREATE TABLE tenders (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    identity_key TEXT NOT NULL,
    current_version_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, identity_key)
);

CREATE TABLE tender_versions (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    version_number INTEGER NOT NULL,
    raw_snapshot_id BIGINT NOT NULL REFERENCES raw_snapshots (id),
    parser_version TEXT NOT NULL,
    normalized_fields JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tender_id, version_number)
);

ALTER TABLE tenders
    ADD CONSTRAINT tenders_current_version_fk
    FOREIGN KEY (current_version_id) REFERENCES tender_versions (id);

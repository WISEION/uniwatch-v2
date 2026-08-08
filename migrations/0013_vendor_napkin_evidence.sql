-- Vendor napkin-ingestion raw evidence (TENDER_INTELLIGENCE_SPEC.md §6.1,
-- task 3.A, P312/P313, INV-18): the exact captured bytes behind a
-- photo-of-a-price-list (and, once an ASR tech choice is made -- still
-- open, see docs/decisions/OPEN-QUESTIONS.md -- a voice note). Same
-- DM-02/DM-03 immutability discipline as packages/tender/raw_snapshot.py's
-- raw_snapshots table: a re-capture always inserts a new row, checksum is
-- sha256 of the exact raw bytes, and this table is never UPDATEd.
--
-- A separate table, not a reuse of raw_snapshots: packages/vendor must
-- never import from packages/tender (ADR-0001 domain boundary), and the
-- payload shape differs fundamentally (raw binary bytes here vs. JSON
-- there) -- BYTEA, not JSONB.

CREATE TABLE vendor_napkin_evidence (
    id BIGSERIAL PRIMARY KEY,
    capture_kind TEXT NOT NULL CHECK (capture_kind IN ('photo', 'voice')),
    mime_type TEXT NOT NULL,
    checksum TEXT NOT NULL,
    raw_bytes BYTEA NOT NULL,
    correlation_id TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A re-capture always inserts a new row (DM-02) -- application code never
-- issues an UPDATE against this table.
CREATE INDEX vendor_napkin_evidence_checksum_idx ON vendor_napkin_evidence (checksum);

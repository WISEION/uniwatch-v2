-- Execution Ledger (Phase 4, task 4.C, TENDER_INTELLIGENCE_SPEC.md Section7.3,
-- INV-18, P318): plan-vs-fact reality from the construction site for an
-- already-decided tender. execution_napkin_evidence and execution_facts are
-- both append-only (ADR-0003 layers 1/2-3) -- application code never issues
-- an UPDATE/DELETE against either.
--
-- "Project" == the tender itself (no separate Project entity exists or is
-- invented here) -- tender_id is Section8's проект_ref.

-- Raw immutable napkin-ingestion evidence, scoped to one tender (unlike
-- vendor_napkin_evidence, which isn't tied to any one tender). A separate
-- table from vendor_napkin_evidence: packages/decision must never share a
-- table with packages/vendor across the ADR-0001 domain boundary, and this
-- capture is inherently project-scoped from the moment it's taken.
CREATE TABLE execution_napkin_evidence (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    capture_kind TEXT NOT NULL CHECK (capture_kind IN ('photo', 'voice')),
    mime_type TEXT NOT NULL,
    checksum TEXT NOT NULL,
    raw_bytes BYTEA NOT NULL,
    correlation_id TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX execution_napkin_evidence_tender_idx ON execution_napkin_evidence (tender_id);
CREATE INDEX execution_napkin_evidence_checksum_idx ON execution_napkin_evidence (checksum);

-- One atom: project -> position -> plan vs fact -> deviation reason ->
-- culprit -> date (Section7.3's own atom list). boqline_source_line_id is
-- nullable: a site-wide observation (e.g. preliminaries overhead) is not
-- tied to any one priced BOQ line. planned_qty/actual_qty are nullable for
-- the same reason -- not every deviation is a clean quantity comparison
-- (e.g. a pure downtime narrative has no qty at all).
CREATE TABLE execution_facts (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    boqline_source_line_id BIGINT,
    planned_qty NUMERIC,
    actual_qty NUMERIC,
    deviation_reason TEXT NOT NULL,
    deviation_category TEXT CHECK (deviation_category IN ('preliminaries', 'downtime', 'rework', 'last_mile')),
    culprit_type TEXT NOT NULL CHECK (culprit_type IN ('vendor', 'customer', 'internal', 'external')),
    culprit_vendor_name TEXT,
    culprit_vendor_id BIGINT,
    evidence_source TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX execution_facts_tender_idx ON execution_facts (tender_id);

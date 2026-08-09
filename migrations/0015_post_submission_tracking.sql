-- Post-submission tracking (Phase 4, task 4.B, TENDER_INTELLIGENCE_SPEC.md
-- §7.2, P317): once a tender has a Bid/Conditional Bid decision, a
-- recurring worker job (packages/tender/post_submission_tracking_job.py)
-- re-checks it on eTender for deadline shifts and document/BOQ changes.
-- tender_change_events and boq_line_recalc_flags are both append-only
-- (ADR-0003 layer 3: derived signal) -- application code never issues an
-- UPDATE/DELETE against either. tender_watch_state is the one mutable
-- table here: a per-tender operational high-water-mark, not a fact or a
-- human decision.

CREATE TABLE tender_change_events (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    change_type TEXT NOT NULL CHECK (change_type IN ('deadline_shift', 'document_changed')),
    changed_fields JSONB NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL,
    raw_snapshot_id BIGINT NOT NULL REFERENCES raw_snapshots (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX tender_change_events_tender_idx ON tender_change_events (tender_id);

-- P317: "the affected BOQ lines are marked as needing recalculation".
-- resolved_at stays NULL until something explicitly resolves it -- this
-- migration does not decide who/what does that (docs/decisions/OPEN-QUESTIONS.md).
CREATE TABLE boq_line_recalc_flags (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    boqline_source_line_id BIGINT NOT NULL,
    change_event_id BIGINT NOT NULL REFERENCES tender_change_events (id),
    flagged_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX boq_line_recalc_flags_tender_idx ON boq_line_recalc_flags (tender_id) WHERE resolved_at IS NULL;

-- One row per tracked tender; last_checked_at is the poll job's own
-- high-water-mark (packages/tender/change_tracking_store.py's
-- upsert_watch_state), not a fact about the tender itself.
CREATE TABLE tender_watch_state (
    tender_id BIGINT PRIMARY KEY REFERENCES tenders (id),
    last_checked_at TIMESTAMPTZ NOT NULL
);

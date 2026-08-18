-- Pilot feedback queue (Phase 6, task 6.D, master plan section18 Phase 6's
-- "training materials and feedback queue for pilot users" result). Durable
-- submission log -- a submitter's message is never edited or deleted, only
-- its triage status changes (open -> resolved), same append-only-history
-- discipline as exception_queue/audit_log. submitted_by/resolved_by are
-- plain username snapshots (matches audit_log.actor's own convention),
-- not a users FK, so a later-disabled user's feedback history stays
-- readable without a join.
CREATE TABLE pilot_feedback (
    id BIGSERIAL PRIMARY KEY,
    submitted_by TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('bug', 'question', 'feature_request', 'other')),
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    resolution_note TEXT,
    resolved_by TEXT,
    correlation_id TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX pilot_feedback_status_idx ON pilot_feedback (status, submitted_at DESC);

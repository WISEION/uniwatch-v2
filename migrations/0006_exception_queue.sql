-- Exception queue (FR-JOB-08): unrecoverable/unhandled items are never
-- lost silently -- schema drift, egress blocks, stale facts, unrecognized
-- artifacts all land here with a reason and (where available) a raw
-- evidence reference. `retryable` items get automatic backoff; `needs_human`
-- items wait for a human action (or an automated contract fix) to close them.

CREATE TABLE exception_queue (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    exception_type TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('retryable', 'needs_human')),
    raw_ref BIGINT REFERENCES raw_snapshots (id),
    contract_name TEXT,
    reason TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed')),
    closed_at TIMESTAMPTZ,
    closed_reason TEXT,
    closed_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Dedup key for "the same recurring problem" -- a retry of the same job's
-- same page/resource bumps `attempts` on the existing open row rather than
-- creating a new one every attempt.
CREATE INDEX exception_queue_dedup_idx ON exception_queue (source, exception_type, correlation_id, status);

-- Lets a contract fix close every open needs_human row that names it, in
-- one statement (P307).
CREATE INDEX exception_queue_contract_idx ON exception_queue (contract_name, category, status);

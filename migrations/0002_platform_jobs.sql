-- Durable worker jobs + transactional outbox.
-- FR-JOB-01..08

CREATE TABLE jobs (
    id BIGSERIAL PRIMARY KEY,
    job_type TEXT NOT NULL,
    params JSONB NOT NULL DEFAULT '{}'::jsonb,
    source TEXT NOT NULL,
    range_start TEXT,
    range_end TEXT,
    contract_version TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'leased', 'completed', 'failed', 'cancelled')),
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    attempt INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    next_retry_at TIMESTAMPTZ,
    checkpoint JSONB NOT NULL DEFAULT '{}'::jsonb,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A cursor belongs to exactly one job identity (type/params/source/range/
-- contract version) — FR-JOB-02, P002. Enforced at the application layer by
-- always deriving a fresh job (and therefore a fresh checkpoint) for any new
-- filter/range rather than reusing another job's row.
CREATE INDEX jobs_claimable_idx ON jobs (status, next_retry_at);

-- Transactional outbox (FR-JOB-07): a row is inserted in the same DB
-- transaction as the effect it describes. The publisher delivers
-- at-least-once and is safe to re-run because `published_at` is only ever
-- set once, by the publisher itself.
CREATE TABLE outbox (
    id BIGSERIAL PRIMARY KEY,
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    correlation_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'published'))
);

CREATE INDEX outbox_pending_idx ON outbox (status, created_at);

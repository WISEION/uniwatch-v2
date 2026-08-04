-- Trusted source registry (NFR-SEC-03, threat model T2,
-- docs/architecture/egress-validator-contract.md §1): a host must be
-- explicitly registered and promoted to 'trusted' by an actual scanner run
-- before any outbound request is permitted to it. Never 'trusted' on
-- creation.

CREATE TABLE trusted_sources (
    id BIGSERIAL PRIMARY KEY,
    host TEXT NOT NULL UNIQUE,
    allowed_schemes TEXT[] NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending_scan'
        CHECK (status IN ('pending_scan', 'trusted', 'revoked')),
    scanner_run_reference TEXT,
    registered_by TEXT NOT NULL,
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    promoted_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoked_reason TEXT
);

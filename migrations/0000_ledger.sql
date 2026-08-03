-- Bootstrap migration: creates the ledger itself.
-- Requirements: FR-PLT-12, DM-06.
-- This is the only migration ever applied by anything other than the (future, 0.B) migration
-- runner's bootstrap path: before this table exists, there is no ledger to check against.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version           INTEGER PRIMARY KEY,
    description       TEXT NOT NULL,
    checksum          TEXT NOT NULL,
    applied_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    applied_by        TEXT NOT NULL,
    preflight_status  TEXT NOT NULL CHECK (preflight_status IN ('passed', 'failed', 'skipped')),
    postflight_status TEXT NOT NULL CHECK (postflight_status IN ('passed', 'failed', 'skipped'))
);

-- A migration is only considered successfully applied when both preflight and postflight
-- are 'passed'. A runner MUST refuse to record a row with postflight_status = 'failed' as
-- the current version for startup's schema-version check (FR-PLT-12 rule 2).

INSERT INTO schema_migrations (version, description, checksum, applied_by, preflight_status, postflight_status)
VALUES (0, 'ledger bootstrap', 'n/a', 'bootstrap', 'skipped', 'skipped')
ON CONFLICT (version) DO NOTHING;

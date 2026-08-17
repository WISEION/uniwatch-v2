-- Restore-drill evidence (Phase 6, task 6.C, NFR-REL-01 / master plan
-- §23.1's "backup age / restore drill age" line). docs/operations/runbook.md
-- step 3 already requires a restore drill to be "performed and logged" --
-- this is the first table that lets that actually be true. Append-only,
-- same discipline as deployment_authorizations/audit_log: a bad drill
-- result is not corrected by editing this row, only by running and
-- recording a new drill.
CREATE TABLE restore_drill_runs (
    id BIGSERIAL PRIMARY KEY,
    backup_filename TEXT NOT NULL,
    target_database TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    detail TEXT NOT NULL,
    drilled_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX restore_drill_runs_drilled_at_idx ON restore_drill_runs (drilled_at DESC, id DESC);

-- Deployment authorization (Phase 6, task 6.B, Gate 4 -- FR-AUT-06/INV-14,
-- docs/adr/0005-authority-model.md). This is the first mechanical record of
-- "production deployment requires a distinct approver from the initiator" --
-- previously purely a human/WORKLOG.md convention with zero enforcement.
--
-- Append-only, same disable-not-delete-family discipline as audit_log/
-- user_sessions: no update/delete function exists in
-- packages/platform/deployment_authorization.py for this table. A wrong
-- authorization is not corrected by editing this row -- it stays as
-- evidence of what was actually checked at the time.
CREATE TABLE deployment_authorizations (
    id BIGSERIAL PRIMARY KEY,
    commit_sha TEXT NOT NULL,
    image_digests JSONB NOT NULL,
    initiator TEXT NOT NULL,
    approver TEXT NOT NULL,
    db_schema_version_at_authorization INTEGER NOT NULL,
    authorized_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes TEXT
);

CREATE INDEX deployment_authorizations_commit_sha_idx ON deployment_authorizations (commit_sha);

-- Local auth (Phase 6, task 6.A -- D-IDP: lightweight local auth over the
-- existing users/roles/role_permissions tables, resolved 2026-08-14; not
-- Entra/OIDC, no break-glass -- the pilot is not internet-facing).
--
-- password_hash is nullable: existing/dev-only rows have none until a
-- password is explicitly set via a separate admin action (set-password is
-- not part of user creation -- FR-ADM-04's own "capability is separate from
-- creation" shape). failed_login_count/locked_until implement account
-- lockout structurally; the exact threshold/duration is an implementation
-- detail (recorded in docs/decisions/OPEN-QUESTIONS.md), not a PRD number.
ALTER TABLE users
    ADD COLUMN password_hash TEXT,
    ADD COLUMN failed_login_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN locked_until TIMESTAMPTZ;

-- Sessions are revoked, never deleted (same disable-not-delete discipline
-- packages/platform/audit.py already applies to users) -- a revoked session
-- remains visible to a future audit/session-history query rather than
-- disappearing. id is an opaque random token (secrets.token_urlsafe), not a
-- sequential identifier -- it is the bearer credential itself, handed to the
-- browser as a cookie value.
CREATE TABLE user_sessions (
    id TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE INDEX user_sessions_user_id_idx ON user_sessions (user_id);

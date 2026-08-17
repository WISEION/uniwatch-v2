# Runbook: suspected credential/PII incident

**Trigger:** suspicion that a user credential (password hash, session
token) or personally-identifiable data was exposed, guessed, or accessed
outside normal authorized use.

## Response (mechanical steps only — this repo has no legal/compliance process to invent)

1. **Revoke the affected session(s) immediately**: `packages/platform/auth/session_store.py::revoke_session` for any specific session, or disable the account entirely via `apps/api_tender/routers/admin_users.py`'s disable endpoint (`packages/platform/audit.py::disable_user` — disable-not-delete, so the account's history remains for investigation).
2. **Force a password reset**: `admin_users.py`'s `POST /{id}/set-password` is the only way to set a password in this system — use it to set a new, operator-chosen password the affected user must then change; there is no self-service "forgot password" flow to fall back on.
3. **Check `failed_login_count`/`locked_until`** on the affected user row for evidence of a brute-force attempt (`migrations/0021_algoritm_local_auth.sql`'s lockout columns) — a pattern of failures just before the suspected incident is a real signal, not proof, of how access was obtained.
4. **Review the audit trail**: every admin action is appended to the audit log (`packages/platform/audit.py`) rather than mutating history — pull every audit entry for the affected account/actor around the suspected window.
5. **Note the cookie's TLS gap**: `apps/api_tender/routers/auth.py`'s session cookie is httpOnly but explicitly without `Secure` (TLS is out of scope for this pilot per `docs/decisions/OPEN-QUESTIONS.md`'s 2026-08-15/16 entry) — if the suspected incident involves network interception rather than credential guessing/reuse, this is the most likely vector and is a known, previously-recorded gap, not a new one to silently patch here.
6. Record the incident, response, and outcome in `docs/reports/WORKLOG.md`.

## Do not

- Do not attempt to fabricate a formal legal/compliance breach-notification process here — no such process is defined anywhere in this project's source documents (`AGENTS.md` §1), and inventing one would itself violate hard ban #2's spirit (don't substitute an invented answer for a genuinely open decision).

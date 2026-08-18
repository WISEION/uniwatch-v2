# Pilot user onboarding (Phase 6, task 6.D)

D-PILOT's decision (`docs/decisions/OPEN-QUESTIONS.md`, 2026-08-17/18): 12 pilot
users across 4 roles, provisioned by `scripts/seed_pilot_users.py`. This
document is what a pilot user needs to get started, and what an operator
needs to onboard them for real.

## For operators: assigning a real person to a pilot slot

`scripts/seed_pilot_users.py` created 12 placeholder accounts
(`pilot_<role>_<n>`), each with a freshly generated password printed once
at seed time and handed to whoever ran the script. To assign a real person:

1. Give them their placeholder username and the password from that one-time
   printout (not recoverable any other way — if lost, use
   `PATCH /admin/users/{id}/password` via a `technical_specialist` account
   to set a new one).
2. Tell them to sign in at the web app's URL and change nothing about their
   username — `PATCH /admin/users/{id}` can update `display_name` to their
   real name, but the endpoint does not support renaming `username` itself.
3. Point them at "For pilot users" below.

## For pilot users: what you can do and how to log in

1. Open the app in a browser, enter the API base URL if it isn't already
   filled in (ask your operator if unsure), and sign in with the username
   and password you were given.
2. What you can do depends on your role:

| Role | You can |
|---|---|
| **worker** | View bid-readiness/forecast/recalc-flag data; log and view execution facts; submit feedback |
| **tender** | Everything `worker` can, plus create Bid/No-Bid decisions and Go/No-Go entries, read/write forecast snapshots |
| **procurement** | View/log execution facts, close out projects, read/write decision outcomes; submit feedback |
| **technical_specialist** | Manage the policy graph (АЛГОРИТМ: view/edit/approve/activate, run simulations), manage user accounts, triage feedback |

If something looks like it should work but doesn't, that's not necessarily
a mistake on your part — this is a pilot. See "Reporting a problem" below.

## Reporting a problem or asking a question

Every signed-in pilot user can submit feedback directly in the app (the
"Send feedback" form, always visible once you're signed in) — pick a
category (`bug`, `question`, `feature_request`, `other`) and describe what
happened. This goes into a real, durable queue
(`packages/platform/pilot_feedback.py`) that a `technical_specialist`
reviews — there is no separate email/chat channel for pilot feedback today.

**Known limitation:** triage (reviewing and resolving submitted feedback)
is API-only right now — `GET /pilot-feedback` and
`POST /pilot-feedback/{id}/resolve`, both requiring the
`platform.feedback.triage` permission — there is no dedicated triage screen
in `apps/web` yet. Recorded as a gap, not silently built partway.

## What this document does not cover

- The exact permission-to-role mapping's reasoning and what's still open
  about it — see `docs/decisions/OPEN-QUESTIONS.md`'s 2026-08-17/18 D-PILOT
  entry.
- The go-live/rollback decision — see
  `docs/operations/go-live-decision-pack.md`.

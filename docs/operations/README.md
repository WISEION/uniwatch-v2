# docs/operations

Runbooks and operational documentation.

- [`runbook.md`](runbook.md) — the linear pre-release sequence for running a release (Gate 0-5).
- [`runbooks/`](runbooks) — 9 incident-response runbooks (master plan §23.4): what to do when something specific goes wrong live, distinct from `runbook.md`'s pre-release sequence.
- [`slo.md`](slo.md) — SLO categories (no numbers yet — `D-SLO` open).
- [`pilot-onboarding.md`](pilot-onboarding.md) — how a pilot user signs in and what their role can do (Phase 6, task 6.D).
- [`go-live-decision-pack.md`](go-live-decision-pack.md) — template for the go-live/rollback decision (Phase 6, task 6.D; master plan §22 Gate 4).
- [`cutover-plan.md`](cutover-plan.md) — v1→v2 cutover/rollback mechanics for the pilot.
- [`release-notes-template.md`](release-notes-template.md) — per-release notes template (master plan §22 Gate 3).
- [`release-manifest.md`](release-manifest.md) — what the CI-produced release manifest artifact contains and how it's used.
- [`container-conventions.md`](container-conventions.md) — non-root/minimal-image/no-baked-secrets rules every `apps/*/Dockerfile` follows.

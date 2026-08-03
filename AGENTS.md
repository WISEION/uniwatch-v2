# AGENTS.md — rules for any human or AI agent working in this repository

This file is normative. It is kept in sync with the source documents under `C:\Users\orkha\Documents\Uniwatch VER2\` (NFR-DOC-01: `CONTEXT`/`AGENTS`/ADR are kept current, checked by a docs-gate in CI). If this file and the source documents disagree, the source documents win and this file must be corrected in the same change.

## 1. Read-docs-first (non-negotiable)

Before writing or changing any code, read, in this order:

1. `Uniwatch VER2/uniwatch-v2-project.md` — locked owner decisions and verified facts.
2. `Uniwatch VER2/UNIWatch-v2-PRD-v1.0.md` — the contract: FR-\*/NFR-\*, invariants `INV-01..14`, hard bans `NEG-01..07`, regressions `P001-P229`, gates §9, phases §10.
3. `Uniwatch VER2/UNIWatch-v2-master-development-plan-2026-07-28.md` — target architecture §7, domain model §14, roadmap §18, tests §21, gates §22.
4. `Uniwatch VER2/UNIWatch-v2-tender-intelligence-source-map-deep-research-2026-07-28.md` — tender data sources and evidence levels.
5. `Uniwatch VER2/Uniwatch/UNIWatch-v1-full-audit-2026-07-27.md` — 29 v1 findings, the regression checklist (Appendix A) + 13 release-note defects (RN-01..13).

On conflict: PRD v1.1 > master development plan (2026-07-28) > tender source map / v1 audit. Every requirement ID (`FR-*`, `INV-*`, `NEG-*`, `P0xx`, `NFR-*`) used in this repo (commits, tests, ADRs) must trace back to one of these documents. Do not invent a requirement ID.

See `docs/CONTEXT.md` for the condensed, always-current summary of these documents.

## 2. Hard bans (violation = stop, no exceptions)

1. **Never write to v1.** v1 lives at `Documents\Tendet Watcher` and at `Documents\UNIWatch` (a different checkout — not this repo). No code, script, or migration in this repo may read-write, mutate, or hold credentials for either path. Enforced by `tools/check-v1-untouched.*` (`FR-MIG-04`, `NEG-01`, `NEG-02`).
2. **Never invent numbers.** Financial weights, ML thresholds, SLO/RPO/RTO, and the exact pilot permission matrix are `TBD-01..05` / `D-*` pending an explicit research/approval gate (PRD §5.7.4, §13). Leave them as `TBD-nn`/`D-nn` in code, config, and docs — do not substitute a "reasonable" default.
3. **No silent fallback values.** `missing` / `stale` / `incomplete` / `synthetic` states are always shown, never hidden behind a default (`INV-11`).
4. **Ingestion never overwrites a human decision.** Auto-match / auto-derived data is always a `candidate`; only a human action creates or changes a decision (`INV-01`, `DM-04`).
5. **BOQ is `complete` only after proven page/row reconciliation** (`INV-04`). Absence of a source-provided total is `source_exhausted_unverified`, never `complete`.
6. **Green CI is not a production deployment authorization** (`INV-14`). Production requires a distinct approver and a separate two-person gate.
7. **No `dev_team`-style all-access role.** RBAC is deny-by-default (`FR-ADM-01`); every permission is explicit.

## 3. Domain boundaries (modular monolith, master plan §7.2)

- `packages/tender` never reads `packages/vendor` internal tables directly — only through an application contract.
- `packages/vendor` does not know the final Bid/No-Bid decision.
- `packages/decision` stores references to immutable input versions, never a mutable copy of "current" state.
- `packages/algorithm` does not own business facts — it owns policy graphs, evaluations, and approvals.
- `packages/platform` never contains domain scoring logic.

See `docs/adr/0001-modular-monolith-boundaries.md` for the enforced rules and how they are checked.

## 4. Phase / gate discipline

- One main line of work; phases do not overlap. Phase N+1 does not start before the supervisor issues GO on Phase N's exit report.
- Sub-agents specialize **within** the current phase; they are not parallel unrelated builds. Short parallelism is allowed only across independent `apps/*` with no shared code — when in doubt, go sequential.
- Every deviation from PRD/master-plan, or new assumption, is recorded in `docs/decisions/OPEN-QUESTIONS.md` — never decided silently.
- Phase/task plan of record: `docs/reports/PLAN-MISSION-1.md`. Session log: `docs/reports/WORKLOG.md` (append, do not rewrite history).

## 5. Repository map

```text
UNIWatch-v2/
  AGENTS.md               this file
  README.md
  docs/
    CONTEXT.md             condensed, current summary of the 5 source docs + boundaries
    architecture/          threat model, contracts, runtime diagrams
    adr/                   architecture decision records (NFR-ARC-07)
    product/               product-facing notes (Phase 2+)
    research/              open research (ML, financial policy — Phase 8+)
    operations/            runbooks, on-call, deploy (Phase 0.B+)
    decisions/             OPEN-QUESTIONS.md — deviation/assumption log
    reports/               PLAN-MISSION-1.md, WORKLOG.md, PHASE-N-EXIT.md
    superpowers/plans/     working plans
  apps/
    api/                   FastAPI — request/response only, no long external calls in-request
    worker/                separate Python worker — ingestion, jobs, outbox consumers
    web/                   React/TypeScript UI
  packages/
    platform/              cross-cutting: auth, RBAC, audit, observability, migrations glue
    tender/                tender ingestion, normalization, signals
    vendor/                vendor registry (synthetic-only until legal gate)
    decision/              Bid/No-Bid workflow, No-Go, outcomes
    algorithm/             policy graph / evaluation / approval (no business facts)
    contracts/             shared OpenAPI/DTO/schema contracts across apps and packages
  migrations/              versioned PostgreSQL migrations + ledger (see migrations/README.md)
  tests/
    unit/ integration/ contract/ state/ security/ e2e/ performance/
  fixtures/
    synthetic/             synthetic vendor fixtures (watermarked, deterministic seed)
    tender-snapshots/      frozen real-source fixtures for the empirical-contract connector
  operations/              deploy/runbook artifacts
  scripts/                 dev-only scripts
  tools/                   CI/repo-hygiene tools (e.g. v1-untouched check)
  .ci/                     CI gate definitions
```

This is the logical scaffold from master plan §7.3. Exact package contents are added as each phase's tasks require them — do not pre-build packages ahead of the plan.

## 6. Traceability convention

- Commits, PRs, and test names reference requirement IDs, e.g. `feat(worker): resumable pagination cursor commit (FR-JOB-04, FR-JOB-05, INV-03, P002)`.
- Every regression test file states which `P0xx`/`RN-xx` it covers and, if not yet enforced, which phase makes it mandatory (see `docs/reports/PLAN-MISSION-1.md` §5).
- ADRs are numbered sequentially in `docs/adr/`, never renumbered or deleted — superseded ADRs are marked `Superseded by ADR-000N`, not removed.

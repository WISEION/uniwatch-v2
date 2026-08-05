# ADR-0006 — Tender and Vendor as separate deployable services

**Status:** Accepted
**Date:** 2026-08-05
**Requirements:** PRD §2.2 non-goal amendment (2026-08-05), D-ARCH (§13.1, amended), supersedes part of ADR-0001

## Context

ADR-0001 locked in a modular monolith ("v2 must be a single deployable unit for now — no premature
microservices, `TBD-05`") directly from PRD v1.1 §2.2's own non-goal: "Не построить микросервисную
архитектуру на старте." That was a correct read of the PRD as written.

On 2026-08-05, the owner surfaced a hard customer requirement, received after PRD v1.1 was approved
and not previously recorded anywhere in this repo or the source documents: **Tender and Vendor must
operate as fully separate tools (own process/deployment), communicating with each other only through
an API** — not as packages sharing one process. The PRD (`Uniwatch VER2/0_UNIWatch-v2-PRD-v1.0.md`)
has been amended in place (§2.2 non-goal, D-ARCH §13.1) to record this as a scope change for this one
pair of modules specifically — see the "Правка 2026-08-05" annotations there. This ADR is the
repository-side decision record for that amendment (`AGENTS.md` §4: every deviation is recorded, never
decided silently).

**Scope of this decision:** Tender ↔ Vendor only. `packages/decision`, `packages/algorithm`,
`packages/platform` are not addressed by this ADR and remain governed by ADR-0001/ADR-0002 as written
until a separate decision says otherwise — both `decision` and `algorithm` are still empty packages
with no code built against the old assumption, so there is nothing to migrate there yet.

## Decision

- `apps/api` is split into two independently deployable FastAPI processes: **`apps/api-tender`** and
  **`apps/api-vendor`**. Each has its own process, own port, own startup/shutdown lifecycle — not two
  routers mounted on one app.

  > **Naming note (2026-08-05, at implementation time):** the actual directories/import paths are
  > `apps/api_tender` and `apps/api_vendor` (underscores) — Python package names cannot contain
  > hyphens. The hyphenated form above refers to the deployable service name (process/image/deploy
  > target), not the Python package path.
- `packages/tender` code and `packages/vendor` code are never imported into each other's process. The
  existing ADR-0001 rule ("`packages/tender` never imports or queries `packages/vendor` internals
  directly — cross-domain data flows only through a typed contract in `packages/contracts` **or a
  documented service call**") already anticipated this; the "documented service call" branch is now
  **mandatory** for this pair, not an allowed alternative to a future in-process contract.
- `packages/contracts` is promoted, for the Tender↔Vendor seam, from "shared Pydantic DTOs imported by
  both sides of one process" to a **real, versioned network API contract**: `apps/api-vendor` serves an
  OpenAPI-described HTTP API; `apps/api-tender` (or a future `packages/decision` that needs both) calls
  it over HTTP through a generated/typed client, with real network failure modes (timeout, retry,
  version mismatch) — not an in-process function call that happens to share a schema.
- `packages/platform` (db, migrations, RBAC, audit, correlation, errors, jobs, outbox, egress, etc.)
  remains a **shared library** imported by both `apps/api-tender` and `apps/api-vendor` (and the
  worker) — it is not itself split into two services. Each service still only ever touches its own
  domain's tables (unchanged from ADR-0001's "every business fact has exactly one authoritative
  entity/table" rule); cross-domain reads go through the new API, never a shared-table read.
- `apps/worker` is **not split by this decision**. It is currently tender-scoped in practice (no real
  vendor jobs exist yet — `packages/vendor` is still an empty package). Whether the worker itself needs
  to become two separate worker processes is deferred until vendor ingestion work actually starts,
  rather than decided speculatively now.

## Explicitly NOT decided here (stays open, do not invent)

- **Database topology:** one shared PostgreSQL instance with strict per-service table ownership, vs.
  a separate database/schema per service. This is real infrastructure cost tied to the still-open
  `TBD-05` (infra budget) and `D-HOST` (hosting) — inventing an answer here would violate `AGENTS.md`
  hard ban #2. Until resolved, `apps/api-tender` and `apps/api-vendor` may point at the same PostgreSQL
  instance, each restricted to its own domain's tables at the application layer (not yet at the DB-user/
  schema level) — a real gap, tracked in `docs/decisions/OPEN-QUESTIONS.md`, not hidden.
- **Separate CI/CD pipelines per service, service-to-service auth, service discovery.** Not designed
  yet — first implementation pass can run both processes from the same CI build/test suite; a real
  per-service deploy pipeline is a `D-HOST`-dependent follow-up.
- **Whether this repo stays one git repository for both services**, or splits into two. The owner's
  clarification was "own process/deployment," not explicitly "own repository" — kept as one monorepo
  for now (lower ceremony, still satisfies "own process/deployment"); revisit if that turns out to be
  insufficient.

## Consequences

- Every existing and future cross-domain call between `tender` and `vendor` must be expressed as a real
  HTTP call through `packages/contracts`' OpenAPI schema, with real timeout/retry/error handling — this
  is strictly more work than the in-process call ADR-0001 originally allowed for this pair, in exchange
  for actually satisfying the customer's requirement instead of a "seam that could be split later."
  There is currently no code that crosses this boundary yet (`packages/vendor` is empty), so this is a
  net-zero migration cost today and a real constraint on all future `tender`↔`vendor` work.
  `apps/api` (currently one FastAPI app) needs to be restructured into `apps/api-tender` +
  `apps/api-vendor` — a concrete, schedulable implementation task, not yet done as of this ADR.
- `docs/CONTEXT.md`'s "Locked decisions" section and ADR-0001's own decision bullets are updated
  alongside this ADR to reflect the amendment rather than silently drifting from it.

## Related

- Supersedes, for the Tender↔Vendor boundary only: ADR-0001 §"Decision", bullet on
  `packages/tender`/`packages/vendor` boundary enforcement. ADR-0001 is not deleted or renumbered — see
  its own updated header note.
- `docs/decisions/OPEN-QUESTIONS.md`, 2026-08-05 — full record of the deviation, its discovery, and the
  still-open infra questions above.
- `docs/reports/DEVELOPMENT-PAUSED-2026-08-05.md` — the pause report this ADR resolves the blocking
  question for; implementation (splitting `apps/api`) is tracked as the next task, not part of this ADR.

# ADR-0002 — Technology stack

**Status:** Accepted (owner-locked, PRD §13.1 D-ARCH — Approach A)
**Date:** 2026-08-04
**Requirements:** NFR-ARC-01, NFR-ARC-02, NFR-ARC-03, NFR-ARC-04, NFR-ARC-06

## Context

The kickoff TZ and PRD §13.1 (D-ARCH) already lock the stack at the owner level ("Что уже решено", not open for re-debate in Mission 1). This ADR exists to record the decision and its rationale per `NFR-ARC-07` ("ADRs are mandatory for boundary/stack/data-authority decisions"), not to re-open it.

## Decision

- **Frontend:** React / TypeScript (`NFR-ARC-01`).
- **API:** Python / FastAPI, contract-first — OpenAPI is the source of truth, strict request/response validation (`NFR-ARC-02`, `FR-PLT-01`). Implemented starting 0.B, not in this ADR's scope.
- **Worker:** a separate Python worker process, not in-request background threads (`NFR-ARC-03`). Rationale: v1's P113/P116 failures came directly from long network/BOQ/reconciliation work running inside the HTTP request lifecycle and from SQLite/process-lock limits; a durable, independently-scaled worker with job lease/retry/resume is required from day one.
- **Datastore:** PostgreSQL (`NFR-ARC-04`), with versioned migrations and a ledger (see ADR-0003 and `migrations/README.md`) — replacing v1's ad hoc SQLite schema changes at startup.
- **Repository/runtime:** one repository, one runtime, at `C:\Users\orkha\Documents\UNIWatch-v2`, fully separate from both v1 checkouts (`NFR-ARC-06`).

## Consequences

- Two language runtimes in one repo (TypeScript web, Python api/worker) — `packages/contracts` is the seam that keeps their interface honest; contract tests (master plan §8.2, §9.2) run against both.
- PostgreSQL from day one means Phase 0 must stand up a real migration ledger before any domain code lands (see ADR-0003, `migrations/README.md`) — there is no SQLite fallback path to fall back on if this slips.
- A separate worker process means every long-running operation (ingestion page fetch, BOQ reconciliation, notification generation) must be expressed as a durable job with identity, lease, and resumable progress (`FR-JOB-01..08`) rather than an in-request call — this is a hard constraint on 0.B/1.A design, not an optimization to consider later.

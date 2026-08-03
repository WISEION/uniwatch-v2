# ADR-0001 — Modular monolith with enforced domain boundaries

**Status:** Accepted
**Date:** 2026-08-04
**Requirements:** NFR-ARC-05, NFR-ARC-06, NFR-ARC-07, DM-01, INV-02, master plan §7.2/§7.3

## Context

UNIWatch v1's audit (`Uniwatch/UNIWatch-v1-full-audit-2026-07-27.md`) shows repeated cross-cutting breakage from undisciplined coupling: ingestion writing over human decisions, no clear owner for "the" business truth of a record, UI-only permission checks. v2 must be a single deployable unit for now (no premature microservices — no infra budget decision has been made, `TBD-05`), but with domain seams strict enough to split out a service later without a rewrite.

## Decision

- v2 is one repository, one runtime, one deployable unit: modular monolith (`NFR-ARC-05`), at `C:\Users\orkha\Documents\UNIWatch-v2`, fully separate from the v1 repo/runtime (`NFR-ARC-06`).
- Code is organized as `packages/{platform,tender,vendor,decision,algorithm,contracts}` plus thin `apps/{api,worker,web}` entry points (master plan §7.3). Business logic lives in `packages/*`; `apps/*` only wire packages to HTTP/CLI/UI.
- Enforced boundary rules (master plan §7.2):
  - `packages/tender` never imports or queries `packages/vendor` internals directly — cross-domain data flows only through a typed contract in `packages/contracts` or a documented service call.
  - `packages/vendor` has no reference to Bid/No-Bid decision state.
  - `packages/decision` stores references to immutable input versions (tender, BOQ, vendor, policy, model — `FR-DEC-01`, `INV-05`), never a mutable "current" copy of another domain's data.
  - `packages/algorithm` persists policy graphs, evaluations, and approvals — never business facts (those belong to `tender`/`vendor`/`decision`).
  - `packages/platform` (auth, RBAC, audit, observability, migrations glue) contains no domain scoring or business-decision logic.
- Every significant business fact has exactly one authoritative entity/table (`DM-01`, `INV-02`) — no shadow copies maintained by a second domain "for convenience."
- Boundary enforcement mechanism (added when 0.B introduces real code, not yet in 0.A): import-linter/dependency-graph check in the Fast CI gate blocks a `packages/x` → `packages/y` import that bypasses `packages/contracts`.

## Consequences

- Cross-domain features (e.g., a tender→vendor recommendation) require an explicit contract type in `packages/contracts`, which is slightly more ceremony than a direct import, in exchange for the boundary being machine-checkable instead of a convention nobody enforces.
- Splitting a package into its own deployable later is a packaging change, not a rewrite, because the import boundary already holds.
- This ADR does not decide *how* the boundary is mechanically enforced in CI (linter choice) — that is a 0.B/0.D task, referenced here as a follow-up, not decided now.

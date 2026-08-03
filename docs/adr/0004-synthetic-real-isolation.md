# ADR-0004 — Synthetic/real vendor data isolation

**Status:** Accepted
**Date:** 2026-08-04
**Requirements:** FR-VND-06, NEG-04, INV-11, master plan §8.2, PRD goal G4

## Context

The owner has locked vendors as **synthetic-only** until a separate legal/privacy/security gate (kickoff TZ "Что уже решено"; master plan §9-vendor scope; PRD goal G4). Synthetic data exists to let Decision/Algorithm work be built and tested before real vendor onboarding is legally cleared — but synthetic data creating false confidence, or leaking into a real/BI surface, is an explicit risk the master plan calls out (§17 risk register: "Synthetic создаёт ложную уверенность").

## Decision

- Separate `data_realm` per record: `vendor-sandbox` vs `vendor-production` (master plan §8.2). No table is shared across realms by convention alone — the realm is a first-class column/partition, not an inferred property.
- Every synthetic record is deterministically seeded and visibly watermarked `SYNTHETIC` in every surface it appears on (UI, API payload, export) — `INV-11` (no hidden fallback/synthetic state).
- **Strict isolation, not a soft label** (`FR-VND-06`): synthetic data cannot enter the production data path, and a synthetic record cannot be converted/promoted into a real record. A real vendor is always created via a fresh, confirmed onboarding flow — never by "flipping a flag" on a synthetic row.
- Synthetic IDs use a namespace disjoint from real IDs (e.g., a distinct ID prefix or a separate ID sequence/table space), so a foreign key or lookup cannot accidentally resolve a synthetic ID against production data.
- Sandbox users/roles cannot activate a production vendor record — this is enforced at the RBAC/service layer (0.B), not only by UI hiding.
- BI/exports exclude synthetic realm data by default; including it requires an explicit, auditable opt-in.
- The same application contract (`packages/contracts`) is used for both realms, and contract tests run against both the synthetic and the (future) real adapter, so isolation does not come at the cost of two divergent code paths silently drifting apart.

## Consequences

- Every vendor-domain table needs a `data_realm` dimension from its first migration — adding it later would require a backfill/migration on data that, by definition, must never mix realms, which is exactly the risk this ADR exists to avoid.
- Phase 1 (tender-only) does not yet exercise this ADR in running code; it is recorded now because `packages/vendor`'s schema and contract shape are decided at the same time as `packages/tender`'s, per ADR-0001's boundary rules, and must not need a breaking change when Vendor work starts.
- The real-vendor legal/privacy/security gate is out of Mission 1 scope; this ADR does not decide when that gate opens (that is `D-PII`/owner-level, PRD §13.2), only that the code path is structurally incapable of an accidental promotion before it does.

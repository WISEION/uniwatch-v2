# CONTEXT — UNIWatch-v2

Condensed, kept-current summary of the source documents (NFR-DOC-01). This file is a map, not a replacement — for exact wording of a requirement, go to the source document in `C:\Users\orkha\Documents\Uniwatch VER2\`.

## What this is

Tender / Vendor / Decision Intelligence for Unico QSC. Top-level navigation is exactly **Tender / Vendor / Decision**. A from-scratch rebuild — v1 (`Tendet Watcher` / `UNIWatch`) is not extended, not imported in-place, and not touched by v2 runtime credentials.

## Locked decisions (not up for debate, PRD §13.1 D-ARCH/D-AUTH/D-DATA/D-P0)

- Stack: React/TypeScript + Python/FastAPI + separate Python worker + PostgreSQL. Modular monolith. Separate repo/runtime at `C:\Users\orkha\Documents\UNIWatch-v2` (`NFR-ARC-01..06`).
- **Amended 2026-08-05 (ADR-0006, PRD §2.2/D-ARCH amendment):** `tender` and `vendor` are no longer part of the same deployable — they are separate services (`apps/api-tender`, `apps/api-vendor`), each its own process, communicating only through a real API contract (`packages/contracts`, promoted from in-process DTOs to a versioned network contract). `decision`/`algorithm`/`platform` are unaffected — still modular-monolith, per ADR-0001 (now only partially superseded for the `tender`↔`vendor` pair).
- Source: eTender, JSON-first, real data from the first vertical slice. Known contract facts: BOQ is complete on the API side (e.g. event 355920 → 4,135 BOM lines / 42 pages); the feed does **not** contain VÖEN or monetary values; the `EventType` filter is unreliable — the connector must validate actual response values, not trust request parameters (e.g. `EventType=2` returned `eventType=7`).
- Vendors: **synthetic only** (watermark `SYNTHETIC`, deterministic seed, strict isolation from real data) until a separate legal gate.
- Algorithm page: a versionable policy-graph builder with `Human` / `Rule` / `Gate` node types. ML is advisory-only and blocked until Phase 8.
- RBAC: deny-by-default; no `dev_team`-style all-access role.
- **Resolved 2026-08-14 (owner decision, `D-HOST`):** Hosting is **local network only** — no private/public cloud. Unblocks Phase 6 task 6.A's hosting-topology row; deployment pipeline/immutable-image-digest work can target a local-network target directly, no cloud provider abstraction needed.
- **Resolved 2026-08-14 (owner decision, `D-IDP`):** Pilot identity/auth is **lightweight local auth** built on the already-existing `users`/`roles`/`role_permissions` tables (`packages/platform/rbac`) — a real (not dev-bypass) login, but no external IdP (no Entra/OIDC) and no break-glass procedure, since the pilot is local-network-only and not internet-facing. This replaces `apps/api_tender/deps.py`'s current dev-only `X-Dev-User` header for the pilot, once built — not done yet, tracked as Phase 6 task 6.A work. Unblocks Phase 6 task 6.A's identity-integration row.

## Hard bans (NEG-01..07, PRD §2)

| ID | Ban |
|---|---|
| NEG-01 | Building v2 inside the v1 repo or v1 SQLite database |
| NEG-02 | Writing anything to `Documents\Tendet Watcher` or to another `Documents\UNIWatch` checkout |
| NEG-03 | Importing v1 BOQ as complete data |
| NEG-04..07 | See PRD v1.0 §2 for full list (no fabricated numbers, no silent fallback, no ingestion-overwrites-decision, no green-CI-is-deploy) |

## Data model — four layers (master plan §8, `DM-01..06`)

1. **Raw immutable evidence** — the exact source response/document, checksummed.
2. **Normalized fact** — typed representation that does not erase raw provenance.
3. **Derived signal/score** — computed, versioned by rule/model.
4. **Human decision** — append-only, with role, reason, and input snapshot.

Layer 3 never writes itself as layer 4 (`INV-01`, `DM-04`). Every significant record carries `id`, `source_id`/`source_record_id`, `source_url`/document id, `captured_at`/`effective_at`/`observed_at`, `raw_snapshot_id` + checksum, `parser_version`/`normalizer_version`, `data_origin` (`real`/`synthetic`/`legacy`/`derived`), `reality_status`, `freshness_status`, `completeness_status`, `quality_flags`.

## Synthetic/real isolation (master plan §8.2)

Separate `data_realm` (`vendor-sandbox` / `vendor-production`); visible `SYNTHETIC` watermark; sandbox roles cannot activate a production vendor record; synthetic IDs use a separate namespace; BI/exports exclude synthetic by default; synthetic→real promotion is forbidden (a new real vendor goes through onboarding instead); the same contract tests run against both adapters.

## Domain boundaries (master plan §7.2)

- `tender` never reads `vendor` internals directly — application contract only.
- `vendor` does not know the final Bid/No-Bid.
- `decision` references immutable input versions, never a mutable "current" copy.
- `algorithm` owns policy graphs/evaluations/approvals, not business facts.
- `platform` contains no domain scoring logic.

## Authority model (`FR-AUT-01..06`, `INV-06/07/13/14`)

- Final Bid/No-Bid and financial-policy activation: human only.
- Financial policy activation: maker/checker, two distinct identities; a policy's designer cannot activate their own policy.
- ML: advisory ranking / entity-matching / prioritization only. Never decides Bid/No-Bid, never overrides an active No-Go, never rewrites a human decision.
- Any override of an active No-Go: separate maker/checker flow, mandatory reason + evidence, both identities recorded.
- Score → recommendation/candidate, never a human decision by itself (`INV-07`).
- Production deployment: distinct approver from the initiator (`INV-14`).

## Mission 1 scope (this repo, now)

Phase 0 (Foundation) + Phase 1 (Tender ingestion core). Full task breakdown: `docs/reports/PLAN-MISSION-1.md`. Day-30 checkpoint (PRD §11): a real tender arrives → raw evidence stored → normalized version → data-quality status visible → signal created → deep link opens. Zero rows written to v1.

**Not in Mission 1 scope, tracked but not implemented yet:** Vendor onboarding UI, Decision/Bid workflow UI, Algorithm builder, ML. `P005` (final Bid/No-Go gate) still lands with Phase 4 Decision (`TENDER_INTELLIGENCE_SPEC.md` §7's Decision Core). `P003`/`P004` (tender↔project link decisions) and the frontend/`apps/web`/employee-dashboard/deep-links content **no longer have a confirmed phase** as of 2026-08-05 — `PLAN-MISSION-2.md` assigned them to Phase 2, but `TENDER_INTELLIGENCE_SPEC.md` §5's Phase 2 (BOQ depth + Forecast layer, now the plan of record) doesn't cover any of them; see `docs/decisions/OPEN-QUESTIONS.md`, 2026-08-05, for the open question to the owner. Phase 0/1 carry only their domain invariants + phase-tagged stub tests for P003/P004 — they are **not** reported as closed regressions of this mission (see `docs/reports/PLAN-MISSION-1.md` §5, remark #1 from task-002).

## Open questions blocking only their own phase (PRD §13.2)

| ID | Question | Blocks |
|---|---|---|
| D-SRC | Additional real tender sources, history range, snapshot retention | Full-volume close of Phase 1 (not the connector start) |
| D-LANG | First UI language and AZ/RU/EN order | Phase 2 |

`D-HOST`/`D-IDP` **resolved 2026-08-14** — see Locked decisions above; this was the one pair `PLAN-MISSION-6.md` §1 named as blocking Phase 6's *start* (task 6.A), not just a sub-task, so their resolution is what actually opens Phase 6 for planning. `D-PILOT` (pilot users/permission matrix, blocks Phase 6 task 6.D specifically) and `D-SLO` (SLO numbers, blocks Phase 6 task 6.C's numbers, not its mechanism) remain open — Phase 6 task 6.A can proceed without them. `D-TAX`, `D-FIN`, `D-PII`, `D-ML` block Phase 3+/7/8 sub-parts, already resolved-around in those phases' own mechanism-building. `TBD-01..05` (SLO/RPO/RTO/ML thresholds/financial weights/budget) stay unresolved — never defaulted (see `AGENTS.md` §2.2).

## Where things live

- Plan of record: `docs/reports/PLAN-MISSION-1.md`.
- Session log: `docs/reports/WORKLOG.md`.
- Deviations/new assumptions: `docs/decisions/OPEN-QUESTIONS.md`.
- ADRs: `docs/adr/`.
- Threat model: `docs/architecture/threat-model.md`.
- External standards/primary sources registry (S1-S14, e.g. OWASP SSRF for 1.C, UNECE UOM codes for
  Phase 3, WCAG 2.2 for Phase 2, NIST AI RMF for Phase 8): `docs/research/external-standards-and-sources.md`.
- Plan of record for the rest of Phase 1 (1.C/1.D/1.E) and a restructured Phase 2-4
  (DFE/SCG/EL/MDC subsystems, superseding `PLAN-MISSION-3/4/5.md`'s Vendor/Decision/Algorithm framing
  for the phases it covers): `TENDER_INTELLIGENCE_SPEC.md` (project root). Its own `INV-15..20`/`P301-P319`
  continue the PRD's `INV-01..14`/`P001-P229` scale without colliding — see
  `docs/decisions/OPEN-QUESTIONS.md`, 2026-08-04, for the full renumbering record and two owner
  decisions (Phase 3 real-vendor-data timing, forecast-percentage provisionality).

# CONTEXT — UNIWatch-v2

Condensed, kept-current summary of the source documents (NFR-DOC-01). This file is a map, not a replacement — for exact wording of a requirement, go to the source document in `C:\Users\orkha\Documents\Uniwatch VER2\`.

## What this is

Tender / Vendor / Decision Intelligence for Unico QSC. Top-level navigation is exactly **Tender / Vendor / Decision**. A from-scratch rebuild — v1 (`Tendet Watcher` / `UNIWatch`) is not extended, not imported in-place, and not touched by v2 runtime credentials.

## Locked decisions (not up for debate, PRD §13.1 D-ARCH/D-AUTH/D-DATA/D-P0)

- Stack: React/TypeScript + Python/FastAPI + separate Python worker + PostgreSQL. Modular monolith. Separate repo/runtime at `C:\Users\orkha\Documents\UNIWatch-v2` (`NFR-ARC-01..06`).
- Source: eTender, JSON-first, real data from the first vertical slice. Known contract facts: BOQ is complete on the API side (e.g. event 355920 → 4,135 BOM lines / 42 pages); the feed does **not** contain VÖEN or monetary values; the `EventType` filter is unreliable — the connector must validate actual response values, not trust request parameters (e.g. `EventType=2` returned `eventType=7`).
- Vendors: **synthetic only** (watermark `SYNTHETIC`, deterministic seed, strict isolation from real data) until a separate legal gate.
- Algorithm page: a versionable policy-graph builder with `Human` / `Rule` / `Gate` node types. ML is advisory-only and blocked until Phase 8.
- RBAC: deny-by-default; no `dev_team`-style all-access role.

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

**Not in Mission 1 scope, tracked but not implemented yet:** Vendor onboarding UI, Decision/Bid workflow UI, Algorithm builder, ML. `P003`/`P004` (tender↔project link decisions) land with Phase 2 linking; `P005` (final Bid/No-Go gate) lands with Phase 4 Decision. Phase 0/1 carry only their domain invariants + phase-tagged stub tests for these three — they are **not** reported as closed regressions of this mission (see `docs/reports/PLAN-MISSION-1.md` §5, remark #1 from task-002).

## Open questions blocking only their own phase (PRD §13.2)

| ID | Question | Blocks |
|---|---|---|
| D-HOST | Hosting: local network / private cloud / public cloud | Phase 0 production part / Phase 6 |
| D-IDP | Identity: Entra/OIDC for pilot, incl. break-glass | Phase 0 auth part / Phase 6 |
| D-SRC | Additional real tender sources, history range, snapshot retention | Full-volume close of Phase 1 (not the connector start) |
| D-LANG | First UI language and AZ/RU/EN order | Phase 2 |

D-PILOT, D-TAX, D-FIN, D-PII, D-SLO, D-ML block Phase 3+, out of Mission 1. `TBD-01..05` (SLO/RPO/RTO/ML thresholds/financial weights/budget) stay unresolved — never defaulted (see `AGENTS.md` §2.2).

## Where things live

- Plan of record: `docs/reports/PLAN-MISSION-1.md`.
- Session log: `docs/reports/WORKLOG.md`.
- Deviations/new assumptions: `docs/decisions/OPEN-QUESTIONS.md`.
- ADRs: `docs/adr/`.
- Threat model: `docs/architecture/threat-model.md`.
- External standards/primary sources registry (S1-S14, e.g. OWASP SSRF for 1.C, UNECE UOM codes for
  Phase 3, WCAG 2.2 for Phase 2, NIST AI RMF for Phase 8): `docs/research/external-standards-and-sources.md`.

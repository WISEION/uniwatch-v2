# ADR-0007 — ALG-RESEARCH dossier schema

**Status:** Accepted
**Date:** 2026-08-12
**Requirements:** FR-ALG-20, FR-ALG-21, FR-ALG-23, master plan §13.2 (ALG-RESEARCH gate, R1-R12), §13.3 (dossier schema), D-FIN, TBD-04

## Context

`docs/reports/PLAN-MISSION-5.md` §4 states: no policy version carrying a financial-impact flag may reach `approved` status until it has passed the ALG-RESEARCH gate (R1-R12, master plan §13.2) and its dossier is filled in (§13.3). That gate's *enforcement* — checking R1-R12 compliance before allowing an `approved` transition — belongs to task 5.B's compiler, which does not exist yet. But the dossier's own *shape* is needed now, in task 5.A, because `policy_versions.research_dossier_id` (the link the future compiler will check) needs somewhere real to point at, and a schema decision made under 5.B's time pressure (once the compiler is being built and something is needed *today*) is exactly how a dossier ends up missing a field nobody notices until a real financial policy needs it.

Candidate algorithms A-E (Tender Opportunity Priority, Bid/No-Bid support, Vendor Eligibility+Value Ranking, Price/delivery risk, ML matching/ranking) exist in the master plan only as formula *skeletons* — coefficients, thresholds, and weights are explicitly not decided there (`TBD-04`). This ADR does not resolve `TBD-04`; it only decides the shape a resolution would eventually be recorded in.

## Decision

A `ResearchDossier` (`packages/algorithm/research_dossier_model.py`) carries exactly the fields master plan §13.3 names, with one deliberate addition and one deliberate relaxation:

- **Fields, verbatim from §13.3:** decision statement; owners; approvers; source register; assumptions; data dictionary; formula/decision table; coefficients + rationale; validation design; test dataset manifest; results/limitations; fairness analysis; security/privacy analysis; approval/effective dates; monitoring/retirement criteria.
- **Every field is required except `fairness_analysis`**, which §13.3 itself qualifies as "где применимо" (where applicable) — not every policy has a fairness dimension worth analyzing (e.g. a pure data-quality gate node), and forcing a non-empty fairness section on one would fabricate an analysis rather than honestly reflect a checked "not applicable."
- **`coefficients_and_rationale` and `formula_or_decision_table` are opaque JSON, not typed numeric columns.** This ADR does not know, and must not guess, what shape a real financial formula will take (linear weights? a decision table? something else per candidate algorithm A-E) — typing them now would be inventing structure this ADR has no source for. Their *content* remains subject to `TBD-04`/`D-FIN`; this ADR only reserves the field.
- **A dossier is a standalone, append-only row** (`research_dossiers` table, no update/delete function in `research_dossier_store.py`), linked to a `policy_versions` row via a nullable `research_dossier_id` FK set after the fact — not embedded in `policy_versions` directly. A dossier's own identity (decision statement, source register, etc.) does not depend on which policy version currently points at it, and a future dossier revision is a new row, same append-only discipline as every other fact table in this codebase.
- **This ADR does not build gate enforcement.** Whether a given `policy_versions` row satisfies R1-R12 before `approved` is task 5.B's compiler's job, once it exists; this schema only gives it something concrete to check against.

## Consequences

- Task 5.B's compiler, when built, checks `financial_impact` nodes' version against a non-null `research_dossier_id` pointing at a dossier whose fields are all populated (except `fairness_analysis`) — this ADR is what makes that check well-defined rather than something 5.B has to invent its own shape for under time pressure.
- `D-FIN`/`TBD-04` remain exactly as unresolved as before this ADR. No coefficient, weight, or threshold is decided or defaulted anywhere in this schema.
- If a future candidate algorithm's real formula needs structure `coefficients_and_rationale`'s opaque JSON cannot express cleanly, that is a schema revision for whoever resolves `TBD-04` — not a violation of this ADR, since the field was deliberately left untyped for exactly this reason.

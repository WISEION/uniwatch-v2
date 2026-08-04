# External standards and primary sources (S1-S14)

Registry of official/primary external sources the owner has identified as authoritative for
specific future design decisions across phases. This is a **reference index**, not itself a
requirement source — it does not create new `FR-*`/`NFR-*`/`INV-*` IDs; it records *why* a future
ADR, contract, or policy design will cite a given external standard, and which existing
requirement IDs it backs. Per `AGENTS.md` §1, the five source documents under
`C:\Users\orkha\Documents\Uniwatch VER2\` remain the only place requirement IDs are defined — this
file supports design work against those requirements, it doesn't add to them.

URLs below are copied verbatim from Appendix C of `C:\Users\orkha\Downloads\UNIWatch-executive-report.md`
(28.07.2026 management report — an executive-summary derivative of the same master-plan/audit already
fully incorporated into `docs/reports/PLAN-MISSION-1..8.md`; not itself an additional normative source
under `AGENTS.md` §1). That report also cites the same two source documents already in AGENTS.md's
read-docs-first list, with checksums (`UNIWatch-v1-full-audit-2026-07-27.md`,
`UNIWatch-v2-master-development-plan-2026-07-28.md`) for reference if integrity verification is ever
needed.

## Procurement domain model and evaluation transparency

| ID | Source | Relevant to |
|---|---|---|
| S1 | [World Bank — Rated Criteria](https://www.worldbank.org/en/about/rated-criteria) — transparent non-price criteria, evidence, weights, value for money | `FR-DEC-*` (Phase 4 Decision scoring), `TBD-04` (financial policy weights research gate) — a methodology reference for what an evidence-based, explainable non-price criterion looks like, not itself the source of any AZ-specific weight |
| S2 | [World Bank — Procurement Framework](https://www.worldbank.org/ext/en/what-we-do/project-procurement/framework) | Same domain as S1; general guidance on evaluation/procurement process design |
| S3 | [Open Contracting Data Standard (OCDS) — Primer](https://standard.open-contracting.org/latest/en/primer/how/) (planning → tender → award → contract → implementation, releases, provenance) | Already named in the PRD as `INT-07` ("OCDS used as reference model for procurement lifecycle and provenance/data-quality review") — this is the primer document for that existing requirement, not a new one |
| S4 | [OCDS Data Review Tool](https://review.standard.open-contracting.org/) (schema/data-quality review) | Supports `INT-07` and `DM-05` (data-quality status as first-class attribute) — a concrete tool for validating a normalized-fact schema against OCDS conventions |
| S5 | [UNECE Recommendation 20](https://unece.org/code-list-recommendations) (unit-of-measure codes for international exchange) | Phase 3 Vendor (`FR-VND-*`, UOM/price/freshness per `PLAN-MISSION-3.md` draft) and the BOQ `unitOfMeasure` field already observed in the real eTender BOM-lines capture (`fixtures/tender-snapshots/etender/event_355920_bomlines_page1.raw.json`, values like `"ədəd"`) — a candidate canonical UOM code list for normalizing that field |

## Legal basis (Azerbaijan)

| ID | Source | Relevant to |
|---|---|---|
| S6 | [Azerbaijan Law № 988-VIQ](https://president.az/az/articles/view/60879) — base statutory text on public procurement | Legal foundation for the domain generally; relevant when Phase 7 (real vendor onboarding, legal/privacy gate) or Phase 4 Decision policy design needs to cite statutory basis |
| S7 | [Decree on the law's application](https://president.az/az/articles/view/60880) | Implementation detail for S6 |
| S8 | [Amendment, 20 July 2026](https://president.az/az/articles/view/73016) | Concrete evidence that the legal basis changes over time — relevant to `D-SRC` (retention/history range) and to not hardcoding legal assumptions into code without a review mechanism |

## AI/ML governance and model risk (Phase 8 preparation)

| ID | Source | Relevant to |
|---|---|---|
| S9 | [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework) (human-AI roles, governance, evaluation, lifecycle risk) | Phase 8 ML-advisory design (`FR-ALG-08`, `NEG-05`, `INV-06`/`INV-07`, `docs/adr/0005-authority-model.md`) — a governance framework reference for keeping ML advisory-only enforceable by design, not just by policy |
| S10 | [Federal Reserve SR 26-2](https://www.federalreserve.gov/supervisionreg/srletters/SR2602.htm) (risk-based model validation) | Methodological reference for independent model validation practice — cited as a well-regarded model-risk-management methodology to borrow structure from, **not** a literal compliance obligation (Unico QSC is not a US bank holding company); useful for Phase 8's model registry/validation design |

## Security and secure development

| ID | Source | Relevant to |
|---|---|---|
| S11 | [NIST Secure Software Development Framework (SSDF)](https://csrc.nist.gov/pubs/sp/800/218/final) | `NFR-SEC-07`/`NFR-SEC-09` (CI security gate: secret/dependency/license scanning), `.ci/README.md` security-gate stub plan, `docs/operations/container-conventions.md` — a secure-SDLC framework the CI security gate (not yet fully wired, per task 0.C) can be checked against |
| S12 | [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) (allowlist + defense-in-depth egress controls) | Directly backs `docs/architecture/egress-validator-contract.md` (`NFR-SEC-01..03`, `INV-10`, `P006`) — the central egress validator design task 0.C drafted and task **1.C** (not started) implements; this is the concrete control-pattern reference for that implementation |

## Accessibility

| ID | Source | Relevant to |
|---|---|---|
| S13 | [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) | `FR-UX-*` (Phase 2 UI), and the `tests/e2e/` a11y suite (`tests/README.md`: "Browser E2E + a11y") — the accessibility conformance standard those tests check against |

## Financial time-series (Phase 4/8 preparation)

| ID | Source | Relevant to |
|---|---|---|
| S14 | [Azerbaijan State Statistics Committee (Gosstat) — price indices](https://www.stat.gov.az/source/price_tarif/) | Candidate official time-index source for future financial models — relevant once `TBD-04` (financial policy weights) and Phase 4/8 scoring design move past the research/approval gate; not used by any code yet |

## Provenance of the two already-normative source documents (for integrity verification only)

Per the same executive report's Appendix C — these are the two `AGENTS.md` §1 source documents
this project already treats as normative; the checksums are recorded here only in case doc
integrity ever needs spot-checking, not as new information about their content:

- `UNIWatch-v1-full-audit-2026-07-27.md` — SHA-256 `1D7DDF69CA94AE1167D77D01AB3B72F631159012E55C3688FF5952556D126E94`
- `UNIWatch-v2-master-development-plan-2026-07-28.md` — SHA-256 `BBB818888523AF283066F7AB509191E47D3FFAECA6931A5B9F06E49B549F3946`

## How to use this registry

- When starting Phase 3 (Vendor), Phase 4 (Decision), Phase 5 (Algorithm), 1.C (egress validator
  implementation), or Phase 8 (ML advisory), check this table for sources already identified as
  relevant before researching from scratch.
- Citing one of these sources in an ADR or design doc does not by itself resolve a `TBD-*`/`D-*`
  item (e.g. S1/S2/S14 inform financial-policy *design*, they do not supply the actual weights —
  `TBD-04` stays open until its own research/approval gate, per `AGENTS.md` §2.2).
- Add exact URLs/citations here as they're confirmed, rather than reconstructing them from memory.

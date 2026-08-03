# ADR-0005 — Human / algorithm / ML authority model

**Status:** Accepted
**Date:** 2026-08-04
**Requirements:** FR-AUT-01, FR-AUT-02, FR-AUT-03, FR-AUT-04, FR-AUT-05, FR-AUT-06, INV-06, INV-07, INV-13, INV-14, PRD goal G3

## Context

v1's audit and release notes record two related failure classes: automated/derived outputs being treated as decisions (score without a human step, No-Go not enforced at the final gate — P005, RN-08), and deployment/policy authority not being distinct from the person or system proposing the change (RN-12: `environment: production` deployed by one person with no active required reviewer). PRD goal G3 ("preserve human authority over decisions") and the owner's locked decision that ML stays advisory (kickoff TZ) both require this to be a structural rule, not a UI convention.

## Decision

- **Human authority is final and exclusive** for the final Bid/No-Bid decision and for activating a financial policy (`FR-AUT-01`). No score, rule, or model output can itself constitute either.
- **Maker/checker on financial policy activation** (`FR-AUT-02`, `INV-13`): activation requires two distinct identities; the identity who designed/authored a policy cannot be the one who activates it. Financial policy additionally requires research, validation, monitoring, and rollback capability before activation (`INV-13`) — this ADR does not define *what* that research/validation consists of (that is `TBD-04`/Phase 8+ scope), only that activation cannot bypass the two-identity check.
- **ML stays advisory** (`FR-AUT-03`, owner-locked): in the phases where ML exists at all (blocked until Phase 8), it may only produce advisory ranking, entity/material matching, or prioritization. It cannot issue a final Bid/No-Bid, cannot cancel/override an active No-Go, and cannot rewrite a human decision.
- **No-Go override is a separate, audited flow** (`FR-AUT-04`, `INV-06`): any override of an active No-Go requires its own maker/checker flow with a mandatory reason and evidence; both identities are recorded. The final Bid/No-Bid transaction checks for an active No-Go as a hard stop (`FR-DEC-05`, `FR-DEC-06`) — this check is transactional (all-or-nothing with the rest of the final-Bid checks), not a separate best-effort validation step. (Full implementation is Phase 4/Decision scope — Phase 0/1 record the invariant and a stub, see `docs/reports/PLAN-MISSION-1.md` §5.)
- **A score is a recommendation, never a decision** (`FR-AUT-05`, `INV-07`): any algorithmic/derived output is written to a `candidate`/`recommendation` shape distinct from the human-decision table (see ADR-0003) — this is the same append-only-vs-candidate separation used for tender↔project linking (P003/P004) and applies symmetrically to Decision/Algorithm outputs.
- **Production deployment requires a distinct approver from the initiator** (`FR-AUT-06`, `INV-14`): green CI is necessary but not sufficient for a production deploy; the approval step is a separate, recorded action by a different identity, and checks an exact `commit ↔ image digest` match (guards against the v1 RN-12/RN-11 failure modes of a tag or version drifting from what was actually reviewed).

## Consequences

- Every domain that produces a derived/automated output needs, from its first schema, a `candidate` or `recommendation` table distinct from the `decision` table it feeds — this constrains Decision/Algorithm package design even though those packages are out of Mission 1's build scope.
- The financial-policy maker/checker and the production-deploy distinct-approver rules cannot be satisfied by a single-actor CI/CD pipeline; the eventual CI/CD design (Phase 0.D onward) must have a place for a second, distinct identity to approve, or this ADR is violated by construction.
- `TBD-04` (financial policy weights/thresholds) remains unresolved by this ADR — the ADR fixes *who* may activate a policy and how, not what the policy's numeric content is.

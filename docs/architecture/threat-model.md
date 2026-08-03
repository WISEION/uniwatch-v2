# Threat model (draft) — UNIWatch-v2

**Status:** Draft, produced by 0.A (architect). To be reviewed and jointly approved with 0.C (security) before Phase 0 exit — "architecture and threat model approved" is a Phase 0 exit criterion (kickoff TZ, `PLAN-MISSION-1.md` §2 Exit gate). Do not treat this file as approved until 0.C has signed off.
**Date:** 2026-08-04
**Requirements:** NFR-SEC-01..09, INV-10, P006, master plan §17 risk register, v1 audit lessons (S12 OWASP SSRF Prevention)

## 1. Scope

Phase 0/1 scope: the API, the worker, PostgreSQL, and the worker's outbound network calls to the eTender source. Web UI auth/session threats (`NFR-SEC-05`, `NFR-SEC-06`) are noted here for completeness but are primarily a Phase 0.B/2 concern once login exists.

## 2. Assets

| Asset | Why it matters |
|---|---|
| Raw tender evidence (snapshots, documents) | Legal/audit trail; loss or corruption breaks traceability (`FR-TND-02`) |
| Normalized tender data + BOQ | Business-critical; incomplete/incorrect BOQ was P001 |
| Human decisions (link accept/reject, Bid/No-Bid — Phase 2/4) | Must never be silently overwritten (`INV-01`) |
| Credentials/secrets (DB, future IdP, egress allow-list config) | Compromise = broad blast radius |
| v1 data and credentials (`Documents\Tendet Watcher`, other `Documents\UNIWatch` checkout) | Out of scope for v2 to touch at all — a v2 bug reaching v1 is a threat in itself (`NEG-01`, `NEG-02`) |
| Audit log / correlation trail | Needed to reconstruct any incident |

## 3. Trust boundaries

```text
[ eTender / external tender sources ]  <-- untrusted, redirect-capable
        |  (worker egress, HTTP)
[ Central egress validator + trusted source registry ]   <-- Phase 1 control point
        |
[ Worker process ]  --outbox-->  [ PostgreSQL ]  <--  [ API process ]  <--  [ Web UI / operator ]
        |                                                    ^
        +---- structured logs / correlation id --------------+
[ v1 runtime/DB (Tendet Watcher, other UNIWatch checkout) ]  <-- must remain UNREACHABLE from v2 (NEG-01/02)
```

Boundaries that matter most in Phase 0/1:

1. **Worker ↔ external network.** The worker is the only component that makes outbound calls to tender sources. This is the SSRF surface (P006, RN from v1: SSRF via RSS link/redirect).
2. **API/Worker ↔ PostgreSQL.** Least-privilege DB roles per process; migrations run with a separate, more privileged role than the running application (see `migrations/README.md`).
3. **v2 ↔ v1 filesystem/DB.** Zero legitimate traffic ever crosses this boundary; any attempt is a bug or an attack, not a feature (`FR-MIG-04`).
4. **Operator/browser ↔ API.** Not yet implemented in Phase 0/1 (no UI login flow exists in this repo yet); recorded for Phase 0.B/2 continuity.

## 4. Threats and controls (by NFR-SEC-*)

| # | Threat | Control | Requirement | Status Phase 0/1 |
|---|---|---|---|---|
| T1 | SSRF: connector follows a redirect or a document link into loopback/private/link-local/metadata address space (IPv4 or IPv6) — this is exactly how v1 was hit via an RSS link redirect | Central egress validator checks the target **before DNS resolution and after every redirect**; blocks loopback/private/link-local/metadata ranges, both IPv4 and IPv6 | NFR-SEC-01, INV-10, P006 | Designed in 0.A/0.C, implemented in 1.C. Not yet built — this file records the contract, not the code. |
| T2 | Connector is pointed at an untrusted/unregistered host (compromised config, malicious redirect target, typo) | Trusted source registry: outbound requests are only permitted to hosts explicitly registered; a new source is validated by an actual scanner run before being trusted, not by a structural check alone (lesson from ADB/0.18.0: "HTTPS + status code + trust level" was not sufficient) | NFR-SEC-03 | Contract defined in 0.A/0.C; implementation in 1.C |
| T3 | Defense-in-depth gap: application-layer egress control has a bug and nothing else stops the outbound call | Network-policy-level egress control independent of application code (S12 OWASP SSRF Prevention) | NFR-SEC-02 | Design placeholder — exact mechanism (container/network policy) depends on `D-HOST`, tracked as blocked-on-owner-decision, not a Phase 0/1 blocker |
| T4 | CSRF / session riding once a web UI exists | CSRF tokens, Origin verification, secure cookie flags | NFR-SEC-05 | Out of Phase 0/1 build scope (no login flow yet); recorded so 0.B does not omit it later |
| T5 | Auth/session contract drift (password version, OIDC binding, sign-out, lockout semantics) — v1's P229/RN-class defects | Explicit, tested auth/session contracts | NFR-SEC-06 | Blocked on `D-IDP` (owner decision) for the real IdP; local dev-auth in 0.B does not need to resolve this to proceed |
| T6 | Compromised/malicious dependency or leaked secret reaching a build | Dependency/SBOM scan, secret scan, license scan in CI (NIST SSDF, S11) | NFR-SEC-07 | Stub gate in 0.C/0.D (see `.ci/`); full enforcement is a release-candidate gate, not Phase 0/1 |
| T7 | Container runs as root / writable image gives an attacker persistence or lateral movement | Non-root, read-only container convention | NFR-SEC-08 | Convention recorded in 0.A/0.C; enforced when Dockerfiles are written in 0.B — not yet built |
| T8 | Deployed artifact does not match the reviewed commit (tag reuse, build-time substitution — v1 RN-11/RN-12) | Immutable image digest; `commit ↔ digest` match verified at production authorization | NFR-SEC-09, INV-14 | Out of Phase 0/1 scope (no production deploy path yet); recorded for Phase 0.B/6 continuity |
| T9 | v2 process/credential accidentally reaches v1 paths (bug, copy-paste config, careless script) | No write-credentials to v1 paths in any v2 process; CI check scans for v1 path literals and fails the build if touched | FR-MIG-04, NEG-01, NEG-02 | Implemented in this task — see `tools/check-v1-untouched.py` and `.ci/v1-untouched.yml` |
| T10 | Migration/backfill runs implicitly at every app startup, creating an uncontrolled attack/failure surface (schema drift, partial backfill under load) | Schema changes only via versioned migrations with pre/postflight; schema never changes at startup; backfill is a separate, explicitly invoked operation | FR-PLT-12, DM-06 | Ledger convention and directory skeleton implemented in this task — see `migrations/README.md` |
| T11 | Invariant violation (e.g., FK violation) reaches production data undetected | Constraint violation triggers quarantine/read-only on the affected area and notifies operators; CI blocks on an intentionally-triggered failure | FR-PLT-13, P007 | Contract recorded here; test harness is 0.D scope, not yet built |

## 5. Out of scope for this draft (explicitly deferred, not forgotten)

- Exact network-policy mechanism for T3 — depends on `D-HOST` (owner decision, blocks only the production part of Phase 0, per `docs/CONTEXT.md`).
- Real IdP integration threats (T5) — depends on `D-IDP`.
- Anything downstream of a real login/session existing (CSRF specifics, lockout tuning) — Phase 0.B/2.
- ML/algorithm-authority threats (prompt injection into advisory ranking, model poisoning) — out of Mission 1; ML is blocked until Phase 8 by owner decision.

## 6. Review status

Reviewed by: architect (0.A) — draft only. **Pending:** 0.C (security) joint review and sign-off before this is cited as a closed Phase 0 exit criterion.

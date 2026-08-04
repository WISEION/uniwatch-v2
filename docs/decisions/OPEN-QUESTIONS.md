# OPEN-QUESTIONS — deviation and assumption log

Every deviation from PRD v1.0 / master development plan (2026-07-28), and every new assumption made during implementation, is recorded here at the time it is made — never decided silently (kickoff TZ, "Порядок работы" item 3; `AGENTS.md` §4).

Format per entry:

```markdown
## YYYY-MM-DD — short title

**Context:** what task/phase surfaced this.
**Deviation/assumption:** what was decided and why the source docs did not already cover it.
**Source conflict (if any):** which documents disagree, and which one won per the priority order (PRD > master plan > source map / v1 audit).
**Owner follow-up needed:** yes/no — if yes, link to the relevant `D-*`/`TBD-*` in `docs/CONTEXT.md`.
```

The blocking-but-not-now owner questions (`D-HOST`, `D-IDP`, `D-SRC`, `D-LANG`) and the never-defaulted `TBD-01..05` are tracked in `docs/CONTEXT.md`, not duplicated here — this file is for deviations discovered during build, not the pre-known open list from planning.

## 2026-08-04 — CI runner platform

**Context:** Task 0.D (qa), wiring the Fast/Full CI gates (`docs/reports/PLAN-MISSION-1.md` §2).

**Deviation/assumption:** Neither the PRD nor the master development plan names a CI vendor/platform anywhere in their gate model (Gate 0-5, master plan §22) — they describe what each gate checks, not what runs it. `.github/workflows/ci.yml` (GitHub Actions) was added as the concrete runner. This is a low-risk implementation choice (a common default, easy to replace, no lock-in to any hosting decision), not a re-interpretation of a locked requirement.

**Source conflict (if any):** None — the source docs are simply silent on CI vendor. Not a PRD-vs-master-plan disagreement.

**Owner follow-up needed:** No. Distinct from `D-HOST` (production hosting: local network/private cloud/public cloud) — a CI runner choice does not imply or constrain that decision. If a different CI platform is later preferred, `.github/workflows/ci.yml` is the only file that needs to change; the gate *contents* (`.ci/README.md`) are platform-agnostic.

## 2026-08-04 — eTender event-details capture shows VÖEN and monetary value (contradicts locked "0/103" fact)

**Context:** Task 1.A (`docs/reports/PLAN-MISSION-1.md` §3), live capture of frozen fixtures for the
empirical-contract connector (see `fixtures/tender-snapshots/etender/MANIFEST.md`).

**Deviation/assumption:** A real, bounded `GET https://etender.gov.az/api/events/355920` (2026-08-04)
returned `"organizationVoen": "1000418451"` and `"estimatedAmount": 16922253.74` populated. This appears
to contradict the locked fact in `uniwatch-v2-project.md`/`docs/CONTEXT.md`: "eTender feed carries no
VÖEN (0/103 events) and no monetary values (0/103)". This session did **not** silently resolve the
contradiction — the connector code built in 1.A treats VÖEN/`estimatedAmount` as present-when-the-source-
provides-them on the **details** subresource, without assuming they are absent (per `FR-TND-07`,
independent subresource status) and without assuming the old fact was wrong.

**Source conflict (if any):** Not a PRD-vs-master-plan conflict — both agree with `uniwatch-v2-project.md`.
Working theory (not confirmed): the "0/103" measurement in the source doc was taken against the **events
list** resource specifically, and VÖEN/amount may be fields that only exist on the **event details**
resource, which the earlier check may not have queried per-event. This session could not capture the list
resource to test that theory (see the next entry) and does not assert it as fact.

**Owner follow-up needed:** Yes. Before Phase 4 (Decision, which needs `value_basis` per `FR-DEC-05`/`DM-05`
and buyer-identity handling) treats "eTender has no VÖEN/money" as a settled design constraint, someone
needs to re-run the original 103-event check against the **details** endpoint specifically (not just list)
to confirm or retire this fact. Does not block Phase 1 — the connector already surfaces whatever the source
provides per-field, never fabricating and never silently dropping either way.

## 2026-08-04 — eTender events-list endpoint contract not captured this session

**Context:** Same task 1.A fixture-capture session as above.

**Deviation/assumption:** `GET https://etender.gov.az/api/events` returned `400 Bad Request`
(RFC 9110 problem+json, no field-level validation detail) for every query-parameter combination tried in
this bounded session (`PageSize`/`PageNumber`, `pageSize`/`pageNumber`, `Skip`/`Take`, `PageIndex`,
with/without `EventType`, with/without a publish-date range); `POST /api/events` returned
`405 Method Not Allowed` (confirms GET is correct, just not the right query shape); the site's bundled
frontend JS did not reveal the parameter names via static string search for `events`/`EventType`/`Page*`
tokens. Task 1.A proceeds on the **details** (`/api/events/{id}`) and **BOQ**
(`/api/events/{id}/bomLines`) resources only, both successfully captured and matching documented facts
(see `MANIFEST.md`) — these are sufficient to build and test the empirical-contract/schema-drift mechanism
task 1.A requires. List-resource resumable pagination is task **1.B** scope, not 1.A.

**Source conflict (if any):** None.

**Owner follow-up needed:** Yes, before 1.B starts — the events-list query contract needs to be
established, either by inspecting a working v1/browser network trace of `etender.gov.az`'s own tender
search page, or by a follow-up bounded probing session with more attempts than this one budgeted for.
Blocks 1.B's resumable-pagination work, not 1.A.

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

## 2026-08-04 — eTender event-details capture shows VÖEN and monetary value (contradicts locked "0/103" fact) — RESOLVED same day

**Context:** Task 1.A (`docs/reports/PLAN-MISSION-1.md` §3), live capture of frozen fixtures for the
empirical-contract connector (see `fixtures/tender-snapshots/etender/MANIFEST.md`).

**Deviation/assumption:** A real, bounded `GET https://etender.gov.az/api/events/355920` (2026-08-04)
returned `"organizationVoen": "1000418451"` and `"estimatedAmount": 16922253.74` populated. This appeared
to contradict the locked fact in `uniwatch-v2-project.md`/`docs/CONTEXT.md`: "eTender feed carries no
VÖEN (0/103 events) and no monetary values (0/103)".

**Resolution (same-day follow-up, browser network trace + `GET /api/events` capture):** Confirmed, not
just theorized — the **events list** resource (`events_list_page1.raw.json`) has neither a buyer-VÖEN
field nor any monetary field on its items (`eventId`, `eventType`, `eventStatus`,
`buyerOrganizationName`, `eventName`, `publishDate`, `endDate`, `hasNewVersion`,
`awardedParticipantName`, `awardedParticipantVoen`, `documentViewType`, `actualVersionId`,
`privateRfxId`, `hasRecreated` — `awardedParticipantVoen` is the *winning bidder's* VÖEN, populated only
after award, not the buyer's). The "0/103" fact is correct for the list resource. VÖEN/`estimatedAmount`
are **details-subresource-only** fields — exactly the `FR-TND-07` independent-subresource-status case,
not a contradiction. No old fact was wrong; two different subresources simply carry different fields.

**Source conflict (if any):** None — resolved without needing to override either source.

**Owner follow-up needed:** No further action. Phase 4 (`value_basis`/buyer-identity handling) can rely on:
list resource has no VÖEN/money, details resource has both, when present.

## 2026-08-04 — eTender events-list endpoint contract not captured this session — RESOLVED same day

**Context:** Same task 1.A fixture-capture session as above.

**Deviation/assumption:** `GET https://etender.gov.az/api/events` returned `400 Bad Request`
(RFC 9110 problem+json, no field-level validation detail) for every query-parameter combination tried in
that bounded session (`PageSize`/`PageNumber`, `pageSize`/`pageNumber`, `Skip`/`Take`, `PageIndex`,
with/without `EventType`, with/without a publish-date range); `POST /api/events` returned
`405 Method Not Allowed`. Task 1.A proceeded on the **details** and **BOQ** resources only — sufficient
for that task. List-resource resumable pagination is task **1.B** scope, not 1.A.

**Resolution (same-day follow-up, live browser network trace of the real search page via
`claude-in-chrome`, not further guessing):** The real frontend request is
`GET /api/events?EventType=&PageSize=6&PageNumber=1&EventStatus=1&Keyword=&buyerOrganizationName=&documentNumber=&publishDateFrom=&publishDateTo=&AwardedparticipantName=&AwardedparticipantVoen=&DocumentViewType=&IsArchived=false`
— every listed key must be present in the query string (even empty string), with `PageSize`,
`PageNumber`, `EventStatus` (int), `IsArchived` (bool) non-empty. No cookie or CSRF token required — a
bare `curl` with this exact key set returns `200` (`events_list_page1.raw.json`, checksummed in
`MANIFEST.md`). The earlier `400`s were from ASP.NET query-DTO model binding failing whole-object when a
required non-nullable property (`EventStatus`/`IsArchived`) had no query key at all — not present-but-
wrong-typed, just entirely absent — with no field-level detail surfaced in the error body. `EventType`
itself can be empty (unfiltered) or a specific code; the connector must still validate the actual
`eventType` returned per item rather than trust the requested filter (`FR-TND-10`, unchanged).

**Source conflict (if any):** None.

**Owner follow-up needed:** No further action needed to start 1.B — the query contract above is ready to
use. 1.B itself (resumable pagination implementation) has not started; this only removes its blocker.

## 2026-08-04 — TENDER_INTELLIGENCE_SPEC.md integrated: ID renumbering + Phase 3 vendor-gate deviation + forecast percentages flagged provisional

**Context:** Owner supplied `TENDER_INTELLIGENCE_SPEC.md` (project root) as the continuation spec for
the rest of Phase 1 plus a restructured Phase 2-4 (DFE/SCG/EL/MDC subsystems), right after 1.A/1.B
closed and before starting 1.C.

**Deviation/assumption 1 — ID renumbering (mechanical, not a content decision):** The document's own
draft numbering (`INV-1..10`, `P011-P054`) collided with the PRD's existing `INV-01..14`/`P001-P229`
scale on the same numbers with different meanings (draft `INV-6`=egress/SSRF vs PRD's actual
`INV-10`=egress/SSRF; draft `INV-8`=decision-not-recommendation vs PRD's actual `INV-07`=same
concept; three of the draft's ten invariants turned out to be verbatim restatements of existing PRD
invariants under different numbers). Resolved in-place, per owner instruction ("не трогай нашу
нумерацию, переделай его"): the file was edited directly — restated invariants now cite the existing
PRD ID instead of minting a duplicate; genuinely new invariants continue the PRD's own scale from
`INV-15`; all proofs (none of which are from the original 29-item v1 audit) moved to a new `P301-P319`
block so they never collide with `P001-P229`. PRD's own `INV-01..14`/`P001-P229` were not touched or
renumbered.

**Deviation/assumption 2 — Phase 3 real vendor data, not synthetic-first:** The original
`UNIWatch-v2-master-development-plan-2026-07-28.md` puts *real* vendor data ingestion at Phase 7, only
after a dedicated legal/privacy/security gate — Phase 3 there is synthetic-only (`FR-VND-06`,
`docs/adr/0004-synthetic-real-isolation.md`). `TENDER_INTELLIGENCE_SPEC.md` §6.1 moves real supply-side
ingestion (photos/voice/ERP pulls from real vendors' own folders) into Phase 3. **Owner decision,
recorded, not assumed by the agent:** Unico QSC has 20 years of existing, known vendor relationships —
this is not a cold-start "will we find suppliers" question, so the separate external legal-gate
sequencing built for *unknown* vendors doesn't apply the same way to ingesting data about vendors the
company already works with. Basic data-hygiene concerns (PII of individual contacts in voice
notes/photos, retention, access control) still apply as ordinary internal practice, just not as a
blocking standalone v2 gate. Recorded in `TENDER_INTELLIGENCE_SPEC.md` §6 itself as a visible banner,
not silently dropped.

**Deviation/assumption 3 — Forecast engine percentages (§5.3) are illustrative, not calibrated:** The
draft stated specific confidence tiers (≈30%/60%/85%) as if already decided. Flagged and edited in
place as `TBD-TIS-02` (same treatment as the PRD's own `TBD-03`, ML minimum labels/uplift/calibration)
— the tier *structure* (three levels by number of converging signals) is a real design choice, the
exact percentages are not settled until the retro-sample backtest (`P310`) runs for real.

**Not yet resolved / worth a closer look before Phase 5 starts:** the new document's Phase 4 "Decision
Core" (§7.1, MDC) implements Go/No-Go and Bid/No-Bid decision logic directly, without an obvious
equivalent of the original master-plan's dedicated Phase 5 "АЛГОРИТМ" page (a separate versionable
policy-graph builder with Human/Rule/ML/Gate node types — a decision already locked in
`docs/CONTEXT.md`'s "Locked decisions"). Whether Decision Core is meant to sit *on top of* a future
АЛГОРИТМ builder, or replace the need for one, is not addressed in the new document and hasn't been
asked of the owner yet — noting it here rather than assuming either answer. Does not block Phase 1's
remaining tasks (1.C/1.D/1.E).

**Owner follow-up needed:** No further action needed to continue 1.C. The АЛГОРИТМ-builder question
above should be raised before Phase 5 planning starts.

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

## 2026-08-05 — PLAN-MISSION-2.md vs TENDER_INTELLIGENCE_SPEC.md §5: two different "Phase 2"s

**Context:** Starting Phase 2 after the owner's GO on the Phase 1 Exit gate. Checking `TENDER_INTELLIGENCE_SPEC.md`
against every existing PLAN-MISSION draft (done for 3/4/5 on 2026-08-04) surfaced a gap: `PLAN-MISSION-2.md`
was not compared against the new document at integration time, and it turns out to describe substantially
different content for the same phase number.

**Deviation/assumption:** `PLAN-MISSION-2.md` (drafted before the new spec) scopes Phase 2 as: `apps/web`
frontend, Tenders/Projects/Signals UI, tender<->project human link decisions (`P003`/`P004`), full BOQ
pagination, deep links, employee dashboard, browser E2E/WCAG. `TENDER_INTELLIGENCE_SPEC.md` §5 scopes its
own Phase 2 as: BOQ line depth (2.A), signal ingestion (2.B), a forecast engine (2.C), a forecast card +
delivery (2.D) -- no frontend, no `apps/web`, no tender<->project linking, no employee dashboard at all.

**Resolution (per owner, "go on" after the discrepancy was flagged -- same precedent as the 2026-08-04
Phase 3/4/5 supersession):** `TENDER_INTELLIGENCE_SPEC.md` §5 is the plan of record for Phase 2 content
going forward; `PLAN-MISSION-2.md` is marked likely-superseded, same treatment as 3/4/5, not deleted.

**Consequence that must not be silently dropped:** `docs/CONTEXT.md`'s "Mission 1 scope" section and
`PLAN-MISSION-1.md` §5 both state "`P003`/`P004` (tender<->project link decisions) land with Phase 2
linking" -- that assumption no longer holds under the new Phase 2 scope, which does not mention tender<->project
linking at all. **P003/P004 currently have no assigned phase** in any document that is still the plan
of record. Same open status for the frontend/`apps/web`/employee-dashboard/deep-links content
(`FR-PLT-08`, `FR-TND-11/12`, `P223`, `P226`) that `PLAN-MISSION-2.md` owned -- not covered by the new
document's Phase 2, 3, or 4 either, on a first read.

**Owner follow-up needed:** Yes. Before P003/P004's regression-registry entries can be reassigned to a
real phase (they currently still say "mandatory from Phase 2 (PLAN-MISSION-1.md §5 [правка №1];
PLAN-MISSION-2.md draft)", which is now stale), and before frontend work is skipped or deferred, the
owner should confirm whether: (a) frontend/linking/dashboard content lands in a later phase not yet
drafted, (b) it merges into one of the new document's existing phases, or (c) `PLAN-MISSION-2.md`'s
content stands alongside the new Phase 2 rather than being superseded by it. Not blocking to start
2.A (BOQ line depth) now, which both documents' Phase 2 agree on.

## 2026-08-05 — Task 2.A: preliminaries/provisional-sum/prime-cost keywords are English-only

**Context:** `TENDER_INTELLIGENCE_SPEC.md` §5.1 names `preliminaries`, `provisional sums`, and `prime cost`
as line types to detect, giving only their English terms. The actual source data (eTender, Azerbaijan) is
in Azerbaijani.

**Deviation/assumption:** `classify_line_type` (`packages/tender/boq_line_model.py`) matches English keywords
only. No Azerbaijani or Russian equivalent terms are implemented, because no source document (the spec, the
PRD, the master plan) supplies them, and guessing a translation would be inventing an unsourced fact
(`AGENTS.md` hard ban #2's spirit, even though this isn't a `TBD-nn` financial number specifically).

**Consequence that must not be silently dropped:** a real Azerbaijani-language BOQ line that IS a
preliminaries/provisional-sum/prime-cost line, described only in Azerbaijani, will currently classify as
`normal` — a false negative, not a crash or a guess. `unit_status`/schema-drift-style visibility does not
cover this; it is a silent-until-flagged gap in the classifier's recall, not its precision.

**Owner follow-up needed:** Yes, non-blocking. Confirm the correct Azerbaijani/Russian terms for these three
line types (or confirm English-only is acceptable because BOQ documents on this source are bilingual/English
in practice for these specific line types) before Phase 2.C (forecast engine) or any matching/costing logic
starts relying on `line_type` for anything beyond the English-labeled real-world cases proven so far.

## 2026-08-05 — Task 2.B: signal ingestion closed for exactly one source (World Bank donor pipeline)

**Context:** `TENDER_INTELLIGENCE_SPEC.md` §5.2 names six signal source categories (budgets/investment
programs; presidential/cabinet decrees via president.az/e-qanun.az; donor pipelines WB/ADB/EBRD/AIIB;
TEO/design tenders; annual procurement plans and their changes; customer vacancies/appointments). Task
2.B (`docs/superpowers/plans/2026-08-05-phase2-task2b-signal-ingestion-worldbank.md`) built the generic
`Signal` fact model (`INV-15`/`INV-16`/`INV-17`, new invariants this task is the first to implement) and
proved it against exactly one real, live source: the World Bank Projects API
(`https://search.worldbank.org/api/v2/projects`), one genuine instance of the "donor pipelines" category.

**Deviation/assumption:** three choices made without a source document dictating the exact answer:
1. `confidence` on `Signal` is a qualitative provenance tier (`"official_source"`, fixed for this one
   connector), not a calibrated probability — that remains `TBD-TIS-02` (task 2.C, built from *multiple*
   signals). A future source with less structural certainty (e.g. a decree scraped from e-qanun.az, or a
   voice-note tip per `INV-18`) needs its own tier; `"official_source"` must not become a silent default
   confidence for every future connector.
2. `object_region` for this connector is country-level only (`"Republic of Azerbaijan"`) — the World
   Bank's public Projects API does not expose sub-national geography for Azerbaijan projects. A future
   signal source with real regional granularity should not be forced into this same coarseness by
   precedent.
3. `search.worldbank.org`'s trusted-source registration used in `tests/security/test_worldbank_live_fetch.py`
   is test-scoped (`scanner_run_reference="test-scan"`) — same precedent as `etender.gov.az`'s own
   test-only trust in `tests/security/test_ssrf_suite.py`. Production trust for either host (a real
   scanner run, a real security review) is a still-open operational decision, not resolved by either task.

**Consequence that must not be silently dropped:** the other five `TENDER_INTELLIGENCE_SPEC.md` §5.2
signal categories, and the other three donor institutions (ADB/EBRD/AIIB), remain entirely unstarted — no
phase/task document assigns them individually yet. `P309` is proven for one source, not for the category
in general; a future reader must not read "task 2.B closed" as "signal ingestion is done."

**Owner follow-up needed:** No, not blocking. Confirming production trust for `search.worldbank.org` (or
`etender.gov.az`) is an operational step that can happen independently of further development; the
`confidence`/`object_region` design notes above are guidance for whoever builds the next signal source,
not a decision the owner needs to make now.

## 2026-08-05 — Task 2.B second slice (design/TEO tenders): EventStatus mapping and free-text extraction still open

**Context:** per the owner's direction ("add a second signal source first"), a second `Signal` source
was built (`docs/superpowers/plans/2026-08-05-phase2-task2b-signal-ingestion-design-tenders.md`):
design/TEO tenders derived from eTender's own already-ingested events-list pages, no new external host.

**Deviation/assumption:** two real, honest gaps carried forward rather than guessed at:
1. `EventStatus`'s real value-to-meaning mapping was never decoded (only `EventStatus=1` = "open" is
   known, from the 2026-08-04 follow-up session). Every real `design_tender` signal captured so far has
   `is_awarded: False` because the search only covers open tenders — the spec's own worked example for
   this category ("тендер на ТЭО выигран" = *won*, not just published) describes the stronger signal,
   which needs a different, currently-unknown `EventStatus` value to search for.
2. `object_region`/`object_project_type` are `None` for every `design_tender` signal — eTender's
   events-list item has no structured field for either; both exist only as free text inside `eventName`
   (Azerbaijani place names like "Qəbələ şəhərində", work-category phrases like "yolların əsaslı
   təmiri"). Extracting either is real, valuable, unattempted work (a gazetteer of Azerbaijan
   administrative regions, or a category-keyword taxonomy), not guessed at here.

**Consequence that must not be silently dropped:** a future reader must not assume `is_awarded` will
ever be `True` under the current search parameters, or that `object_region`/`object_project_type` are
simply "not yet populated" in the sense of a TODO — they require new extraction logic this task
deliberately did not attempt, not just a config change.

**Owner follow-up needed:** No, not blocking. Both are real future-work items for whoever extends this
signal source or builds the object graph (task 2.C) that needs finer-grained geography/category than
this source alone provides.

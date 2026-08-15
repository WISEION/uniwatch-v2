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

## 2026-08-05 — Task 2.C partial: World Bank↔eTender object overlap checked and ruled out; region gazetteer is real but narrow

**Context:** before building any part of task 2.C (`TENDER_INTELLIGENCE_SPEC.md` §5.3, object graph +
composite triggers), checked whether the two existing task 2.B signal sources already share a real
object to intersect.

**Deviation/assumption:** two findings recorded rather than acted on speculatively:
1. Zero real overlap between all 147 real design/TEO tenders and all 32 real World Bank AZ agency
   names, checked with fuzzy token matching. The two name matches that do exist by direct search
   (`AZƏRSU`, `AZƏRENERJİ`) are tied to World Bank loans closed 19–31 years ago — treating that as a
   composite forecast signal would be misleading, not a real prediction. This path is **not pursued
   further** unless a *fresh* (non-`Closed`, non-`Dropped`) World Bank AZ project with a named agency
   appears in a future capture.
2. `az_region_identity.py`'s `_KNOWN_REGIONS` covers exactly 4 real observed regions (Zaqatala,
   Siyəzən, Lerik, Naxçıvan) — every other real Azerbaijan rayon/city name will canonicalize to `None`
   until it is actually observed in a captured buyer name and added. This is not an exhaustive
   gazetteer and must not be treated as one.

**Consequence that must not be silently dropped:** task 2.C's composite-trigger engine (§5.3's
weak/medium/strong tiers) has no real cross-category object to prove itself against yet. The real
unlock is a second signal source that names the same rayons already seen in eTender's design-tender
data (a regional budget line or decree) — `president.az`/`e-qanun.az` reconnaissance remains open (a
plain `WebFetch` attempt returned no usable page structure; a live-browser-trace attempt, the method
that worked for eTender's own list endpoint, has not been tried).

**Owner follow-up needed:** No, not blocking. This is a sequencing note for whoever picks up task 2.C's
composite-trigger work next, not a decision the owner needs to make now.

## 2026-08-05 — Task 2.B third slice: procurement-plan versions/items unconsumed; found via static analysis, not a live trace

**Context:** owner deprioritized president.az/e-qanun.az reconnaissance and asked for a different
Phase 2 task instead. Chose a third signal source (annual procurement plans, `TENDER_INTELLIGENCE_SPEC.md`
§5.2) since it lives on eTender itself. The real API was found by static analysis of eTender's own
Angular bundle (grepping the minified JS for the component's actual `apiService.get(...)` call) rather
than a live browser trace — the browser extension was unavailable this session. This resolved the
earlier open item about needing "a live browser trace" for future eTender recon: static bundle analysis
is a real, working alternative when the extension isn't available, at least for this Angular app.

**Deviation/assumption:** two real endpoints found and deliberately not consumed:
1. `GET /api/app/{id}/versions` — a procurement plan's real amendment history. This is the literal
   "changes to them" half of `TENDER_INTELLIGENCE_SPEC.md` §5.2's category name; this task only
   ingests the list endpoint (one signal per plan *submission*), not its amendments.
2. `GET /api/app-version/{id}/items` — real planned-purchase line items (`name`, `month`,
   `deliveryAddress`, `deliveryTime`, `eventType`). `deliveryAddress` would very plausibly give better
   region-match precision than `organizationName` alone (some organization names don't name a region at
   all), and `eventType` remains an undecoded numeric code.
Both require one extra API call *per plan* (1413+ plans for 2026 alone) — a real scale/rate concern,
not attempted speculatively in this task.

**Consequence that must not be silently dropped:** a future reader must not assume "procurement-plan
signals" captures amendments or planned-purchase detail — it captures exactly one fact per submission
(who submitted a plan, for which year, when). The real cross-category intersection proven in this task
(`test_real_cross_category_intersection_on_zaqatala`) is based on organization-name region matching
only, which is coarser than what `deliveryAddress`-based matching could achieve later.

**Owner follow-up needed:** No, not blocking. Real future-work items for whoever extends this signal
source or works on task 2.C's composite-trigger detection.

## 2026-08-05 — Task 2.C: composite-trigger tiers and TTL decay remain unbuilt (blocked on TBD-TIS-01/02)

**Context:** `TENDER_INTELLIGENCE_SPEC.md` §5.3's forecast engine needs weak/medium/strong confidence
tiers and TTL-based decay ("frozen" object state) to be the "forecast" the spec describes. Task 2.C
(`docs/superpowers/plans/2026-08-05-phase2-task2c-composite-trigger-intersection.md`) built only the
literal intersection-detection fact (`detect_object_region_intersection`'s `is_composite` boolean +
the real converged `signal_type` set), proven against the one real Zaqatala case.

**Deviation/assumption:** tiers and decay are left unimplemented rather than approximated, because
both require inventing a number for a `TBD-nn` placeholder, which `AGENTS.md` hard ban #2 forbids:
- Tier thresholds (`TBD-TIS-02`): the spec's own text calls its illustrative ~30%/60%/85% figures "a
  shape of the model, not calibrated thresholds", pending a backtest (`P310`) on ≥30 already-published
  tenders. The tier *compositions* it names (e.g. weak = "program line + strategy mention") also
  reference signal categories (decrees, budgets) this project has no source for yet, so there is no
  honest way to map today's signal_type count onto a named tier.
- TTL durations (`TBD-TIS-01`): `ttl_class` on a `Signal` is a label only (e.g. `"procurement_plan"`,
  `"design_phase_tender"`) — no source document supplies a real expiry duration for any of them, so
  "is this chain broken" can't be computed without inventing one.

**Consequence that must not be silently dropped:** `detect_object_region_intersection` currently
reports only a boolean (`is_composite`) and the raw set of converged `signal_type`s — it cannot yet
say *how confident* a forecast is, or whether an old chain should be considered "frozen" rather than
active. Any UI/delivery work (§5.4, task 2.D — the forecast card) that expects a probability or a
freshness state will find neither here; it must not silently invent one either.

**Owner follow-up needed:** Yes, non-blocking for now. `TBD-TIS-01`/`TBD-TIS-02` need the owner's
research/approval gate (real TTL durations per `ttl_class`, and the `P310` backtest against ≥30
already-published tenders) before tiers or decay can be built for real, per PRD §5.7.4/§13's existing
TBD-resolution process.

## 2026-08-05 — `etender.gov.az` confirmed unreachable from GitHub-hosted CI runners (not flaky)

**Context:** GitHub branch protection on `master` was enabled this session (required "Fast gate"/"Full
gate" status checks). The first PR (task 2.C) exposed that `Full gate` had actually been failing on
every push to `master` for several prior commits (`gh run list --branch master` showed 5 consecutive
`failure` runs) — invisible before because nothing blocked on it. All 3 failures were
`TimeoutError: timed out` in `tests/security/test_design_tender_live_fetch.py`,
`tests/security/test_procurement_plan_live_fetch.py`, and
`tests/security/test_ssrf_suite.py::test_P304_legitimate_external_portal_fetches_successfully` — all
three make a real network call to `etender.gov.az`.

**Deviation/assumption:** added a temporary diagnostic CI step (since removed) to isolate DNS vs.
TCP-connect vs. TLS. Real findings, from an actual GitHub Actions runner: DNS resolves fine
(`etender.gov.az` → `5.191.247.17`, confirmed both via `getent` and Python's own resolver — the same
path the app's egress validator uses); a control request to a different real host
(`search.worldbank.org`) completed a full TLS handshake and got a real 200 response, so the runner's
general internet egress works; but both `curl` to `etender.gov.az:443` and a raw TCP connect directly
to the already-resolved IP (`5.191.247.17:443`, bypassing DNS entirely) timed out at the TCP-connect
step, before TLS even started. Conclusion: `etender.gov.az` itself blocks (or blackholes) inbound TCP
connections from GitHub Actions' IP ranges — a common pattern for government/regional sites blocking
cloud-datacenter IP ranges — not a CI flake, not a code bug, and not fixable from this repo's CI
config (a self-hosted runner with network egress from within Azerbaijan would be the only real fix,
not attempted — out of scope for this project's current stage).

**Resolution (owner-approved, "отдельный non-blocking job в том же workflow"):** the 3 affected tests
are marked `@pytest.mark.live_network` (registered in `pyproject.toml`). `Full gate` now runs
`pytest tests/ -q -m "not live_network"` (excludes them, so they can't block merge on a host this
repo's CI genuinely cannot reach). A new `live-fetch` job in `.github/workflows/ci.yml` runs
`pytest tests/ -q -m live_network` informationally — visible in every PR/push, but deliberately not a
required status check, so a real regression in the egress/connector code is still surfaced to anyone
running these locally (or from a network path that can actually reach the host) without permanently
blocking every future PR. `tests/security/test_worldbank_live_fetch.py` (hits `search.worldbank.org`,
confirmed reachable) is unaffected and stays in `Full gate`.

**Consequence that must not be silently dropped:** `live-fetch`'s job will show red on essentially
every PR/push from a GitHub-hosted runner — this is expected and not a signal of a real regression by
itself. A real regression must be checked by running `pytest tests/ -m live_network -v` from a network
path that can actually reach `etender.gov.az` (e.g. locally), not by the CI job's status alone.

**Owner follow-up needed:** No, not blocking — decision already made and applied. If a self-hosted
runner (or any CI environment with real network access to Azerbaijan-hosted government sites) becomes
available later, revisit whether `live-fetch` should be promoted to a required check at that point.

## 2026-08-05 — Tender/Vendor must be separate deployable services (customer requirement missed until now)

**Context:** Development was paused this session (`docs/reports/DEVELOPMENT-PAUSED-2026-08-05.md`) when
the owner recalled a hard customer requirement — Tender and Vendor must operate as fully separate
tools (own process/deployment), communicating only through an API — that had never been recorded
anywhere in this repo or the source documents. Checked against the actual PRD
(`Uniwatch VER2/0_UNIWatch-v2-PRD-v1.0.md`) before assuming this was new: the real PRD v1.1 §2.2
explicitly states the opposite as a non-goal ("Не построить микросервисную архитектуру на старте...
модульный монолит"), and the master-plan/design doc name "microservice overengineering" as a named
risk mitigated by the monolith. So this is not an error in this repo's reading of the PRD — ADR-0001
was derived correctly from the PRD as it stood.

**Deviation/assumption:** Owner confirmed (2026-08-05) this is a genuine new customer requirement,
received after PRD v1.1 was approved, not previously written down anywhere — the PRD itself was
outdated on this point. Owner asked that the PRD be corrected directly (done — see
`Uniwatch VER2/0_UNIWatch-v2-PRD-v1.0.md`, three "Правка 2026-08-05" annotations: header, §2.2 non-goal,
D-ARCH §13.1), while this repo's side (ADR, `docs/CONTEXT.md`) is handled here. Recorded as
**ADR-0006** (`docs/adr/0006-tender-vendor-service-separation.md`), partially superseding ADR-0001 for
the `tender`↔`vendor` boundary only — `decision`/`algorithm`/`platform` are unaffected.

**Scope decided (owner-confirmed, not the heaviest possible interpretation):** "separate
process/deployment communicating via API" — not necessarily separate databases, separate git
repositories, or a full microservices platform (service mesh, service discovery). Concretely:
`apps/api` splits into `apps/api-tender` + `apps/api-vendor` (two FastAPI processes); `packages/contracts`
is promoted from in-process DTOs to a real versioned network API contract for this pair only.
Chosen because `packages/vendor` is still an empty package (no code built against the old
single-process assumption yet) — this is the cheapest possible moment to enforce the boundary, and a
lighter interpretation avoids pre-committing to the still-unresolved `TBD-05` (infra budget) and
`D-HOST` (hosting) questions.

**Consequence that must not be silently dropped:** Database topology (shared PostgreSQL instance vs.
separate DB/schema per service), per-service CI/CD pipelines, and service-to-service auth are
explicitly **not decided** by ADR-0006 — left open, tied to `TBD-05`/`D-HOST`, not invented. Until
those resolve, `apps/api-tender`/`apps/api-vendor` may share one PostgreSQL instance with only
application-layer (not DB-user/schema-level) enforcement of per-service table ownership — a real,
tracked gap. `apps/worker`'s own split (or not) is deferred until real vendor ingestion work starts.
Implementing the `apps/api` split itself (into `apps/api-tender`/`apps/api-vendor`) is **not done by
this entry** — it is the next schedulable task, needs its own plan before code changes.

**Owner follow-up needed:** No further clarification needed to start the `apps/api` split — scope is
decided. `TBD-05`/`D-HOST` still need the owner's research/approval gate before database/hosting
topology can be finalized (unchanged from their pre-existing status in `docs/CONTEXT.md`).

## 2026-08-05 — ADR-0006 implemented: apps/api_tender + apps/api_vendor, real network contract proven

**Context:** ADR-0006's split (recorded above) is now implemented (plan
`docs/superpowers/plans/2026-08-05-apps-api-tender-vendor-split.md`) — `apps/api_tender`/`apps/api_vendor`
are real, separate FastAPI processes with a real network contract (`packages/contracts/vendor_api.py`)
between them, proven both against a mock transport and against the real vendor app end to end.

**Deviation/assumption:** `GET /internal/ping` (the one real vendor endpoint proving the contract
mechanism) is unauthenticated — no `D-IDP`-backed service-to-service auth exists yet, and building one
speculatively for a proof endpoint with no real data would be scope creep beyond ADR-0006's own
explicitly-deferred items.

**Consequence that must not be silently dropped:** any *future* `/internal/*` or vendor-domain endpoint
that carries real data must not copy this endpoint's unauthenticated pattern — it exists only because
this endpoint returns a static, non-sensitive value. Also unchanged from ADR-0006: `apps/api_tender` and
`apps/api_vendor` currently share one PostgreSQL instance with only application-layer table separation —
still open, tied to `TBD-05`/`D-HOST`. `apps/worker` was not touched by this implementation either.

**Owner follow-up needed:** No, not blocking. Real service-to-service auth and database-per-service
topology remain future work once `D-IDP`/`D-HOST`/`TBD-05` resolve.

## 2026-08-06 — Task 2.D: forecast card is an evidence chain gated on `is_composite`, not a real probability

**Context:** `TENDER_INTELLIGENCE_SPEC.md` §5.4 (`P311`) specifies a forecast card gated on a ≥50%
calibrated probability, with three probabilities (publish at all / in window / commercial
attractiveness), a publication window, and a Next Best Action. Task 2.D
(`docs/superpowers/plans/2026-08-05-phase2-task2d-forecast-card.md`) built only the real
evidence-chain assembly (`packages/tender/forecast_card.py`, `signals_store.build_object_region_forecast_card`),
gated on `is_composite` (task 2.C) instead.

**Deviation/assumption:** `is_composite` — a real, non-fabricated boolean — substitutes for the spec's
literal probability threshold, because no calibrated model exists (`TBD-TIS-02`) and none should be
invented. Three probabilities, publication window, and Next Best Action are omitted entirely, not
stubbed with a placeholder. `budget_estimate` and the evidence chain's "links" are real but
incomplete: only `donor_pipeline_project` signals carry a monetary field (`total_amount_usd_text`) or a
real URL; `design_tender`/`procurement_plan` signals carry neither — for those, `budget_estimate` is
honestly `None` and each evidence entry's real, always-present "link" surrogate is its `raw_snapshot_id`,
not a guessed URL. This is every real object found so far (Zaqatala included).

**Consequence that must not be silently dropped:** a card produced by `build_object_region_forecast_card`
is NOT the calibrated forecast §5.4 describes — it is a real evidence-chain view gated on a cruder,
honest proxy. Any future UI/delivery work (§5.4's own "доставка" half, still unbuilt — weekly digest,
urgent alert) must not present this card as if it carries a real confidence percentage or a real
publication-window estimate — neither exists yet.

**Owner follow-up needed:** Yes, non-blocking. `TBD-TIS-01`/`TBD-TIS-02` still need the owner's
research/approval gate before real probabilities/tiers/windows can replace the `is_composite` proxy;
weekly digest/alert delivery remains a separate, unscoped future task.

## 2026-08-06 — Task 3.A: vendor synthetic sandbox — first slice only (1 provider, 2/7 adverse cases)

**Context:** `TENDER_INTELLIGENCE_SPEC.md` §6.1 / PRD `FR-VND-01..06,09` specify the full vendor
synthetic sandbox: at least 2 providers, all 7 adverse cases (stale offer, mixed UOM, MOQ conflict,
currency/VAT mismatch, capacity shortfall, expiring evidence, partial fulfillment), and tenant isolation
tests at route/service/database levels. Task 3.A
(`docs/superpowers/plans/2026-08-06-phase3-task3a-vendor-synthetic-sandbox.md`) built one provider
(`SyntheticProvider`), 2 adverse cases (`stale_offer`, `moq_conflict`), and database-level isolation only.

**Deviation/assumption:** No real vendor inputs (photos, voice notes, ERP/folder access) exist in this
session, so `FR-VND-01`'s actual "napkin ingestion" (OCR/ASR pipeline over real Unico supplier
artifacts) could not start — the owner chose to build the synthetic-sandbox engine first instead,
explicitly allowed to run before/parallel to real ingestion per `TENDER_INTELLIGENCE_SPEC.md` §6's own
text. Scope was further trimmed to a first slice (1 provider, 2 adverse cases, DB-only isolation) rather
than the full `FR-VND-01..06,09` bar, matching this project's established incremental-slice discipline
(same treatment task 2.C gave weak/medium/strong tiers).

**Consequence that must not be silently dropped:** `SyntheticProvider` alone does not satisfy
`FR-VND-04`'s "minimum two providers" phase-level requirement — a second provider (e.g. CSV) is real,
unbuilt future work. The 5 un-covered adverse cases (mixed UOM, currency/VAT mismatch, capacity
shortfall, expiring evidence, partial fulfillment) are real gaps, not silently assumed handled — any
future SCG/matching code (task 3.D) must not assume full adverse-case coverage exists yet.
Route/service-level tenant isolation (`FR-VND-09`) remains unbuilt until a real vendor HTTP API exists
beyond `apps/api_vendor`'s existing `/internal/ping` proof endpoint (ADR-0006).

**Owner follow-up needed:** No, not blocking — the trimmed scope was the owner's own choice. Real
vendor inputs and the OCR/ASR tooling choice for actual napkin ingestion, the second provider, the
remaining adverse cases, and route-level isolation are all open future work, not urgent.

## 2026-08-06 — `FR-VND-03` "represented" half done (7/7); "handled by an explicit decision" half is not

**Context:** Follow-up to task 3.A. `SyntheticProvider` now represents all 7 of `FR-VND-03`'s named
adverse cases (`stale_offer`, `moq_conflict`, `mixed_uom`, `currency_vat_mismatch`,
`capacity_shortfall`, `expiring_evidence`, `partial_fulfillment`), up from 2.

**Deviation/assumption:** `FR-VND-03`'s full acceptance criterion is "каждый случай представлен и
обрабатывается решением явно" — represented AND handled by an explicit decision. Only the
"represented" half is done. No code anywhere yet reads an `Offer.adverse_case` label and reacts to it
(e.g. excluding a `stale_offer` from a match, discounting a `capacity_shortfall` vendor's availability
status) — that decision logic belongs to task 3.C (Executable Availability, `INV-19` reputation
weighting) and 3.D (BOQ↔SCG matching), neither started yet.

**Consequence that must not be silently dropped:** Do not report `FR-VND-03` as fully closed in any
future exit-gate/phase-summary — only the generator's representation half is real; the "decision" half
is a genuine gap until 3.C/3.D exist. `FR-VND-04`'s second-provider requirement and `FR-VND-09`'s
route/service isolation (recorded in task 3.A's own prior entry) are unaffected by this task, still open.

**Owner follow-up needed:** No, not blocking. 3.C/3.D are the natural next Phase 3 work whenever the
owner wants to pursue the "decision" half of `FR-VND-03` for real.

## 2026-08-06 — `FR-VND-04` satisfied (2 providers): synthetic + CSV; CSV schema is invented, not real

**Context:** `FR-VND-04` requires "минимум два провайдера в Phase 3." `CsvProvider`
(`packages/vendor/csv_provider.py`) is now the second, alongside `SyntheticProvider`.

**Deviation/assumption:** `CsvProvider`'s 12-column CSV schema
(`vendor_name,material,price,currency,vat_rate,uom,uom_canonical_qty,moq,capacity,inventory,valid_from,valid_until`)
is this task's own invention — no real vendor CSV export exists in this session to base it on. Also:
`SupplyProvider`'s contract was changed (`seed` moved off the shared `generate()` method into
`SyntheticProvider.__init__`) because the original shape was accidentally synthetic-specific — a real
design correction, not a cosmetic rename.

**Consequence that must not be silently dropped:** When a real vendor CSV export is eventually
available (whenever real vendor onboarding starts), its actual column names/order/shape may not match
`CsvProvider`'s invented schema — `CsvProvider` may need real changes then, not assumed to already fit.
Anyone building a third provider (ERP/API/portal) should follow `SupplyProvider`'s current shape
(`generate(self, *, as_of: str)`, provider-specific config in `__init__`), not the old
`generate(seed, as_of)` shape task 3.A originally shipped.

**Owner follow-up needed:** No, not blocking. Revisit `CsvProvider`'s schema once a real vendor CSV
sample exists.

## 2026-08-06 — `FR-VND-09` closed for Phase 3: PRD-vs-PLAN-MISSION doc drift resolved in favor of the PRD

**Context:** Before starting this task, `docs/reports/PLAN-MISSION-3.md` and
`docs/reports/PLAN-MISSION-7.md` both scoped `FR-VND-09` (route/service/database tenant isolation
tests, PRD §5.5 line 323, P0) to Phase 7 only — `OPEN-QUESTIONS.md`'s own prior entries (task 3.A,
2026-08-06) repeated that framing twice. A targeted re-read of the source PRD
(`Uniwatch VER2/0_UNIWatch-v2-PRD-v1.0.md` §10.1 roadmap table, line 581) found that the PRD itself
lists `FR-VND-01..06, 09` under **Phase 3's** exit criteria, not Phase 7's (Phase 7's row, line 585,
lists only `FR-VND-07,08` + `NFR-PRV-01..04`). No `PLAN-MISSION-{1..8}.md` document other than
PLAN-MISSION-7 ever mentions `FR-VND-09`. Per `AGENTS.md` §1's conflict rule ("on conflict, the
source documents win and this file must be corrected in the same change") and the owner's explicit
direction this session ("build it now, PRD wins"), `FR-VND-09` is built now, in Phase 3.

**Deviation/assumption:** The identity mechanism used to prove route-level isolation
(`apps/api_vendor/deps.py::get_current_vendor_id`, a server-issued per-vendor API key stored in the
new `vendors.api_key` column, migration `0010`) is a Phase-3, sandbox-only credential scheme —
**not** a resolution of `D-IDP` (the pilot's internal human-user identity provider decision, still
open) and not a claim that Phase 7's real vendor onboarding will keep using it (Phase 7's own
onboarding state machine, `PLAN-MISSION-7.md` §7.B, has a separate "invitation → identity/tenant
isolation" step that may need a genuinely different flow, e.g. real credential issuance during
onboarding rather than at synthetic-generation time). Postgres Row-Level Security (a defense-in-depth
mechanism beyond correct application-level `WHERE vendor_id = ...` scoping) was considered and
deliberately not built — no other table in this codebase uses RLS yet, and the PRD's own wording only
asks for tests "at the route, service, and database levels", not a specific enforcement mechanism per
level.

**Consequence that must not be silently dropped:** `docs/reports/PLAN-MISSION-3.md` still does not
list `FR-VND-09` under task 3.B's table (only `FR-VND-06`/`NEG-04` synthetic-vs-production isolation)
— it should eventually be corrected to match the PRD so a future session reading only the mission
plan doesn't re-derive this same conflict from scratch. Not fixed in this task (out of this task's own
scope, which was the code + tests, not a plan-doc rewrite) — flagged here as a real follow-up, not
silently left stale. Real vendor onboarding (Phase 7) may still need its own, different identity
mechanism; this task's API-key scheme should not be assumed to survive that gate unchanged.

**Owner follow-up needed:** No, not blocking. Two non-urgent follow-ups recorded: (1) correct
`PLAN-MISSION-3.md`'s task 3.B table to list `FR-VND-09`, (2) when Phase 7 real vendor onboarding
starts, re-evaluate whether this API-key mechanism carries forward or is replaced.

## 2026-08-06 — New open decision `D-VND-REP`: reputation trust-coefficient formula unresolved

**Context:** Phase 3, task 3.B (SCG) — `TENDER_INTELLIGENCE_SPEC.md` §6.2's reputation layer
(`ReputationFact` domain model, deterministic synthetic generator, DB-enforced storage with TTL
expiry). Note: this is a *different* task 3.B than the one closed just above — that entry's 3.B was
`PLAN-MISSION-3.md`'s own numbering (tenant isolation); this one is `TENDER_INTELLIGENCE_SPEC.md`
§6's numbering (reputation layer), which this repo has been tracking against since task 3.A (see
that entry's own doc-drift note). Two different documents both use "3.B" for different content —
recorded here explicitly so a future reader isn't confused by the same label meaning two things.

**Deviation/assumption:** `INV-19` states reputation is "a trust coefficient through which every
availability status and every SCG price passes" (§6.2). No source document (PRD, master plan,
`TENDER_INTELLIGENCE_SPEC.md`) supplies the actual formula that collapses a vendor's
`ReputationFact` history into that coefficient. Since `INV-19` explicitly ties the coefficient to
SCG *prices*, inventing a formula now would mean inventing a financial-adjacent number — the same
category `AGENTS.md` §2's hard ban #2 covers for `TBD-nn`/`D-*` items, even though no existing
`TBD-nn` tag currently names this specific gap. This task therefore built only the raw-fact layer
(model, generator, storage, TTL expiry) and left the coefficient formula unresolved — recorded as a
**new** open decision, `D-VND-REP`, rather than silently picking a heuristic.

**Consequence that must not be silently dropped:** `D-VND-REP` blocks only the *numeric* half of
tasks 3.C (Executable Availability, §6.3) and 3.D (BOQ↔SCG matching, §6.4) — both explicitly name
`INV-19`. Neither task is blocked from *starting*: both can consume raw `ReputationFact` rows
directly (e.g. counting negative events per vendor) without a collapsed coefficient, same
incremental-slice discipline already used elsewhere in this phase (e.g. task 2.D's `is_composite`
proxy for the still-open `TBD-TIS-01`/`TBD-TIS-02`). Two further gaps recorded, not silently
approximated: (1) `ReputationFact`'s TTL implements a plain `observed_at + ttl_days` expiry, not
§6.2's "TTL resets on vendor ownership change" — `packages/vendor` has no ownership/parent-entity
concept on `Vendor` at all yet; (2) this task's `ReputationFact` only models `vendor_ref`-scoped
facts — §8's entity definition also allows `object_ref`-scoped facts (e.g. customer reputation for
Phase 4's Go/No-Go, §7.1's "репутация заказчика"), which is out of scope here and would be a
separate future task if/when Phase 4 needs it.

**Owner follow-up needed:** Yes, non-blocking for now. `D-VND-REP` (the reputation-coefficient
formula) needs an explicit research/approval gate before 3.C/3.D can compute a real weighted
availability status or TCO risk-reserve term — tracked the same way `D-TAX` tracks the UOM/FX/VAT
coefficient gap for this phase.

## 2026-08-06 — Task 3.D matching heuristics and TCO scope

**Context:** Task 3.D (`TENDER_INTELLIGENCE_SPEC.md` §6.4, BOQ↔SCG matching, `INV-19`, `P315`).

**Deviation/assumption:** Three gaps recorded, not silently approximated:
1. **Material matching** (`BoqLine.description` vs. `Offer.material`) uses a case-insensitive
   substring heuristic — no source document supplies a real entity-matching/NLP algorithm, and this
   is the same deterministic-heuristic discipline `boq_line_model.py`'s spec-requirement regexes
   already use.
2. **Volume sufficiency** only compares `Offer.inventory` (on-hand stock) against `BoqLine.qty`, and
   only when both sides' units canonicalize to the same value via the existing `canonicalize_unit()`.
   `Offer.capacity` (a production *rate*) is not used, because comparing a rate to a flat quantity
   needs a delivery window `BoqLine` does not carry. An unmapped/mismatched unit is its own explicit
   `volume_status`, never folded into a false match or false non-match.
3. **TCO** (`price + logistics + financing + insurance + risk_reserve(репутация)`, §6.4) is computed
   as `base_price_with_vat` only. `risk_reserve` is exactly `D-VND-REP`'s still-open coefficient;
   `logistics`/`financing`/`insurance` have no source-supplied formula either and no existing
   `TBD-nn` tag names them yet. `TcoEstimate.status` is always `"partial_price_only"` so no caller can
   mistake this for a complete TCO ranking.

**Source conflict (if any):** None — the source spec names the full TCO formula and the
"who can guarantee delivery" ordering, but supplies no algorithm for either the entity match or the
financial weights.

**Owner follow-up needed:** Yes, non-blocking. A real material/spec-matching algorithm and the
logistics/financing/insurance weights need their own research/approval gate before `3.D`'s traffic
light and TCO ranking can be trusted as anything beyond a first-pass heuristic. Tracked alongside
`D-VND-REP` — no new `D-*`/`TBD-*` ID is minted here since both gaps are sub-parts of the same
"SCG pricing/matching needs an approved formula" question `D-VND-REP` already opened.

## 2026-08-06 — Task 3.D final-review fixes and remaining deferred gaps

**Context:** Final whole-branch review of task 3.D (`TENDER_INTELLIGENCE_SPEC.md` §6.4), after all 6 per-task reviews passed individually. The final review ran the feature against `packages/vendor/synthetic_provider.py`'s real generator output for the first time and found several cross-component bugs no single task's diff could reveal — fixed in this same commit: VAT-rate convention (percent vs fraction), cross-currency price ranking, dropped `adverse_case` field, and a `uom="ton"` canonicalization gap. See `packages/decision/matching.py`'s module docstring for the fixed behavior.

**Deviation/assumption:** Three further gaps the final review raised are deliberately deferred, not fixed in this pass, and recorded here rather than silently dropped:
1. **`moq` (minimum order quantity) is not checked.** A vendor whose `moq` exceeds the BOQ line's `qty` can still be classified `sufficient` — in real procurement this usually just means paying for excess, not a hard executability block, but no source document confirms this interpretation, so encoding a MOQ-blocks-executability rule now would risk inventing a business rule rather than reading one.
2. **`GET /internal/offers` has no pagination**, despite `CLAUDE.md`'s explicit rule to apply `packages/platform/pagination.py` to any new listing endpoint. Deferred because the only current caller base (synthetic sandbox, single realm) is small; a real fix needs the client (`packages/contracts/vendor_api.py::list_vendor_offers`) to handle cursor pages too, which is more than a one-file change.
3. **`summarize_boq_matches` raises a bare `KeyError`** if `matches` is missing an entry for a `"normal"`-type, non-`None`-amount `BoqLine`. This is judged intentional fail-fast behavior for a caller-contract violation (the caller is expected to have run `match_boq_line` for every normal line), not a hard-ban-#3 "silent fallback" — a loud crash surfaces the problem, it doesn't hide it. Revisit if a real caller makes this a frequent footgun.

**Source conflict (if any):** None.

**Owner follow-up needed:** No new `D-*`/`TBD-*` ID needed — none of these three are financial-weight or numeric-threshold questions; they're implementation-completeness gaps tracked here for visibility, same discipline as the matching-heuristics entry above.

## 2026-08-06 — Task 3.D final-review fix wave: re-review findings

**Context:** Scoped re-review of the final-review fix wave above (commit range `47af925..55d854a`). All 12 fixes verified present and correct; the re-review surfaced two further gaps in the fix wave itself, adjudicated here rather than triggering a second fix wave (`subagent-driven-development`'s Final Review section: one fix wave, one scoped re-review, no second wave — residual non-load-bearing findings are recorded, not fixed).

**Deviation/assumption:** Two gaps, both judged real but non-blocking:
1. **`BoqMatchSummary` has no `non_matchable_amount`.** The fix wave added `non_matchable_line_count: int` for lines whose `line_type != "normal"`, but only a line *count*, not the money those lines represent. A summary whose whole purpose is "X%/Y%/Z% by money" (P315) currently makes a non-matchable line's amount invisible rather than surfacing it in its own bucket — closer to hard ban #3's "hidden" than its "surfaced" side, though it doesn't corrupt the percentages that *are* computed (green/yellow/red still sum correctly against `total_priced_amount`). No later task in this plan builds on the missing field, so this is deferred rather than blocking. Fix, if picked up later: accumulate `boq_line.amount` (when not `None`) into a new `non_matchable_amount: Decimal` field inside the existing `line_type != "normal"` branch of `summarize_boq_matches`.
2. **`_volume_status`'s `adverse_case` check runs before the quantity-sufficiency check.** This is exactly what the fix wave was asked to do (an adverse-flagged offer must never be silently scored as a clean match), but it has a real, previously-unstated consequence: an offer that is *both* adverse-flagged *and* short of the required quantity (e.g. `partial_fulfillment`, whose `inventory` is well under a large BOQ `qty`) now classifies `"adverse_case"` rather than `"insufficient"` — which counts as an existing (if flagged) source for traffic-light purposes, softening what would otherwise be a red line to yellow. Recorded as an accepted, understood design consequence, not a defect — FR-VND-03's "handled by an explicit decision" framing is closer to "flag for human review" than "silently prove absent," which yellow (not red) better reflects.

Also noted, not actioned: the re-review flagged `test_all_seven_adverse_case_offers_are_excluded_from_ranked_executable` (in `tests/unit/test_matching_against_synthetic_provider.py`) as asserting less than its name implies — it proves no non-`"sufficient"` candidate leaks into `ranked_executable`, but not that all seven FR-VND-03 cases were exercised (only one of the seven adverse offers even material-matches the test's chosen BOQ line). Test-quality gap, not a runtime defect; the test still meaningfully guards against a ranking leak.

**Source conflict (if any):** None.

**Owner follow-up needed:** No new `D-*`/`TBD-*` ID needed — same reasoning as the entry above.

## 2026-08-07 — Closed both cheap follow-ups from the task 3.D final-review fix wave

**Context:** The two gaps the 2026-08-06 "final-review fix wave: re-review findings" entry above recorded as "cheap follow-ups if picked up incidentally by later work" — picked up now, incidentally, rather than as their own scheduled task.

**Resolved:**
1. **`BoqMatchSummary` now has `non_matchable_amount: Decimal`.** `summarize_boq_matches` sums `boq_line.amount` (when not `None`) for every non-`"normal"`-type line into this new field, inside the same branch that already increments `non_matchable_line_count`. A non-matchable line that is *also* unpriced contributes to the line count but not the amount — its money is honestly absent, not zero, same reasoning `unpriced_line_count` already applies to matchable lines. `green_pct`/`yellow_pct`/`red_pct` are unaffected (still divide by `total_priced_amount`, which never included non-matchable lines).
2. **`MatchCandidate` now carries `adverse_case: str | None`.** `classify_candidate` passes `offer.adverse_case` straight through, alongside the existing `volume_status == "adverse_case"` label. A human reviewing a flagged line can now tell *which* of FR-VND-03's seven sub-types it was without a separate lookup back to the raw offer.

Neither change touches `_traffic_light`/`rank_executable_candidates_by_tco`'s decision logic — both are additive, read-only fields/sums layered on top of already-correct behavior confirmed by the prior re-review.

**Source conflict (if any):** None.

**Owner follow-up needed:** No — both items are now closed.

## 2026-08-07 — Task 3.C (Executable Availability): built the raw+effective status layer, deliberately not wired into 3.D's matching

**Context:** Phase 3, task 3.C (`TENDER_INTELLIGENCE_SPEC.md` §6.3, P314). **Numbering note, same pattern as task 3.B's two entries above:** `PLAN-MISSION-3.md`'s own "3.C" names something unrelated (a synthetic-generator tooling task); this entry tracks `TENDER_INTELLIGENCE_SPEC.md`'s §6's "3.C" (Executable Availability), which is what `docs/reports/WORKLOG.md`'s task-3.D entries already forward-referenced as "natural next Phase 3 work."

**Deviation/assumption:** Two gaps recorded, not silently approximated:
1. **Only the qualitative half of `INV-19` is implemented.** `packages/vendor/availability_model.py::effective_executable_status()` applies exactly the one rule `TENDER_INTELLIGENCE_SPEC.md` §6.3 states in words ("Reserved у ненадёжного ≈ Confirmed у надёжного" — a one-tier downgrade when the vendor carries a negative `ReputationFact`) and nothing more: no symmetric upgrade for positive reputation (no source document states one), and no numeric trust coefficient (`D-VND-REP` is still open, per the earlier 2026-08-06 entry, which already anticipated this: "both tasks can consume raw `ReputationFact` rows directly... without a collapsed coefficient"). `unknown` has no lower tier and stays `unknown` under a negative reputation.
2. **Not wired into `packages/decision/matching.py`.** Task 3.D's `_traffic_light`/`rank_executable_candidates_by_tco` still use their own narrower proxy (`volume_status == "sufficient"` + `freshness == "fresh"`) rather than the new graduated `effective_executable_status`. This is a deliberate scope boundary, not an oversight: it mirrors task 3.B's own precedent (the reputation-fact layer was built and proven standalone before 3.D consumed it in a later, separate step), and it protects 3.D's already-final-reviewed, closed logic from picking up regression risk inside this task's diff. The new field is available end-to-end (raw `Offer.executable_status` → `vendor_offers.executable_status` column → `GET /internal/offers`'s `executable_status`/`effective_executable_status` → `VendorOfferDTO`), so 3.D (or a dedicated follow-up) can consume it without another schema/contract change.

**Source conflict (if any):** None — the spec names the four tiers and the one qualitative reputation example; it does not name the coefficient formula or mandate that 3.C rewire 3.D's already-closed matching logic in the same task.

**Owner follow-up needed:** Yes, non-blocking. Two follow-ups, both deferred rather than decided silently: (a) whether/when to replace `matching.py`'s `volume_status`+`freshness` executability proxy with `effective_executable_status` — a real design change to already-reviewed code, better done as its own scoped task with its own test-suite pass, not folded into this one; (b) `D-VND-REP`'s numeric coefficient, unchanged from the 2026-08-06 entry, still needed before any TCO `risk_reserve(reputation)` term or a symmetric upgrade rule can be justified as anything but invented.

**Follow-up (a) closed 2026-08-07** — see the entry immediately below.

## 2026-08-07 — Task 3.C follow-up: wired `effective_executable_status` into 3.D's matching

**Context:** Closes follow-up (a) from the entry directly above. `packages/decision/matching.py` (task 3.D) previously gated green/`ranked_executable` on `volume_status == "sufficient" and freshness == "fresh"` only — never looking at the Executable Availability status this task added. `TENDER_INTELLIGENCE_SPEC.md` §6.4 step 1 asks "who can **guaranteed**ly deliver" (`гарантированно`), which an unverified vendor claim (`reported`/`unknown`) does not satisfy on its own, however fresh or well-priced.

**Deviation/assumption:** None beyond what's already recorded above — this is the planned follow-up itself, not a new gap. One design choice worth naming: `_is_strong_source()` (new helper, used by both `_traffic_light` and `rank_executable_candidates_by_tco`) only *tightens* the existing gate, never loosens it — a `reported`/`unknown` source still counts as "a source exists" (never flips a line to red on its own, same treatment as an adverse-case offer already got in task 3.D), it just can never be one of the ≥2 strong sources green requires, and never enters `ranked_executable`. No existing task-3.D test needed to change: the test factory's `executable_status` default (`"confirmed"`) keeps every pre-existing fixture "strong" under the new gate.

**Source conflict (if any):** None.

## 2026-08-08 — Phase 3 closeout: pagination, shared contract test, MOQ visibility, and real napkin-ingestion (OCR half) closed; `D-VND-REP` and ASR remain the only genuinely open items

**Context:** Following the 2026-08-08 Exit gate Phase 3 write-up (`docs/reports/WORKLOG.md`), the owner asked to close out every remaining open item feasible without inventing a number, and specifically authorized using Baidu's "Unlimited-OCR" (a real, public, Apache-2.0 3B-parameter local VLM, runnable via Ollama/vLLM/llama.cpp per its own README) as the OCR backend for task 3.A's "napkin ingestion" (`FR-VND-01`, P312).

**Closed this session:**
1. **`GET /internal/offers` pagination** (deferred gap from the 2026-08-06 final-review entry) — cursor pagination added end to end: `vendor_store.list_offers_with_vendor_name_by_data_realm` (after_id/limit), the route (`cursor`/`limit`/`next_cursor`), and `packages/contracts/vendor_api.py::list_vendor_offers` (follows every page internally, same as before from the caller's perspective). Real multi-page integration test proves page-boundary correctness (no gaps/dupes), not just that a `next_cursor` field exists.
2. **Shared `SupplyProvider` contract test** (gap found during the 2026-08-08 exit-gate review) — `tests/unit/test_supply_provider_contract.py` runs `SyntheticProvider`, `CsvProvider`, and the new `NapkinOcrProvider` through one identical assertion set (shape, realm/watermark pairing, non-empty evidence_source, valid executable_status, seed/input determinism), closing `PLAN-MISSION-3.md` §4's "два разных fake provider удовлетворяют контракту" criterion with a real shared suite rather than two independently-written ones.
3. **MOQ visibility** — `MatchCandidate.moq_exceeds_qty` (packages/decision/matching.py) surfaces `offer.moq > boq_line.qty` (only when units are comparable) as a visible field. Deliberately **non-gating**: it never changes `volume_status`, `_is_strong_source`, or the traffic light — no source document confirms MOQ should block executability (in real procurement it usually just means paying for excess), so this surfaces the fact (hard ban #3) without inventing the business rule about what it means.
4. **Real napkin ingestion, OCR/photo half** (`FR-VND-01`, P312/P313) — previously entirely unbuilt (2026-08-06 entry: "the actual napkin ingestion... still needs real vendor inputs the owner hasn't supplied"). Built:
   - `packages/vendor/ocr_engine.py` — `OcrEngine` Protocol + `OcrEngineError`, same provider-agnostic discipline as `provider_contract.py`.
   - `packages/vendor/ollama_ocr_engine.py` — real client against Ollama's own stable `/api/generate` multimodal endpoint (`images` as base64, `stream: false`).
   - `packages/vendor/napkin_evidence.py` + `migrations/0013_vendor_napkin_evidence.sql` — immutable, checksummed raw photo/voice bytes (`vendor_napkin_evidence`), same DM-02/DM-03 discipline as `packages/tender/raw_snapshot.py`, kept as a separate table/module (not a cross-import) per the tender/vendor domain boundary.
   - `packages/vendor/napkin_provider.py` — `NapkinOcrProvider` (`SupplyProvider`-conformant), `executable_status="reported"` (same reasoning as `csv_provider.py`: an OCR'd photo is an unverified vendor claim).
   - Unit tests with a fake `OcrEngine` (parsing/atoms mechanism) and a fake HTTP transport (real Ollama wiring), plus a real-Postgres end-to-end integration test (photo bytes → evidence row → parsed offer → DB round-trip).

**Deviation/assumption — recorded, not silently smoothed over:**
1. **The exact Ollama registry tag for Unlimited-OCR is unconfirmed.** This session ran `ollama pull unlimited-ocr` and `ollama pull baidu/unlimited-ocr` against a real local Ollama 0.32.5 instance; both failed with `Error: pull model manifest: file does not exist`. The model's own GitHub README documents Ollama/vLLM/llama.cpp support in prose but gives no concrete pull command or model tag. `OllamaOcrEngine` is therefore built generic against any Ollama-served vision model, with `ocr_model_name` (`packages/vendor/ocr_settings.py`) a **required** setting with no guessed default — whoever pulls real weights under a tag that resolves in their own environment configures it explicitly. No live end-to-end run against the real Unlimited-OCR model has happened in this session; all proof is against a fake engine/fake HTTP transport.
2. **No real napkin photo exists.** The owner still hasn't supplied a real vendor artifact. The JSON extraction schema `napkin_provider.py`'s parser expects (`NAPKIN_EXTRACTION_PROMPT`) is this task's own invention, same honest limitation `csv_provider.py`'s own 12-column CSV schema already carries — a real, testable mechanism, not a claim it has been validated against a real vendor's actual napkin.
3. **ASR (voice) is untouched.** The owner's instruction named OCR/photo specifically ("unlimitedocr"); voice-note ingestion needs its own, separate tech choice and is not addressed by this entry. P313's worked example ("голосовое «кинули по срокам...»") still has no real voice-input mechanism — only the downstream `ReputationFact`/`effective_executable_status` mechanism it would feed (built 2026-08-06/07) exists.
4. **`NapkinOcrProvider` can produce `vendor-production`/`REAL` data**, unlike every other provider in this package — a deliberate reading of Phase 3's own header deviation (already recorded 2026-08-04: real ingestion of Unico QSC's already-known vendors was moved into Phase 3 without a separate legal gate, precisely because it isn't new-supplier discovery). The caller must state `data_realm`/`watermark` explicitly per capture (validated at construction against the two valid pairings); no code path in this session has actually invoked it that way, since no real photo exists yet.
5. **`D-VND-REP` (reputation trust-coefficient) and its TCO sibling gaps (`logistics`/`financing`/`insurance` weights, real material/spec-matching algorithm) remain open, unchanged.** These are financial-adjacent numbers/algorithms with no source-supplied formula — inventing them would violate `AGENTS.md` hard ban #2, regardless of how much of the rest of Phase 3 closes around them. This is the one item "finish P3 fully" genuinely cannot mean closing.

**Source conflict (if any):** None.

**Owner follow-up needed:** Yes, non-blocking for Phase 4. (a) Confirm/pull the actual Unlimited-OCR weights under whichever tag resolves (Ollama/vLLM/llama.cpp) and set `OCR_MODEL_NAME`/`OLLAMA_BASE_URL` for a real live-fire test — until then this mechanism is proven honest but not proven against the real model. (b) Supply a real napkin photo to validate `NAPKIN_EXTRACTION_PROMPT`'s invented schema against real model output (it may need revision once real output is seen — same spirit as Phase 1's eTender contracts being rebuilt from real captures, not assumed). (c) Pick an ASR tech choice when voice-note ingestion is prioritized. (d) `D-VND-REP` and its TCO/matching-algorithm siblings, unchanged from 2026-08-06 — still need an explicit research/approval gate.

## 2026-08-08 — OCR/ASR backend research: PaddleOCR-VL 1.6 recommended over Unlimited-OCR, not yet adopted

**Context:** After the entry above recorded Unlimited-OCR's Ollama support as unconfirmed, the owner asked for a fuller survey of open-source/free OCR (and ASR) options before committing to one. This is a research record only — no code changed in this entry, `OllamaOcrEngine`/`OcrSettings` are unchanged, still generic against any Ollama-served vision model.

**Findings (verified against first-party sources, not just SEO blog summaries — several "how-to" pages found for PaddleOCR-VL read as low-quality programmatic content and were treated with skepticism):**
- **PaddleOCR-VL 1.6** (Baidu, ~0.9–1.3B params, Apache 2.0): tops the open-model OmniDocBench leaderboard (96.33, vendor-reported/unverified) despite being far smaller than Unlimited-OCR (3B) or Qwen2.5-VL. `ollama/ollama#12685` (GitHub, closed 2026-07-05 by maintainer `dhiltgen`) confirms the underlying llama.cpp architecture support merged Feb 2026 (`ggml-org/llama.cpp#18825`) and gives a working recipe: `hf download PaddlePaddle/PaddleOCR-VL-1.6-GGUF --local-dir paddleocr-vl16 --include "*.gguf"` then `ollama create`/`ollama run` from that directory. Multiple earlier user reports in the same thread (Jan–May 2026) hit `500 Internal Server Error: unable to load model` using the simpler `ollama pull hf.co/...` shortcut even after llama.cpp support landed — the maintainer's manual-GGUF recipe is the one confirmed working path, not the shortcut.
- **Qwen2.5-VL:7b** (Alibaba, Apache 2.0 — note only 7B/32B are Apache 2.0, 3B/72B are under Qwen's own separate license): official Ollama library tag, one-command pull, mainstream and well-tested, but 6GB (Q4) and general-purpose rather than OCR-specialized.
- **MiniCPM-V:8b**: official Ollama library tag, strong OCRBench claims, 5.5GB.
- **Unlimited-OCR** (already attempted, prior entry): 93.92 OmniDocBench, but no equivalently clean Ollama support path was found — the gap this session already hit firsthand.
- Classic pipelines (Tesseract, PaddleOCR-classic, EasyOCR, Surya) give raw text/layout, not structured JSON — would need hand-written extraction logic on top rather than a single "extract as JSON" prompt, a worse fit for `napkin_provider.py`'s current design.
- **ASR (ties to P313's still-unbuilt voice-note half):** Whisper (MIT) is the standard; `faster-whisper` (MIT, CTranslate2) is the practical choice for CPU-only hardware; `mammadovziya/whisper-az` (GitHub) is a small (51MB) LoRA adapter specifically closing the Azerbaijani accuracy gap on `whisper-small`, directly relevant given real napkin voice notes would be in Azerbaijani. None of this integrates via Ollama (audio, not vision/text) — would need its own `AsrEngine`-style adapter, same shape as `OcrEngine`.

**Hardware context that shaped the recommendation:** the machine used for this work is a laptop with an Intel Arc iGPU (no discrete GPU) and 16GB RAM — favors PaddleOCR-VL's ~1–1.5GB footprint heavily over any 3B+ model.

**Decision:** Owner chose to record this research now and defer both the OCR-engine swap and ASR scoping to a future task — `OllamaOcrEngine`/`OcrSettings` remain unchanged (generic, `OCR_MODEL_NAME` still unset by default) pending that future decision.

**Source conflict (if any):** None.

**Owner follow-up needed:** Yes, non-blocking. When ready: (a) try PaddleOCR-VL 1.6 via the maintainer's confirmed manual-GGUF recipe against this project's `OllamaOcrEngine` (should work unmodified — it's a generic Ollama `/api/generate` client); (b) if it fails to load on the target machine, fall back to `qwen2.5vl:7b` (official tag, higher integration confidence, more resource-hungry); (c) pick an ASR path (`faster-whisper` + `whisper-az` LoRA is the leading candidate) when voice-note ingestion is prioritized.

**Owner follow-up needed:** No — this closes the recorded follow-up. `D-VND-REP`'s numeric coefficient (follow-up (b) above) remains the only open item from task 3.C.

## 2026-08-08 — Task 4.A Decision Core scope

**Context:** Task 4.A (`TENDER_INTELLIGENCE_SPEC.md` §7.1, Decision Core: Go/No-Go → Bid), first task of Phase 4, started on owner GO per the Exit gate Phase 3 record above.

**Deviation/assumption:** Per an explicit owner decision recorded in this session's conversation (not previously in any document): Go/No-Go's qualitative inputs — company profile, qualification, financing, customer reputation, pre-designated-winner suspicion — are captured as **human-entered free text**, not computed. No source document supplies a scoring/weighting formula for any of these, and customer reputation specifically depends on Phase 4.C's Execution Ledger, which does not exist yet. This task only gives the human's own assessment a durable, queryable home (`go_no_go_inputs` table) — it does not attempt to derive or validate a Go/No-Go verdict from that text.

Six further gaps recorded, not silently approximated:
1. **Margin, risk concentration, own-resource-loading** (§7.1's other Bid/No-Bid criteria) are not computed — no source document supplies the company's own cost basis or resource schedule any of these need.
2. **P316's "three probabilities"** are not produced — no calibrated probability source exists; DFE's own `forecast_card.py` already defers this same gap (P311).
3. **INV-20's lock-in is only the identification half** — `lock_in_requirements` flags which BOQ lines need a lock-in and for which vendor, but does not generate an actual LOI/pre-order legal document.
4. **INV-06's No-Go override maker/checker flow** is not built — `no_go` exists as one of five `Decision` types, but a distinct, audited *override* flow for reversing an active No-Go is separate, future scope.
5. **`GET /bid-readiness-candidate` hardcodes `data_realm="vendor-sandbox"`** — the only realm with any data today (ADR-0004). Revisit once `vendor-production` data exists.
6. **Several smaller gaps found during review, all recorded rather than silently fixed or dropped:**
   - `write_audit_log` calls on both mutating routes have no way to capture the actor's `role` alongside `actor` — `packages/platform/audit.py`'s `audit_log` table has no role column; adding one is a platform-wide schema change out of scope for this task, even though ADR-0003 layer 4 names "actor, role, reason, input snapshot" as the ideal.
   - `GET /bid-readiness-candidate` has a write side effect (it stores a new `bid_readiness_candidates` row on every call, including a page refresh) — matches this task's design (each computation is its own point-in-time record) but means unbounded row growth under repeated polling; no retention/pruning policy exists yet.
   - A `Decision` of type `bid`/`conditional_bid` with no `bid_readiness_candidate_id` silently skips lock-in generation — the response's empty `lock_in_requirements: []` is indistinguishable from "analysed, none needed since no line is single-vendor-critical."
   - `GET /bid-readiness-candidate`'s two 404 cases ("tender not found/no version" vs. "tender has a version but zero BOQ lines") both return the same error code `not_found`, distinguishable only by message text.
   - `create_decision`'s `IntegrityError`-to-422 path (a bad `go_no_go_inputs_id`/`bid_readiness_candidate_id`/`tender_id` on `POST /decisions`) has no direct test — Task 5's fix round restored regression coverage for the equivalent path on `POST /go-no-go-inputs` and for the naive-`as_of` case, but not this one. Same code shape, already exercised manually during review; low risk, but recorded rather than silently assumed covered. **Superseded 2026-08-09**: the Final Review's finding C2 (below) replaced the `go_no_go_inputs_id`/`bid_readiness_candidate_id` halves of this gap with explicit, directly-tested upfront validation; only a bad `tender_id` itself still reaches `IntegrityError`, and remains untested by a dedicated case (still low risk, same reasoning).

**Source conflict (if any):** None.

**Owner follow-up needed:** Yes, non-blocking. Items 1-2 need either real historical cost/resource data or an owner research/approval gate before they can be computed without inventing a number — same discipline as `D-VND-REP`. Items 3-4 are scoped, schedulable follow-up tasks, not open research questions. Item 5 resolves automatically once real vendor onboarding (Phase 7) exists. Item 6's five sub-items are all cheap follow-ups if picked up incidentally by later work, not scheduled tasks on their own.

## 2026-08-09 — Task 4.A Final Review findings C1/C2 fixed; one new deferred item (BOQ computation load)

**Context:** the whole-branch Final Review for Task 4.A found two Critical, merge-blocking bugs — see `docs/reports/WORKLOG.md`'s 2026-08-09 entry for the full technical detail. Both are fixed (commit `04678f2`), confirmed by a scoped re-review, and covered by new regression tests. Recorded here because they change facts stated in the entry above:

1. **C1 (fixed):** `list_boq_lines_by_tender_version()` never worked against real eTender ingestion, because `event_details` and each `bom_lines_page` land under structurally different `tenders` identities (see `packages/tender/etender_contract.py`). Replaced by `get_event_id_for_tender()` + `list_boq_lines_by_event()`, which resolve/query the real `(source, event_id)` aggregate key `boq_lines` already exposes.
2. **C2 (fixed):** `POST /decisions` now rejects a `go_no_go_inputs_id`/`bid_readiness_candidate_id` that does not belong to the URL's `tender_id`, before writing anything to the append-only `decisions` table.
3. **New deferred item, found during C1's fix and its re-review:** `GET /bid-readiness-candidate` now does what it was always designed to do — compute against a tender's FULL BOQ (potentially thousands of lines across dozens of pages) synchronously inside an `apps/api_tender` request handler. This risk was previously masked by C1's bug (the query almost always returned zero or one page's worth of lines). Whether this belongs in `apps/worker` instead (per `CLAUDE.md`'s "apps/api_tender ... request/response only" framing) is a genuine architecture question, not something this bug-fix should decide unilaterally.

**Source conflict (if any):** None.

**Owner follow-up needed:** Yes, non-blocking for this merge. Item 3 needs an owner/architecture call on whether `GET /bid-readiness-candidate` should move its computation to `apps/worker` (async job + polling) before real, multi-thousand-line tenders reach it in production — synthetic/sandbox data today makes this low-urgency.

## 2026-08-09 — Task 4.B (post-submission tracking) wired into the worker; two gaps deliberately left open

**Context:** Task 4.B, task 6 (final task of the plan) — `packages/tender/post_submission_tracking_job.py`'s `check_tender_for_changes` (task 5) is now actually dispatched by `apps/worker/main.py`, alongside the pre-existing `example_job` stub type (the first REAL job-type dispatch this worker has ever had). `apps/worker/main.py` also gained `enqueue_due_tender_checks()`, called once per `run_forever` outer-loop iteration, which enqueues a `tender_change_check` job for every tender that (a) has an active `bid`/`conditional_bid` decision (`list_tenders_with_active_bid_decision`, task 4) and (b) is due per `tender_watch_state`'s own last-checked timestamp (`list_tenders_due_for_check`, task 4). `GET /tenders/{tender_id}/recalc-flags` (permission `decision.recalc_flags.read`) exposes `list_unresolved_recalc_flags` (task 3) as a new read-only route on the existing `apps/api_tender/routers/decision.py` router.

**Deviation/assumption:**
1. **`TENDER_WATCH_POLL_INTERVAL_HOURS = 6`** (`apps/worker/main.py`) — no source document (`TENDER_INTELLIGENCE_SPEC.md` §7.2, P317) supplies a re-check cadence for post-submission tracking, only the mechanism itself. This is a plain owner-decision constant, not a `TBD-nn`/`D-nn`-tagged literal, so hard ban #2 does not apply, but it is recorded here per this file's general "every new assumption made during implementation" charter. Revisit if a real cadence requirement surfaces later.
2. **`decision.recalc_flags.read` is a brand-new permission name**, not seeded anywhere in application code (same as every other `decision.*` permission in this codebase — RBAC seeding is a test/ops-time concern, not something `apps/api_tender` inserts at startup). `require_permission`'s deny-by-default resolution means an identity without this exact permission row simply gets 403, same as any other permission — no special-casing needed.

**Two gaps found while scoping this task, deliberately NOT built, recorded rather than silently dropped:**
1. **Q&A/clarifications tracking is not built.** `TENDER_INTELLIGENCE_SPEC.md`'s post-submission tracking framing (§7.2) implies buyer-side Q&A/clarification activity is part of what a bid team would want tracked after submission, alongside the deadline/BOQ-line change detection this task closes. No eTender endpoint for Q&A/clarifications has been captured in any fixture-capture session to date (`fixtures/tender-snapshots/etender/MANIFEST.md`) — this needs the same kind of bounded, real-network discovery session that found the events-list query contract in task 1.A (`docs/decisions/OPEN-QUESTIONS.md`, 2026-08-04 entries) before it can be built without guessing a response shape.
2. **`boq_line_recalc_flags.resolved_at` is never cleared by anything in this codebase.** `store_boq_line_recalc_flag` (task 3) inserts with `resolved_at` implicitly `NULL`, and `list_unresolved_recalc_flags` (task 3, now exposed via this task's new route) filters on `resolved_at IS NULL` — but no process anywhere sets `resolved_at`. A flagged line therefore stays flagged forever, even after a human/system has re-examined it. The presumed future resolution path is re-running `GET /bid-readiness-candidate` for the affected tender once its recalc flags are addressed, but this task does not build that clearing logic — recording it here rather than leaving it as a silent, undiscoverable gap in an append-only table's own contract.

**Source conflict (if any):** None.

**Owner follow-up needed:** Yes, non-blocking. (a) Schedule a fixture-capture session for the Q&A/clarifications endpoint when eTender access is next available. (b) Decide and build the `resolved_at`-clearing mechanism (most likely inside a future `GET /bid-readiness-candidate` recompute path) before recalc flags are relied on operationally as a "needs attention now" signal rather than a permanent historical log.

## 2026-08-11 — Task 4.C (Execution Ledger): five deferred items, recorded post-hoc

**Context:** Task 4.C (Execution Ledger, `TENDER_INTELLIGENCE_SPEC.md` §7.3, P318) was built in `worktree-phase4-task4c-execution-ledger` and merged via PR #22 on 2026-08-11, but its close-out entry never landed in this file or in `WORKLOG.md` — the plan doc (`docs/superpowers/plans/2026-08-10-phase4-task4c-execution-ledger.md`) listed these items under its own "Deferred (record in `docs/decisions/OPEN-QUESTIONS.md` at close-out)" section and that step was skipped. Recorded here now, verbatim in substance from that plan's own list plus the branch's real commits; the paired `WORKLOG.md` entry of the same date carries the implementation summary and the 2 Critical / 4 Important final-review findings.

**Deferred, deliberately NOT built in 4.C:**
1. **Voice-note transcription (ASR) is still an unresolved tech choice** — the same open gap task 3.A's napkin ingestion already recorded (2026-08-08 entries). `execution_napkin_evidence.capture_kind` accepts `'voice'` and stores the raw bytes unconditionally (INV-18: capture must never depend on whether the system currently understands the input), but the submission route does not attempt to parse a `'voice'` capture — it returns `parsed: false` with the evidence id, never a guessed transcript.
2. **The overhead-buffer *application* is not built** — 4.C produces `overhead_buffer_contributions` as a **raw count per deviation category**, never a cost-weighted adjustment. Turning those counts into an actual cost overlay on a new 4.A estimate is Phase 4.D's calibration loop (`TENDER_INTELLIGENCE_SPEC.md` §7.4, P319). Inventing the weighting here would have been a hard ban #2 violation.
3. **`D-VND-REP` (vendor trust-coefficient formula) remains untouched** — 4.C's vendor-reputation feed only appends typed `ReputationFact` rows across the ADR-0006 network boundary, exactly like the existing unweighted `has_positive_reputation`/`has_negative_reputation` booleans it feeds. No score is computed anywhere.
4. **No automatic linkage from `GET /organizations/{voen}/execution-history` back into `GoNoGoInputs.customer_reputation_notes`** — ADR-0005's human-authority model means a human reads the execution history and writes their own assessment; 4.C does not auto-populate that free-text field (hard ban #4: derived data never becomes a human decision).
5. **`TBD-TIS-01` (exact TTL numbers per fact class, INV-17) is still unresolved.** `reputation_ttl_days` on the napkin submission route has no default — a vendor-culprit fact with a mappable `event_type` but no supplied TTL is queued via `exception_queue` for a human to resolve, never posted with a guessed number (hard ban #3). Note the existing `packages/vendor/synthetic_reputation.py` samples an arbitrary TTL; that is acceptable only because it is explicitly `SYNTHETIC` demo data and is **not** a template for a fact stemming from a real field observation. Additionally, no end-to-end integration test drives a real vendor-culprit fact through OCR to a successful reputation post — proven at the unit/contract level only, the same honest gap `packages/vendor`'s own napkin ingestion already has.

**Also inherited, not newly introduced:** `POST /internal/reputation-facts` on `apps/api_vendor` is unauthenticated, the same known, tracked gap as the pre-existing `/internal/offers` and `/internal/ping` — real service-to-service auth across the ADR-0006 boundary is deferred to the still-open `D-IDP`/`D-HOST` decisions.

**Source conflict (if any):** None.

**Owner follow-up needed:** Yes, non-blocking for 4.C's merge (already merged). (a) Choose an ASR backend (still open from Phase 3). (b) `TBD-TIS-01` TTL numbers per fact class need an approved value before real field-observation reputation facts can post without human intervention. (c) `D-VND-REP` unchanged. Items 2 and 4 are by design, not follow-ups: item 2 is 4.D's own scope, item 4 is ADR-0005 working as intended.

## 2026-08-11 — Task 4.C, sixth deferred item: `capture_kind`/`mime_type` are not validated at the API level

**Context:** the 2026-08-11 entry above recorded five deferred 4.C items, reconstructed from the task's plan doc. A sixth was found by the review that merged PR #22 but survived only in an unmerged local branch (`docs-worklog-task4c-closure`, commit `c720aeb`) and so was missing from this file. Recorded here so a known defect is not tracked solely in a branch nobody would look at. The paired `WORKLOG.md` addendum of the same date carries the other two salvaged facts (PR #22's maker/checker approval record, and a caveat about which test run the merge actually relied on).

**Deviation/assumption:** `capture_kind` and `mime_type` on the napkin-capture submission route (`apps/api_tender/routers/execution_ledger.py`) are validated **only** by the `CHECK` constraint in `migrations/0016_execution_ledger.sql` — there is no API-level validation of either field. An invalid value therefore surfaces as a 500 (the database error propagates) rather than a clean 4xx, which breaks the convention every other route in this codebase follows: a malformed request is the caller's error and gets a typed `ApiError` through `packages/platform/errors.py`'s uniform envelope.

This was found during the review that merged PR #22 and deliberately left unfixed in that fix wave, judged non-critical relative to the two Critical and four Important findings addressed there: it is the *shape of the response to garbage input*, not data loss, data corruption, or a silent default. Hard ban #3 is not implicated — nothing is hidden behind a fallback; the request fails loudly, just with the wrong status code and an uninformative message.

**Source conflict (if any):** None. No source document specifies the accepted `capture_kind`/`mime_type` sets beyond what the migration's own `CHECK` already encodes — closing this needs no new decision, only the validation wired at the route boundary against the same values the constraint already names.

**Owner follow-up needed:** No decision needed — this is a straightforward correctness fix (validate at the route against the migration's own allowed values, return 422). Low priority: it affects only malformed requests. Worth folding into whichever task next touches that router.

## 2026-08-12 — Task 4.D (Calibration loop): eight deferred items, plus the task's own two additions to the sourced enums

**Context:** Task 4.D (`TENDER_INTELLIGENCE_SPEC.md` §7.4, P319, last task of Phase 4) built the *measurement substrate* the spec's actual calibration outputs are blocked on — recorded human outcomes/loss reasons, persisted forecast-card snapshots with human-confirmed tender links and measured observation lag, and a read path for the previously write-only overhead buffer — without inventing any weight, TTL, or overlay formula. The paired `WORKLOG.md` entry of the same date carries the implementation summary, commit list, and full gate output. This entry is the plan's own "record every deferred item at close-out" step, carried out verbatim against what was actually built (verified against the branch, not copied blind from the plan).

**Deviation/assumption:**
1. **`TBD-TIS-02` (DFE signal weights, confidence tiers) — unchanged, but now has a path to resolution.** `forecast_card_snapshots`/`forecast_card_tender_links` (Task 3) start retaining `ForecastCard`s with human-confirmed tender identity, which is the missing precondition for §5.3/P310's "≥30 already-published tenders" backtest. No backtest has actually run — zero snapshots exist outside test fixtures as of this entry — so the weights themselves remain exactly as unresolved as before.
2. **`TBD-TIS-01` (numeric TTL per fact class, INV-17) — unchanged, same reasoning.** `ttl_class` (`signal_model.py`) and the loss/outcome tables built in Task 4.D carry no duration anywhere. `observed_lag_days` (Task 3) measures a real elapsed time but is not consumed by anything — accumulating that measurement is the precondition for eventually approving a TTL, not the TTL itself.
3. **The overhead-buffer *cost overlay* is still entirely unbuilt.** `list_overhead_buffer_contributions` (Task 1) and `GET /tenders/{tender_id}/overhead-buffer` (Task 2) make `overhead_buffer_contributions.fact_count` readable for the first time since 4.C introduced the table — but no weighting formula exists to turn those raw per-category counts into an actual adjustment on a new 4.A cost estimate. No source document supplies one.
4. **`cancelled` on `OUTCOME_TYPES` and `other` on `LOSS_REASONS` are this task's own additions to the spec's sourced sets**, not spec literals. §7.4 names `won`/`lost` and exactly three loss categories ("проиграли дешёвому доступу конкурента" / "демпингу" / "«рисунку»") verbatim; `cancelled` and `other` were added because forcing a real cancelled tender into `lost`, or a real loss cause outside the three named categories into one of them, would fabricate a fact and corrupt the very loss-analysis §7.4 exists to enable. `other` requires a mandatory non-empty `note` (enforced in `LossReason.__post_init__` and re-validated at the route boundary) so the honest escape hatch never degrades into a blank. Neither is a `TBD-nn`/`D-nn` substitution — recorded here per this file's standing "record every new assumption" charter, not because either violates a hard ban.
5. **`tenders.created_at` is used as `observed_lag_days`'s `first_observed_at` operand, and it is NOT a publication date.** No captured eTender field supplies a real tender-publication timestamp (`fixtures/tender-snapshots/etender/MANIFEST.md` records no such field on any captured resource); `tenders.created_at` is when this codebase's own ingestion first fetched the tender. Every response and docstring naming this quantity calls it `first_observed_at` for exactly this reason. The practical consequence: measured lag is a **lower bound** on the true signal→publication horizon, not the horizon itself — whoever eventually calibrates `TBD-TIS-01`/`TBD-TIS-02` from these measurements needs to know that, or every derived horizon will be biased short by however long ingestion typically lags real publication.
6. **No eTender award/result connector exists — tender outcomes are human-entered by design, not by oversight.** `signals.value->'awarded_participant_name'` (`design_tender_signal.py`) has only ever been observed `null` in real captures (every capture used `EventStatus=1`, open), and the events-list resource carries no monetary field at all regardless of status (`MANIFEST.md`). Building a connector needs a real network capture session against an actually-awarded tender first — the same discipline as the Q&A/clarifications gap recorded for Task 4.B (2026-08-09 entry above) and the original eTender contract-discovery sessions (2026-08-04 entries). Until then, `POST /tenders/{tender_id}/outcome` is the only way a `tender_outcomes` row is created, with a mandatory free-text `source_ref` (INV-15) naming where the human saw the public award.
7. **No verdict is emitted about which of §7.4's three loss diagnoses explains a given price delta.** `compare_winner_to_our_basis` (`packages/decision/calibration_summary.py`) computes `winner_vs_our_submitted`/`winner_vs_our_cost_basis` as plain arithmetic, always alongside `is_partial_coverage` — but §7.4 supplies no rule for choosing between "дыра в вендорах" (vendor gap), "демпинг" (dumping), or "«нарисованный» тендер" (drawn tender) from the delta alone. A human reads the delta plus the loss reasons they recorded (Task 1/2) and concludes; encoding a selection rule here would be an invented classifier with no source.
8. **Whether Phase 4's exit gate can close with the loop *recording* but not yet *calibrating* is an owner call, not something this task can decide.** P319's own wording ("после N закрытых циклов ... статистически более точна") is literally untestable until N real closed cycles exist — and as of this entry, zero real `tender_outcomes` rows exist outside test fixtures. Items 1-3 above are the concrete gap between "recording" and "calibrating."

**Source conflict (if any):** None.

**Owner follow-up needed:** Yes, non-blocking for this task's own scope (everything above was known and recorded as out-of-scope going in, per the plan's "Why this scope, and not the spec's literal §7.4" section). (a) Decide whether Phase 4's exit gate can GO with a measurement-only calibration loop, or whether it should wait for a first real closed tender cycle. (b) When a real tender outcome is available, exercise `POST /outcome`/`POST /outcome/loss-reasons`/`GET /tenders/{tender_id}/calibration` against it — everything to date has run only against test fixtures. (c) `TBD-TIS-01`/`TBD-TIS-02`/`D-VND-REP` remain the same unresolved research/approval gates carried since Phase 3, now with Task 3's snapshot retention as their first concrete path toward eventual resolution. (d) A real eTender award/result connector needs its own bounded network-capture session before item 6 above can close.

## 2026-08-12 — Owner decision: Phase 5 АЛГОРИТМ builder is still in scope, on top of Decision Core

**Context:** The 2026-08-04 entry ("TENDER_INTELLIGENCE_SPEC.md integrated...") flagged, and left explicitly unresolved, whether `TENDER_INTELLIGENCE_SPEC.md`'s Phase 4 "Decision Core" (§7.1, MDC — built across tasks 4.A-4.D, now merged) absorbs the original master-plan's Phase 5 "АЛГОРИТМ" page (a separate, versionable Human/Rule/ML/Gate policy-graph builder, a decision already locked in `docs/CONTEXT.md`'s "Locked decisions"), or replaces the need for one. `PLAN-MISSION-5.md`'s own header marks the file ЧЕРНОВИК pending exactly this answer, "уточнить у владельца до старта Phase 5." With Phase 4's exit gate now GO'd (`docs/reports/WORKLOG.md`, 2026-08-12 entries), this was the moment `PLAN-MISSION-5.md` itself named for asking.

**Decision (owner, asked directly in chat):** Build the АЛГОРИТМ policy-graph builder on top of Decision Core, per `PLAN-MISSION-5.md`'s original framing — the locked decision in `docs/CONTEXT.md` stands as-is. Decision Core's direct Go/No-Go/Bid-No-Bid logic (4.A) does **not** replace the need for a separate, versionable builder; `PLAN-MISSION-5.md` is not superseded/retired by `TENDER_INTELLIGENCE_SPEC.md`'s Decision Core framing, unlike `PLAN-MISSION-2/3/4.md`'s DFE/SCG/EL/MDC portions, which *were* restructured by that document (per `docs/CONTEXT.md`'s "Where things live" — a partial supersession, not blanket, and this is the concrete boundary of what it did and did not cover).

**Implication, not yet decided:** How Decision Core's already-built, direct logic (4.A's `go_no_go_inputs`/`decisions` tables, `matching.py`/`boq_summary.py`'s BOQ-coverage arithmetic) relates architecturally to a future versionable graph — whether 4.A's logic gets reimplemented as Human/Rule nodes inside the new builder, sits underneath it as a data source the graph's nodes read from, or something else — is Phase 5 planning's own first question, not resolved by this entry. This entry closes only the "does Phase 5 still happen at all" question `PLAN-MISSION-5.md` was blocked on.

**Source conflict (if any):** None — this affirms `docs/CONTEXT.md`'s existing locked decision rather than changing it.

**Owner follow-up needed:** No further owner input needed to start Phase 5 planning itself. `PLAN-MISSION-5.md`'s own draft-status banner (which names this exact question as its blocker) should be updated to reflect this resolution before that plan is treated as ready to execute against — recorded here rather than done silently in the same edit as this decision, since updating a plan-of-record file is its own distinct step.

## 2026-08-12 — Finding: the World Bank JSON API this codebase's connector ingests from appears stale relative to the live HTML site

**Context:** Owner asked to check the World Bank site for early-signal evidence for Azerbaijan (unrelated to any current task — ad hoc verification). Browsing the human-facing site (`projects.worldbank.org`) live in Chrome showed real, current activity for Azerbaijan: `P505208` ("Azerbaijan Scaling-Up Renewable Energy Project") as **Active**, board-approved March 27, 2025, with a real procurement history back to a June 13, 2024 General Procurement Notice; plus two brand-new **Pipeline**-status projects (`P515029` "Livable Baku Project", $410M; `P508792` "Azerigas Gas Leak Detection and Repair Facility", $15M) with no procurement activity yet — the exact early-signal pattern task 2.B's donor-pipeline signal exists to catch. A direct, real (not fabricated) `curl` against the actual endpoint `packages/tender/worldbank_connector.py`/`worldbank_contract.py` call (`https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=AZ&rows=100&os=0`) told a different story:

1. `?id=P515029` → HTTP 404, `"total":"0"` — this API has no record of the project at all, though it is plainly visible on the live HTML site.
2. `?id=P505208` → still returns `"status":"Pipeline"`, `"p2a_updated_date":"2024-02-28 00:00:00.0"` — over a year stale versus the HTML site's Active/Board-Approved status.
3. `?countrycode_exact=AZ&rows=100&os=0` → `"total":"79"`, status breakdown `4 Active / 61 Closed / 13 Dropped / 1 Pipeline` — byte-for-byte identical to the numbers frozen in `fixtures/tender-snapshots/worldbank/MANIFEST.md` from the 2026-08-05 capture (task 2.B), down to `P505208`'s exact fields (`totalamt: "250,000,000"`, no `boardapprovaldate`/`borrower`/`impagency`).

Taken together this suggests the legacy `search.worldbank.org/api/v2/projects` JSON endpoint — the only World Bank data source this codebase's ingestion pipeline reads from — is stale or frozen relative to whatever backend actually serves `projects.worldbank.org`, and has not reflected real project-status changes for Azerbaijan since at least the 2026-08-05 capture. If accurate, the DFE donor-pipeline signal source has been silently blind to new World Bank signals (including a real, large, brand-new Pipeline project) for the entire time it has existed in this codebase — and nothing in `schema_drift.py`'s contract-drift detection would catch this: the response shape hasn't changed, only its freshness.

**This is a finding from ad hoc manual verification, not from a bounded, reproducible capture session** — no new fixture was captured, and this entry does not itself confirm root cause (could be endpoint deprecation, CDN/edge caching, an account/quota-gated newer API replacing it, or something else). Recorded here per this file's "record every deviation/assumption discovered, never silently" charter rather than left only in chat history.

**Source conflict (if any):** None — this is an operational/infrastructure observation about a live external dependency, not a PRD/spec conflict.

**Owner follow-up needed:** Yes. (a) A dedicated, bounded verification session (same discipline as the original task 1.A/2.B contract-discovery sessions) is needed to confirm whether `search.worldbank.org/api/v2/projects` is genuinely stale/deprecated or whether this was a transient/caching artifact of these particular ad hoc calls. (b) If confirmed stale, the World Bank connector needs a replacement data source or endpoint before the donor-pipeline signal can be trusted as "current" rather than "frozen circa February 2024" — this is a production data-quality gap, not merely a missed feature. (c) Until (a)/(b) resolve, any freshness claim about existing `design_tender`/donor-pipeline World Bank signals for Azerbaijan already in the system should be treated with suspicion.

## 2026-08-12 — Follow-up: staleness confirmed as real (not caching); a `v3` endpoint exists with current data but a materially different field contract

**Context:** Follow-up verification on the same date, requested by the owner, to resolve the previous entry's open question (a) — genuine staleness vs. transient caching artifact. Still an ad hoc verification, not a bounded fixture-capture session; no new fixture was written to `fixtures/`.

**Ruled out caching:** `?id=P505208` with a cache-busting query param (`&_=<random>`) returned the identical stale `"status":"Pipeline"`/`"p2a_updated_date":"2024-02-28"`. Response headers on the plain query show `CF-Cache-Status: DYNAMIC` and `X-Powered-By: Express` — Cloudflare is passing every request straight through to an origin Express server, not serving an edge cache. The staleness is server-side, not a CDN artifact.

**A `v3` endpoint exists and is current:** `https://search.worldbank.org/api/v3/projects?format=json&countrycode_exact=AZ` (HTTP 200, same `search.worldbank.org` host, same Cloudflare/Express stack) returns `"total": 95` — matching the live HTML site's count exactly, versus `v2`'s `"total": 79` (matching only the old frozen fixture). Pulling `P515029`/`P508792`/`P505208` individually out of the `v3` response, their `boardapprovaldate` values (`2027-02-18`, `2026-08-06`, `2025-03-27` respectively) match the live HTML site's displayed approval dates exactly — `v3` is a real, live, current data source for the same underlying project records.

**But `v3`'s record shape has no `status`/`projectstatusdisplay` field at all** — the exact field `worldbank_contract.py`/the donor-pipeline signal logic depends on to classify a record as `"Pipeline"`. `v3`'s fields are `id`/`proj_id`/`countryshortname`/`boardapprovaldate`/`borrower`/`impagency`/`closingdate`/`totalamt`/`curr_ibrd_commitment`/`idacommamt`/`grantamt`/`lendprojectcost`/`regionname`/`sectorcode`/`major_sectors`/`major_sector_name`/`major_sector_code`/`project_name`/`projid_id_display`, optionally `theme_list` — a different, richer, but status-less shape. A `v2`→`v3` migration is therefore **not a drop-in swap**: it needs its own contract-discovery session (same discipline as `packages/tender/etender_contract.py`'s original capture) to work out a `v3`-native way to recognize "not yet board-approved" (the old fixture's `MANIFEST.md` already independently noted `boardapprovaldate`/`borrower`/`impagency` being *entirely absent* — not merely null — as the `v2` proxy for this on unapproved records; whether that same all-absent pattern holds on `v3` was not checked in this session and needs its own verification, since `v3`'s `P515029`/`P508792` records **do** carry populated `boardapprovaldate`/`borrower`/`impagency` values despite being genuinely Pipeline-status per the HTML site — so the `v2` proxy does not carry over as-is).

**Source conflict (if any):** None.

**Owner follow-up needed:** Yes, this replaces follow-up (a) from the prior entry (now resolved: confirmed real staleness, not caching) and sharpens (b): a bounded `v3` contract-discovery session is needed before any migration — specifically to work out `v3`'s own signal for Pipeline/unapproved status (its absence of a `status` field, and the fact its "unapproved" records still populate `boardapprovaldate`/`borrower`/`impagency`, means the current `v2`-era approach of treating those three fields' total absence as the Pipeline marker will not work unmodified). Until that session runs, `packages/tender/worldbank_connector.py` continues reading `v2`, which per this and the prior entry is confirmed stale for Azerbaijan since at least early-to-mid 2024.

## 2026-08-12 — Resolution: `v3` contract discovery session run; `status` field exists, just opt-in via `fl=`; no proxy needed

**Context:** The bounded discovery session the prior entry called for (`docs/superpowers/plans/2026-08-12-worldbank-v3-contract-discovery.md`) ran the same day. Its Task 1 found the actual explanation for the prior entry's "no `status` field" observation — and it is much simpler than a missing-field contract gap.

**Finding:** Using `read_network_requests` against the live `projects.worldbank.org` Azerbaijan project-list page, the site's own JavaScript was observed issuing `POST https://search.worldbank.org/api/v3/projects` with an explicit `fl=` (field list) query parameter naming `status`, `projectstatusdisplay`, `last_stage_reached_name`, `proj_last_upd_date`, `public_disclosure_date`, and roughly thirty other fields. Every one of this session's earlier `v3` probes omitted `fl=` entirely and so silently got `v3`'s default field projection — which excludes `status`. Requesting the field explicitly resolves it completely:

```
GET https://search.worldbank.org/api/v3/projects?format=json&rows=100&fl=id,project_name,status,last_stage_reached_name,boardapprovaldate,borrower,impagency,totalamt,proj_last_upd_date,public_disclosure_date&apilang=en&countrycode_exact=AZ&os=0
```

— a plain, unauthenticated `curl` (no cookies, no special headers, no `POST`; `GET` works identically, confirmed by direct comparison of all four `{GET,POST} x {credentials omitted,included}` combinations from within the page) returns `"total": 95` and a status breakdown of `{Pipeline: 2, Active: 3, Closed: 72, Dropped: 18}` — matching the live HTML site exactly. `P515029`("Livable Baku Project")/`P508792`("Azerigas...")/`P505208`("...Renewable Energy...") individually show `status: "Pipeline"`/`"Pipeline"`/`"Active"` respectively, matching the site precisely, including `last_stage_reached_name: "Concept Review"` for both Pipeline records (matching the HTML table's own "Last Stage Reached" column verbatim).

**This supersedes the prior entry's proxy-signal framing entirely.** No heuristic reconstruction of Pipeline-status from `boardapprovaldate`/`borrower`/`impagency` absence is needed on `v3` — `status` is directly requestable, and is in fact a richer signal than `v2` ever had (`v2` lacked `last_stage_reached_name`/`proj_last_upd_date`/`public_disclosure_date` entirely). The migration path is now well-defined: change the connector's query string from `v2` to `v3` and add an explicit `fl=` parameter including at minimum `status` (plus whatever existing `v2`-sourced fields `worldbank_contract.py` currently reads, checked field-by-field against `v3`'s naming — e.g. `v2`'s `totalamt` string-with-commas format ("250,000,000") differs from `v3`'s plain numeric string ("410000000"), a real formatting difference a migration must handle, not paper over).

**Source conflict (if any):** None.

**Owner follow-up needed:** Yes, but narrowed and much smaller than the prior entry implied. (a) The actual connector migration (`packages/tender/worldbank_connector.py`/`worldbank_contract.py`/`worldbank_pipeline_job.py`) is still not started — this entry only closes the reconnaissance question, per the discovery plan's own explicit scope boundary. (b) A migration task should re-verify every field `worldbank_contract.py`'s current `SourceContract` names against `v3`'s actual shape (not just `status`) before cutting over — at minimum the `totalamt` number-formatting difference noted above. (c) Whether to keep, retire, or explicitly mark historical the existing `v2` fixtures (`az_donor_pipeline_page_os0/os10.raw.json`) is a call for whoever scopes that migration task, not decided here.

## 2026-08-13 — Task 5.A (АЛГОРИТМ: architect): lifecycle transition table is this task's own modeling choice

**Context:** Task 5.A (`docs/reports/PLAN-MISSION-5.md` §3, first task of Phase 5) built the domain schema/lifecycle/research-dossier ADR/official-source registry named there. `docs/superpowers/plans/2026-08-12-phase5-task5a-algoritm-architect.md`'s own Global Constraints section already flagged this at planning time; recorded here per that plan's own close-out step, verified against what was actually built.

**Deviation/assumption:**
1. **`packages/algorithm/policy_lifecycle.py`'s `ALLOWED_TRANSITIONS` table is a concrete reading of a terse spec sentence, not spec text itself.** `PLAN-MISSION-5.md` §3 states the linear sequence "draft → simulation → business_review → risk_review → approved → active → retired" plus "rejected/suspended ветви" without naming exactly which states branch to which. This task fixed: `simulation`/`business_review`/`risk_review` may each transition to `rejected`; `active` may transition to `suspended`; `suspended` may return to `active` or proceed to `retired`. No other pair is allowed. This is a reasonable reading, not a fabricated requirement — but it is this task's own choice, and should be revisited if task 5.B's real compiler or 5.C's simulation engine need a different shape (e.g. a `business_review`-to-`draft` revision path was considered and deliberately not added, since the plan's stated sequence never mentions review stages sending work backward to `draft` — only forward or to `rejected`).
2. **FR-ALG-08's "ml/hybrid not activatable until Phase 8" rule is enforced at the model layer (`PolicyNode.__post_init__`) in this task, not deferred entirely to task 5.B's compiler.** There is no compiler yet, so a model-layer rejection is the only enforcement point that exists today; `NODE_TYPES` still includes `ml`/`hybrid` for schema stability (so Phase 8 needs no migration to add them), but nothing in this codebase can currently construct a `PolicyNode` of either type. 5.B's compiler, once built, should not need to re-decide this — it inherits an already-enforced constraint.
3. **`research_dossier_id` on `policy_versions` is a nullable FK that nothing currently checks.** The ALG-RESEARCH gate's actual enforcement (a financial-impact version may not reach `approved` without a complete, linked dossier) is explicitly task 5.B's compiler's job per the plan — this task only makes the link possible to express.
4. **Zero rows exist in `official_sources` after this task.** The registry is a structural home for real, human-sourced, cited facts (an actual law, an actual CBAR FX rate, an actual VAT percentage) — seeding it with anything in application code would either fabricate a real number (hard ban #2) or plant a fake one indistinguishable from a real one later. Test fixtures use values explicitly labeled as synthetic (e.g. citation `"test-fixture-only, not a real published rate"`).

**Source conflict (if any):** None.

**Owner follow-up needed:** No decision needed to continue to task 5.B — the lifecycle table (item 1) is a reasonable working choice, not a blocking ambiguity, and is cheap to revise if 5.B/5.C surface a concrete need for a different shape (e.g. a review-to-draft revision path). `D-FIN`/`TBD-04` remain exactly as unresolved as before this task, per design.

## 2026-08-13 — Task 5.B (АЛГОРИТМ: backend-core compiler/validator): enforcement points, structural readings, and honest gaps

**Context:** Task 5.B (`docs/reports/PLAN-MISSION-5.md` §3, second task of Phase 5) built the compiler/validator, branch-coverage check, kill switch, and maker/checker activation gate on top of task 5.A's schema. `docs/superpowers/plans/2026-08-13-phase5-task5b-algoritm-compiler-validator.md`'s own Global Constraints section flagged all of the below at planning time; recorded here per this task's own close-out, verified against what was actually built.

**Deviation/assumption:**
1. **Two gates live at two different lifecycle transitions — this task's own reading of `PLAN-MISSION-5.md`'s terse phrasing, not spec text.** `FR-ALG-03`'s "перед отправкой на утверждение" (before submission for approval) is read as the one unambiguous moment that phrase can mean: the `risk_review → approved` transition (`submit_for_approval`, gating structural validity + branch coverage + required-role existence + financial-dossier approval). `FR-ALG-12`'s "активируется" (is activated) is read as the `approved/suspended → active` transition specifically (`activate_version`, gating maker/checker). `transition_version_status` itself is unmodified — every other transition still goes through it directly, so 5.A's own tests kept passing without edits.
2. **"Start node"/"terminal" are read structurally (in-degree 0 / out-degree 0), not as a dedicated node type.** Master plan §12.2 names eight node types including `Terminal` and `Notification/escalation`; `PLAN-MISSION-5.md` §1 and 5.A's own `ACTIVATABLE_NODE_TYPES` restrict Phase 5 to four (`human`/`rule`/`gate`/`data_quality`). Rather than inventing a field for a type this phase doesn't use, degree in the edge set stands in for both concepts. A node reachable only via another node's `fallback_node_key` (not an explicit `PolicyEdge`) is treated as having an implicit edge for reachability/terminal/cycle purposes — found as a real bug during this task's own unit testing (a legitimate fallback-only escape node was initially mis-flagged as a disconnected "island" before this fix).
3. **Cycle validity rule (no spec algorithm given):** a cycle is valid only if it contains a `human` node, or a node with a `retry_policy` carrying a positive integer `max_attempts` **and** a `fallback_node_key` pointing outside the cycle. Anything else is flagged `unbounded_cycle_no_exit`.
4. **Edge type-compatibility rule (no spec algorithm given):** for a direct edge, a key present in **both** the upstream node's `output_contract` and the downstream node's `input_contract` must carry the same type string. This checks conflicts on shared keys, not full input-contract coverage — the spec names no exact matching algorithm, and full-coverage semantics would go beyond what §12.6 actually states.
5. **Branch coverage (`FR-ALG-04`) required one small, additive, documented convention on the already-opaque `test_cases` field, not a schema change.** A Rule node's test-case dict may now carry an optional `covers_condition` key naming an outgoing edge's `condition_label`; every distinct labeled branch needs at least one test case whose `covers_condition` matches it. This is unavoidable — `FR-ALG-04` cannot be checked at all without *some* way to say which test case covers which branch, and the alternative (not implementing branch coverage) would fail to deliver a P0 requirement entirely.
6. **Two `§12.6` checklist items are not mechanically checked at all, recorded as gaps rather than invented:** "все side effects идут через outbox" (no node type in Phase 5's four-type set carries an explicit side-effect/notification concept — that's the `Notification/escalation` type, not adopted into this phase's schema) and "hard constraints не спрятаны в soft weights"/"веса суммируются по утверждённой схеме" (no weighting/scoring schema exists anywhere in this codebase — `coefficients_and_rationale`/`formula_or_decision_table` stay opaque JSON per 5.A's own ADR-0007 rationale; checking this would require inventing the exact structure `D-FIN`/`TBD-04` forbid inventing).
7. **Kill switch's "in-flight evaluations complete in a defined way" (`FR-ALG-13`) is not built.** There is no evaluation/execution engine anywhere in this codebase yet — nothing runs a policy graph against a real case, so there is nothing "in-flight" to complete. `kill_switch()` only implements the half that has something to act on: a reason-mandatory wrapper around the existing `active → suspended` transition.
8. **Rollback works only against a `suspended` version.** 5.A's fixed `ALLOWED_TRANSITIONS` gives `retired` zero outgoing transitions — deliberately not touched by this task (revising it is a bigger decision than this task's own scope). `activate_version()` called against a `suspended` version *is* rollback (the `suspended → active` edge 5.A already allows); called against a `retired` version, the existing `InvalidTransitionError` already rejects it. `retired` stays genuinely permanent by construction, not by a new check.
9. **"Only one active version per policy_graph at a time" did not exist before this task.** Added structurally via a partial unique index (`migrations/0019_algoritm_activation_guard.sql`), same "structural, not just checked" discipline 5.A used for content immutability — `activate_version`'s app-level auto-suspend of the previous active version is a courtesy on top of that index, not the enforcement mechanism itself.
10. **Maker/checker identity source:** per `docs/adr/0005-authority-model.md`, `changed_by` (the activator) must differ from the target version's own `created_by` (already a required field since 5.A — no new field needed). Applies only when the version contains at least one `financial_impact=True` node, per `FR-ALG-12`'s own qualifier.

**Source conflict (if any):** None.

**Owner follow-up needed:** No decision needed to continue to task 5.C/5.D. Items 6-7 above (outbox side effects, hard-constraint/soft-weight separation, in-flight evaluation completion) remain real, honest gaps for whenever an execution engine (5.C+) or a `Notification/escalation`/weighting schema is actually built — not blocking, since nothing in this codebase produces a real side effect or a real weighted score yet. `D-FIN`/`TBD-04` remain exactly as unresolved as before this task.

## 2026-08-14 — Task 5.C (АЛГОРИТМ: simulation/backtest engine): test-case-replay reading, and what "simulation" honestly means here

**Context:** Task 5.C (`docs/reports/PLAN-MISSION-5.md` §3, third task of Phase 5) built the first thing in this codebase that actually *runs* a policy graph against a case (`packages/algorithm/simulation_engine.py`/`simulation_store.py`, `packages/decision/simulation_case_builder.py`). Plan: `docs/superpowers/plans/2026-08-14-phase5-task5c-algoritm-simulation-backtest.md`, whose own Global Constraints section flagged all of the below at planning time; recorded here per this task's own close-out, verified against what was actually built.

**Deviation/assumption:**
1. **This task inherits 5.B's own recorded gap — no `PolicyNode` carries executable logic — and reads "simulation" as test-case replay, not formula execution, as the only honest way to build FR-ALG-05 without inventing one.** A node's real behavior at a branch point is whichever of its own `test_cases` the case's running `state` matches; the human-authored example *is* the decision table. This is a deliberate scope reading, not a lesser stand-in for "the real thing" quietly substituted — building a parser for `preconditions` strings or a weight-evaluator over `research_dossier`'s opaque `coefficients_and_rationale` would violate hard ban #2 and `D-FIN`/`TBD-04`.
2. **No new key was invented on `test_cases` — this task wires up the `"input"`/`"expected_output"` scaffolding already present, unused, in 5.B's own test fixtures** (`tests/unit/test_policy_validator.py`'s `{"input": {}, "expected_output": {}, "covers_condition": ...}`). A test case matches the engine's running `state` when every key in its own `"input"` is present in `state` with an equal value (subset match); a matched test case's `"expected_output"` is merged into `state` before the walk continues, so a downstream node's `input` match can depend on an upstream node's declared output — the same producer/consumer relationship `policy_validator`'s `io_type_mismatch` check already validates structurally.
3. **Every undetermined outcome is a specific, named reason code, never a guessed edge** (`no_matching_test_case`, `ambiguous_test_cases`, `test_case_covers_unknown_edge`, `human_override_no_matching_edge`, `step_limit_exceeded`) — hard ban #3 applied to graph traversal, not just data freshness. A Human node with neither a case-supplied `human_overrides` entry nor a matching test case stops at `awaiting_human` specifically (distinct from the error-shaped `undetermined` statuses) — an engine cannot stand in for a person, only replay what one already said (via `human_overrides`, which is how a historical, already-decided case gets simulated at all) or declared as an example (via `test_cases`).
4. **`FR-ALG-06` (sensitivity analysis) is a recorded gap, not built.** Its own text is "influence of *changing weights/thresholds*" — no weight or threshold representation exists anywhere in this codebase, the same gap 5.B's close-out already recorded for the compiler's soft-weight check (item 6 in the entry above). A structural substitute (e.g., perturbing which test case "wins" as a sensitivity proxy) was considered and deliberately not built — it would invent a semantic the spec never gave. `FR-ALG-06` is `P1` (`FR-ALG-05` is `P0`); shipping the `P0` mechanism and recording the `P1` gap follows this repo's own precedent (5.B's outbox/soft-weight items).
5. **"False-positive/negative review queue" and "human override rate" are deliberately NOT auto-classified.** Deciding whether a simulated terminal/reason-code combination "agrees" with a case's `actual_outcome_label` (e.g. `TenderOutcome.outcome = "lost"`) would require inventing a correspondence between free-text reason codes and free-text outcome labels no source document supplies. `simulation_store.list_case_traces()` instead returns every case's simulated result and its `actual_outcome_label` side by side, unclassified — the same "arithmetic gives a delta, a human makes the call" precedent `packages/decision/calibration_summary.py` already established (see the 2026-08-12 Phase-4-exit-gate entry above, item 7).
6. **"Rollback rehearsal log" needed no new code.** 5.B's `policy_version_transitions` (append-only, already includes `suspended → active` rollback transitions) already *is* this log; `policy_store.list_transitions_by_version()` already reads it. This task added nothing for that bullet — 5.E's future rehearsal test is what turns it into a proven exit-gate artifact.
7. **Monetary ranges are grouped by `(terminal_node_key, currency)` and never summed across currencies** — same discipline `packages/decision/matching.py` already applies to cross-currency vendor offers (no FX rate invented, `D-TAX`). A case with a `monetary_amount` but no declared `monetary_currency` is excluded from every range and counted separately (`monetary_amount_uncurrencied_count`), never silently mixed in.
8. **`build_case_from_bid_readiness` serves both the "synthetic vendor cases" and "frozen real tender snapshots" `PLAN-MISSION-5.md` bullets with one function** — the distinction is purely which `BoqLine`/offer data the *caller* built the `BidReadinessCandidate` from (vendor offers are always synthetic today regardless, per ADR-0004); the caller picks the `case_source` label when recording the run. No separate "synthetic" vs "frozen real" builder function was written, since the underlying transformation (BidReadinessCandidate → SimulationCase) is identical either way.

**Source conflict (if any):** None.

**Owner follow-up needed:** No decision needed to continue to task 5.D/5.E. `FR-ALG-06` stays unbuilt pending a weight/threshold representation this task does not invent (same posture as 5.B's own recorded gaps). Auto-classifying simulated-vs-actual agreement into a real false-positive/negative *count* remains deliberately unbuilt for the same invented-correspondence reason as item 5 above — a future task could revisit this if a policy author explicitly declares the reason-code-to-outcome-label mapping themselves (a policy-authoring decision, not an engine inference). `D-FIN`/`TBD-04`/`D-TAX` remain exactly as unresolved as before this task.

## 2026-08-14 — Task 5.D (АЛГОРИТМ: frontend): outline-only scope, first HTTP surface, tech choices

**Context:** Task 5.D (`docs/reports/PLAN-MISSION-5.md` §3, fourth task of Phase 5) built the first HTTP API over `packages/algorithm` (`apps/api_tender/routers/algoritm.py`) and the first real code in `apps/web` (`docs/superpowers/plans/2026-08-14-phase5-task5d-algoritm-frontend.md`'s own Global Constraints section flagged the scope reduction below at planning time, before any code was written). Recorded here per this task's own close-out.

**Deviation/assumption:**
1. **Master plan §12.5 names canvas as the primary interface and the outline/table view as "доступная альтернатива" (the accessible alternative) — this task builds only the alternative, and treats it as a complete, real UI in its own right, not a degraded stand-in for the primary form.** Building a real drag-and-drop/zoom/minimap canvas means choosing and integrating a graph-rendering library — a substantially separate effort with its own tech decision this task does not make. `FR-ALG-07`'s own requirement (a full keyboard-operable accessible alternative) is satisfied end-to-end; §12.5's canvas-specific bullets (drag-and-drop, zoom, minimap, live impact counters, search-by-node/role/input/reason) are not built and have no code today.
2. **Version diff view, human-readable PDF/Markdown export, and live impact counters are recorded gaps, not attempted with a placeholder.** Version diff needs a real diff algorithm over two node/edge sets (the `GET /policy-versions/{id}` route both versions would use already exists, so this is pure frontend work for a future task). PDF/Markdown export needs real templating/layout — only machine-readable JSON export (`src/exportJson.ts`, a client-side `Blob` download) is built. Live impact counters would need a live production evaluation stream — nothing in this codebase evaluates a policy against live traffic yet (that concept doesn't exist before Phase 6).
3. **New permission strings (`algorithm.policy.read`/`write`/`approve`/`activate`, `algorithm.simulation.read`/`write`) were picked, not derived from any source document.** Permissions are ungoverned free text in this codebase (granted per role via `role_permissions`, the same as every existing route's permission string, e.g. `decision.outcome.write`) — there is no central enum anywhere to update or that these needed to match.
4. **Frontend tooling (Vite, Vitest, `@testing-library/react`, plain `fetch`, plain CSS — no data-fetching library, no component library) is this task's own implementation-detail choice, not a locked PRD decision.** `docs/CONTEXT.md`'s locked decision names React/TypeScript only; this is the first frontend code in the whole repo, so there is no existing convention to follow or violate. Same posture as the 2026-08-04 CI-runner-platform entry (a PRD-names-the-family-not-the-tool gap).
5. **`GET /research-dossiers/{id}` returns the store's raw dict rather than a typed Pydantic response model** (`response_model=dict[str, Any]`) — `ResearchDossier`'s 17 fields are already fully typed at the domain layer (`research_dossier_model.py`) and duplicating that shape as a second Pydantic model for one read-only route was judged not worth the duplication for this task's scope; a future task exposing dossier authoring UI should revisit this.
6. **`packages/algorithm/policy_store.py` gained one new read function, `get_version()`** (single-version lookup by id, independent of its parent graph) — needed because the API layer must resolve a version's metadata (status, `research_dossier_id`, etc.) without the caller already knowing its `policy_graph_id`, which `list_versions_by_graph()` alone can't do. Pure additive read, no behavior change to any existing function.

**Source conflict (if any):** None.

**Owner follow-up needed:** No decision needed to continue to task 5.E. The canvas/diff/PDF-export/live-impact-counter gaps above are real, not blocking — 5.E's accessibility criterion is scoped against what this task actually built (the outline view), not against an unbuilt canvas. A future task should pick a canvas library before attempting §12.5's remaining bullets, and that choice deserves its own ADR given how much it will shape `apps/web`'s later structure.

## 2026-08-14 — Task 5.E (АЛГОРИТМ: security/qa exit-gate suite): what was already proven, what this task added, and the kill-switch/simulation scope boundary

**Context:** Task 5.E (`docs/reports/PLAN-MISSION-5.md` §3, fifth and last task of Phase 5) closes the phase's exit gate. `docs/superpowers/plans/2026-08-14-phase5-task5e-algoritm-exit-gate.md`'s own evidence-audit table (written before any new code) found that four of §5's five criteria were already fully proven by 5.A-5.D's own tests as a side effect of building the mechanism — this task audited that claim rather than assuming it, then built only the two genuine gaps plus the one criterion nothing before this task could satisfy (an automated accessibility scanner pass).

**Deviation/assumption:**
1. **"Kill switch stops new evaluations" (`FR-ALG-13`) is read, consistently with 5.B's own reading, as stopping future *production routing* to a version — not as gating `POST /policy-versions/{id}/simulate`.** `packages/algorithm/simulation_store`/`simulation_engine` (5.C) operate on a version's nodes/edges regardless of its lifecycle status, and this task deliberately does not add a status check to the `simulate` route: an analyst investigating *why* a version was killed (or replaying a suspended version's behavior during a rollback rehearsal — see item 2) genuinely needs to be able to simulate it. There is still no production evaluation/routing engine anywhere in this codebase for a kill switch to meaningfully gate beyond the lifecycle-status flip 5.B already built — the same honest gap 5.B/5.C recorded, unchanged by this task.
2. **The rollback rehearsal's "restores behavior" claim is proven via 5.C's `simulation_engine.run_case`, looked up against whichever version `list_versions_by_graph` reports as currently `active`** (`test_rollback_rehearsal_restores_active_versions_behavior_and_keeps_transition_log_visible`) — not a hardcoded version id. This matters because the previous rollback test (5.B) predates the simulation engine entirely and could only assert the status column flipped; content immutability already guaranteed a version's own behavior can't change, so the real thing worth proving is that the *graph's* current behavior (whichever version is active) reverts — which this task's dynamic lookup demonstrates rather than assumes.
3. **`vitest-axe`'s published TypeScript types don't resolve against this project's vitest 3.x `expect` (a real gap in that third-party package, confirmed by the matcher working correctly at runtime but `tsc --noEmit` rejecting the call).** Isolated to one named helper (`expectNoViolations` in `apps/web/src/accessibility.test.tsx`) rather than scattering `as unknown` casts — recorded rather than silently worked around, and rather than downgrading to a less precise assertion to dodge the type error.
4. **The accessibility scan found and this task fixed one real violation**, not a synthetic one: `SimulationPanel.tsx`'s per-case results table had an empty `<th scope="col">` for its actions column (`empty-table-header` — no text visible to screen readers). Fixed by giving it real visible text ("Actions") rather than a visually-hidden trick, since no CSS/utility-class system exists yet in `apps/web` to support one cleanly.

**Source conflict (if any):** None.

**Owner follow-up needed:** No decision needed — Phase 5's exit gate (`PLAN-MISSION-5.md` §5) has evidence for every criterion as of this task; see `docs/reports/WORKLOG.md`'s exit-gate summary table for the full mapping. `D-FIN` (per `PLAN-MISSION-5.md` §6) remains the one open item, and it blocks only the *activation* of a first real financial policy, not anything this phase's mechanism-building tasks (5.A-5.E) needed to resolve.

## 2026-08-14 — Owner decision: `D-HOST` (local network only) and `D-IDP` (lightweight local auth, no external IdP)

**Context:** `PLAN-MISSION-6.md` §1 names `D-HOST`/`D-IDP` as the one pair of open questions in this entire plan of record that blocks a phase's *start* (task 6.A) rather than just a later sub-task or activation step — asked directly in chat once Phase 5's exit-gate work was substantially done, the same pattern used for the Phase 3→4, Phase 4→5, and Phase 5 АЛГОРИТМ-scope decisions above.

**Decision (owner, asked directly in chat):**
- **`D-HOST`:** Hosting is **local network only** — no private or public cloud. No hosting-provider abstraction is needed anywhere in `apps/*`'s deployment story.
- **`D-IDP`:** Pilot identity/auth is **lightweight local auth**, built on the already-existing `users`/`roles`/`role_permissions` tables (`packages/platform/rbac`, in place since Phase 0) — a real login mechanism, not `apps/api_tender/deps.py`'s current dev-only `X-Dev-User` header, but explicitly **not** Entra/OIDC and **not** a break-glass procedure, since a local-network-only pilot is never internet-facing. `PLAN-MISSION-6.md`'s own task 6.A row literally named "Entra/OIDC... включая break-glass" as the anticipated shape of this decision — the owner's actual answer is narrower than that anticipation, recorded here rather than the plan's guess being silently treated as the real decision.

**Implication, not yet decided:** *How* the lightweight local auth mechanism is actually built (password hashing scheme, session vs. token, whether `apps/api_vendor` needs its own login or shares `apps/api_tender`'s) is task 6.A's own implementation question, not resolved by this entry — same posture as every other "the owner answered the scope question, the mechanism is the task's job" decision in this log (e.g. the 2026-08-12 АЛГОРИТМ-scope entry).

**Source conflict (if any):** None — this is the owner directly answering a question `PLAN-MISSION-6.md` itself posed, not a deviation from anything already locked.

**Owner follow-up needed:** No further input needed to start planning Phase 6 task 6.A once Phase 5's exit gate receives its own GO (`AGENTS.md` §4 — phases still don't overlap; resolving `D-HOST`/`D-IDP` unblocks 6.A's *content*, not the phase-sequencing rule). `D-PILOT` (blocks task 6.D specifically) and `D-SLO` (blocks task 6.C's actual numbers, not its dashboard/alert mechanism) remain open, unaffected by this entry.

## 2026-08-16 — Task 6.A (АЛГОРИТМ/ops: hosting, local auth, shadow-comparison harness, cutover plan)

**Context:** `PLAN-MISSION-6.md` §3 task 6.A — the first, blocking task of Phase 6, covering four independent deliverables (hosting topology, identity/auth, shadow-comparison harness, cutover/rollback plan). Owner gave GO to start Phase 6 directly in chat. `D-HOST`/`D-IDP` were already resolved (2026-08-14, see entry above); this task is where their *mechanism* gets built. Work was split across this session directly (local auth, Tasks 1-3) and three parallel subagents (hosting/CI, shadow comparison, cutover doc, Tasks 4-7), each independently briefed and reviewed.

**Deviation/assumption — local auth (Tasks 1-3, this session directly):**
1. **Password hashing: `argon2-cffi` (new dependency), not a hand-rolled PBKDF2/HMAC scheme.** Confirmed with the owner before implementation as the one real design fork worth asking about (memory-hard, purpose-built vs. this repo's general dependency-minimalism).
2. **Session mechanism: a DB-backed `user_sessions` table (opaque random token as cookie value), not a stateless JWT.** NFR-SEC-06's "correct sign-out" requirement can't be honestly satisfied by a stateless token that remains valid until its own expiry regardless of logout — only a server-side revocable record makes sign-out real. Sessions are revoked, never deleted (same disable-not-delete discipline `packages/platform/audit.py` already applies to users).
3. **Lockout policy — 5 consecutive failures locks the account for 15 minutes — is an implementation detail, not a locked PRD number.** No source document specifies this threshold (unlike financial weights/ML thresholds/SLO which are explicitly `D-*`/`TBD-*`); picked as a reasonable engineering default, same class of decision as 5.D's tech-choice entries above.
4. **A real, non-obvious bug found and fixed during this task: recording a login failure inside the same per-request transaction that then raises an `ApiError` for the 401 response silently rolled back the failure-count increment.** `apps/api_tender/deps.py`'s `get_connection` dependency commits on success / rolls back on any exception (by design, documented in `app_factory.py`) — but a failed-login route legitimately wants to both persist the failure count AND return a 401. Fixed by having `authenticate_user` take the engine directly and manage its own independent transaction for the lockout bookkeeping, so it commits regardless of what the route handler does afterward. Caught by two independent, identical pytest failures (not a flaky result) — verified correct by careful code reasoning after this machine's Docker/testcontainers networking became too unreliable for a third live confirmation.
5. **`apps/api_vendor` gets no login mechanism** — it already has its own separate API-key tenant-isolation mechanism (`get_current_vendor_id`/`X-Vendor-Api-Key`), explicitly untouched by `D-IDP` per that mechanism's own docstring.
6. **TLS/HTTPS is out of scope; the session cookie is issued without `Secure`.** No reverse proxy/TLS termination exists yet in this repo — a real gap for a genuinely internet-facing deployment, acceptable only because `D-HOST` confirms this pilot is local-network-only, non-internet-facing.
7. **A frontend login page (`apps/web/src/Login.tsx`) was built this session** (owner's explicit choice, not deferred) — replaces the free-text "Dev user" input in `App.tsx` entirely; `algoritmClient.ts`'s per-call `username` parameter is removed since identity now travels via the browser's automatic cookie attachment (`credentials: "include"`), not a client-supplied header.

**Deviation/assumption — hosting/CI (Tasks 4-5, subagent):**
1. **Base images:** `python:3.12-slim` (matches `requires-python = ">=3.12"`) for the three Python services; `node:20-alpine` build stage + `nginxinc/nginx-unprivileged:1.27-alpine` serve stage for `apps/web` (chosen specifically for its non-root-by-default posture, matching `docs/operations/container-conventions.md`'s non-root rule with no extra Dockerfile work).
2. **Compose network/project name: `uniwatch`.** Fixed local ports: 8001 (tender), 8002 (vendor), 8080 (web); Postgres stays internal-only (no host port published, since `docker-compose.local.yml` is the complete deployment description for whatever single machine runs it — `D-HOST`'s "local network only" is satisfied by this compose file directly, not a placeholder for a cloud provider's orchestration).
3. **Image digest = `docker inspect`'s local content ID (`.Id`), not a registry distribution digest** — there is no registry yet (`D-HOST` is local-network-only), so the CI-produced `release-manifest.json` (commit SHA ↔ per-image digest) is the durable proof; how it physically reaches a deploy host is left to task 6.B, which is Gate 4's actual "commit↔digest proof" consumer.
4. **Real bug found while validating the Dockerfiles, not scope creep: `httpx` was listed only under the `dev` extra in `pyproject.toml`, but `apps/api_tender/deps.py` and `packages/contracts/vendor_api.py` both `import httpx` at module scope** — a production install (`pip install .` without `[dev]`) crashed both `api_tender` and `worker` at import time. Moved to main `dependencies`; confirmed by actually building and running all four images together via `docker compose -f docker-compose.local.yml up`, with `/health/ready` reporting the correct schema version on both API services and read-only rootfs verified active via `docker inspect` on every app container.

**Deviation/assumption — shadow-comparison harness (Task 6, subagent):**
1. **Consumes a bounded, human-exported v1 snapshot file, never a live call into v1** — confirmed with the owner before any subagent work started, as the one genuine interpretation call this sub-task required: `tools/check_v1_untouched.py` only pattern-matches two literal path strings (it would not technically catch a live network call whose URL doesn't contain those literals), but the prose ban in `AGENTS.md`/`CLAUDE.md` ("never read, write, or reference [v1] from any code") is broader than the scanner, and v1's own audit methodology (the 2026-07-27 v1 audit) treated it as an out-of-band snapshot, never a live connection from code. Building a live-call harness would have relied on a scanner gap, not honored the actual rule.
2. **No persistence added — `packages/tender/shadow_comparison.py` is pure functions, no store/migration.** Nothing yet consumes a persisted comparison-run history (task 6.E's exit-gate report is the eventual consumer, not built); adding a second migration (0022) concurrently with this session's own 0021 (local auth) risked merge conflict for no present benefit.
3. **The record contract requires the caller to supply `record_kind` plus each side's own known ingestion-scope (`v1_covers_record_kinds`/`v2_covers_record_kinds`) to resolve ID-presence/BOQ-presence discrepancies into `v1_loss`/`v2_defect` vs. `expected_semantic_difference`** — without both, the module reports "unresolved" rather than guessing. No source document specifies how this scope evidence should be assembled in practice (e.g. automatically from `source_contract.py`); left to the future comparison-job caller that doesn't exist yet.
4. **Field-value mismatches (`status`, `key_details`) classify as `source_drift` only when both records carry a parseable `captured_at` and v2's is strictly later than v1's** — a deliberately conservative modeling choice, not a specced rule (no source document defines "plausible drift").
5. **BOQ completeness-mismatch classification hardcodes `boq_completeness.py`'s known status values** (`complete`/`incomplete`/`in_progress`/`source_exhausted_unverified`) into specific bucket outcomes — inferred from that module's existing semantics, not from an explicit shadow-comparison spec.
6. **A `key_details` key present on only one side is unconditionally `expected_semantic_difference`** (treated as a structural schema difference) — a design simplification, not spec'd.

**Deviation/assumption — cutover/rollback plan (Task 7, subagent):**
1. Cutover criteria reference the shadow-comparison harness generically (its exact file layout wasn't fixed when this doc was written) rather than naming specific function signatures.
2. `D-SLO`/`TBD-01`/`TBD-02` (RPO/RTO, freshness, availability numbers) and `D-PILOT` (exact pilot-user scope) are referenced as still-open, not resolved or given placeholder numbers.

**Source conflict (if any):** None.

**Owner follow-up needed:** No decision needed to consider 6.A's mechanism-building complete. Remaining before 6.A can be called fully closed: the mechanical migration of 6 pre-existing integration test files off the now-removed `X-Dev-User` header onto the real login flow (in progress as of this entry). `D-PILOT`/`D-SLO` remain open, blocking task 6.D and 6.C's final numbers respectively, not 6.A. Task 6.B (Gate 3/4/5 wiring, restore drill) is the next task in `PLAN-MISSION-6.md` §3's order, and is what actually consumes this task's `release-manifest.json` digest artifact.

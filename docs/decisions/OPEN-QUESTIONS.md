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

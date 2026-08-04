# eTender frozen fixtures — capture manifest

Real, live captures against `https://etender.gov.az` (INT-01, INT-02, FR-TND-10 — empirical contract, not
fabricated data). Captured 2026-08-04, per task 1.A (`docs/reports/PLAN-MISSION-1.md` §3).

| File | Method | URL | Captured at (UTC) | HTTP status | sha256 |
|---|---|---|---|---|---|
| `event_355920_details.raw.json` | GET | `https://etender.gov.az/api/events/355920` | 2026-08-04T12:21:32Z | 200 | `dabd9dc504c630e77d577dccdfed36e05796ceabbcbd66f98fd6c51af7c85b80` |
| `event_355920_bomlines_page1.raw.json` | GET | `https://etender.gov.az/api/events/355920/bomLines?PageSize=100&PageNumber=1` | 2026-08-04T12:21:32Z | 200 | `bb0c308425394fe1a26af1c9e6f4677c8ffa05f128dcb01cba5681941a0625d4` |

Files are the exact raw response bytes, unmodified — this is layer-1 raw evidence
(`docs/adr/0003-data-authority-and-provenance.md`). Do not hand-edit them; a re-capture creates a new
dated file, never an edit of these.

## What these confirm

- `event_355920_bomlines_page1.raw.json`: `totalPages: 42`, `totalItems: 4135` — matches the audit-verified
  fact in `uniwatch-v2-project.md` ("event 355920 → 4 135 bomLines over 42 pages") exactly. Confirms BOQ is
  structured and complete at the API side; v1's loss was an ingestion defect, not a source limit.

## What these contradict — flagged, not silently reconciled

- `event_355920_details.raw.json` has **`organizationVoen: "1000418451"`** and
  **`estimatedAmount: 16922253.74`** populated. This appears to contradict the locked fact "eTender feed
  carries no VÖEN (0/103 events) and no monetary values (0/103)" (`uniwatch-v2-project.md`,
  `docs/CONTEXT.md`). Working theory, **not yet confirmed**: the 0/103 measurement was taken against the
  **events list** resource, while this capture is the **event details** resource — i.e. VÖEN/amount may be
  a details-only field, absent from the list payload (list-endpoint contract could not be captured this
  session — see `docs/decisions/OPEN-QUESTIONS.md`, 2026-08-04 entries). Recorded there for owner
  follow-up; the connector code in this task does NOT assume either resolution and surfaces both fields
  as present-when-source-provides-them, never fabricated and never silently dropped.
- `event_355920_details.raw.json` has `"eventType": 7` — consistent with the documented "`EventType`
  filter unreliable, actual value may not match request parameter" contract fact, though this specific
  capture did not itself filter by `EventType` (no comparable request/actual divergence pair was captured
  this session for the details resource; the divergence fact is carried over from the PRD's own
  28.07.2026 live-check, not re-derived here).

## What could not be captured this session

- The events **list** endpoint's exact query contract (`GET /api/events`) returned
  `400 Bad Request` (RFC 9110 problem+json, no field-level detail) for every parameter combination tried
  (`PageSize`/`PageNumber`, `pageSize`/`pageNumber`, `Skip`/`Take`, `PageIndex`, with/without `EventType`,
  with/without a publish-date range) and the bundled frontend JS did not reveal the parameter names via
  static string search. `POST /api/events` returned `405 Method Not Allowed` (confirms GET is the right
  verb, contract just not reverse-engineered from bounded probing). List-resource pagination is 1.B scope,
  not 1.A — this does not block task 1.A, which only needs one working empirical-contract resource pair
  (details + BOQ, both captured successfully above). Logged in `docs/decisions/OPEN-QUESTIONS.md` for
  whoever picks up 1.B.

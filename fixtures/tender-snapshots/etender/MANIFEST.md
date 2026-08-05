# eTender frozen fixtures — capture manifest

Real, live captures against `https://etender.gov.az` (INT-01, INT-02, FR-TND-10 — empirical contract, not
fabricated data). Captured 2026-08-04, per task 1.A (`docs/reports/PLAN-MISSION-1.md` §3) and a follow-up
discovery session the same day (events-list query contract).

| File | Method | URL | Captured at (UTC) | HTTP status | sha256 |
|---|---|---|---|---|---|
| `event_355920_details.raw.json` | GET | `https://etender.gov.az/api/events/355920` | 2026-08-04T12:21:32Z | 200 | `dabd9dc504c630e77d577dccdfed36e05796ceabbcbd66f98fd6c51af7c85b80` |
| `event_355920_bomlines_page1.raw.json` | GET | `https://etender.gov.az/api/events/355920/bomLines?PageSize=100&PageNumber=1` | 2026-08-04T12:21:32Z | 200 | `bb0c308425394fe1a26af1c9e6f4677c8ffa05f128dcb01cba5681941a0625d4` |
| `events_list_page1.raw.json` | GET | `https://etender.gov.az/api/events?EventType=&PageSize=6&PageNumber=1&EventStatus=1&Keyword=&buyerOrganizationName=&documentNumber=&publishDateFrom=&publishDateTo=&AwardedparticipantName=&AwardedparticipantVoen=&DocumentViewType=&IsArchived=false` | 2026-08-04T~13:05Z | 200 | `b6a5d6f2080ffa5170ac7b53bbe9f4c51eec76733a236ef97fe2518c720b2f63` |
| `event_355920_bomlines_page2.raw.json` | GET | `https://etender.gov.az/api/events/355920/bomLines?PageSize=100&PageNumber=2` | 2026-08-04T~14:00Z | 200 | `b87231b2ea420c3a250fc271709599c08244c9d17bccf7e381324301199f1614` |
| `event_355920_bomlines_page3.raw.json` | GET | `https://etender.gov.az/api/events/355920/bomLines?PageSize=100&PageNumber=3` | 2026-08-04T~14:00Z | 200 | `b1a601742c6bb93c2d7b15889d72c682dcf5908dd7b739127487c54f269a0f73` |
| `design_tender_search_page1.raw.json` | GET | `https://etender.gov.az/api/events?EventType=&PageSize=10&PageNumber=1&EventStatus=1&Keyword=layih%C9%99&buyerOrganizationName=&documentNumber=&publishDateFrom=&publishDateTo=&AwardedparticipantName=&AwardedparticipantVoen=&DocumentViewType=&IsArchived=false` | 2026-08-05 | 200 | `ea88088034078a47c0627cb775199310dec6b16eb03faa284a80c6dc51424ed0` |
| `design_tender_search_page2.raw.json` | GET | same URL with `PageNumber=2` | 2026-08-05 | 200 | `0e19ec745c0c9a467668bd6d5b5d6d104801b84bcc08fb16bda1b0cbd3796bcd` |

Pages 2/3 captured for task **1.B** (resumable pagination) — real, distinct pages of the same known
4135-line/42-page BOQ (page 2 starts at line id `5131548`, page 3 at `5131648`; page 1 started at
`5131448`), so a "resume after page-2 failure, don't skip to page 3" test can use genuinely different
real page content, not a duplicated or fabricated page.

Files are the exact raw response bytes, unmodified — this is layer-1 raw evidence
(`docs/adr/0003-data-authority-and-provenance.md`). Do not hand-edit them; a re-capture creates a new
dated file, never an edit of these.

## What these confirm

- `event_355920_bomlines_page1.raw.json`: `totalPages: 42`, `totalItems: 4135` — matches the audit-verified
  fact in `uniwatch-v2-project.md` ("event 355920 → 4 135 bomLines over 42 pages") exactly. Confirms BOQ is
  structured and complete at the API side; v1's loss was an ingestion defect, not a source limit.
- `events_list_page1.raw.json` fields per item: `eventId`, `eventType`, `eventStatus`,
  `buyerOrganizationName`, `eventName`, `publishDate`, `endDate`, `hasNewVersion`,
  `awardedParticipantName`, `awardedParticipantVoen`, `documentViewType`, `actualVersionId`,
  `privateRfxId`, `hasRecreated` — **no VÖEN field for the buyer and no monetary field at all**. This
  **confirms** (not just theorizes) the resolution of the VÖEN/money question below: the "0/103, no
  VÖEN, no money" fact was measured against the list resource, and it holds there. `awardedParticipantVoen`
  is a different field entirely (the winning bidder's VÖEN, only populated after award — null on every
  currently-open item captured here), not the buyer's.
- The events-list query contract discovered via a live browser network trace (not guessed): `GET
  /api/events` requires **every** listed query key to be present in the URL, even empty
  (`EventType=&Keyword=&buyerOrganizationName=&documentNumber=&publishDateFrom=&publishDateTo=&AwardedparticipantName=&AwardedparticipantVoen=&DocumentViewType=`),
  plus non-empty `PageSize`, `PageNumber`, `EventStatus` (int), `IsArchived` (bool). No CSRF token or
  cookie is required — a bare `curl` with this exact key set returns `200` (verified, see fixture above).
  This is presumably why every prior guess (task 1.A session) got a generic `400`: ASP.NET model binding
  for the query DTO fails whole-object when a required non-nullable property (`EventStatus`/`IsArchived`)
  has no bound value, with no field-level detail surfaced in the error body.

- `design_tender_search_page{1,2}.raw.json` (task 2.B, design/TEO-tender signal slice): real server-side
  `Keyword=layihə` search returns **147 total matches across 15 pages** (`PageSize=10`). Every match on
  both captured pages has `awardedParticipantName: null` (all open tenders, `EventStatus=1` — no
  awarded/closed design tender has been captured yet, see `docs/decisions/OPEN-QUESTIONS.md`). Page 1 is
  10/10 genuine design/estimate tenders (`layihə-smeta`/`layihə smeta`/`layihələndir-`/`layihələmdir-`
  — the last a real observed typo). Page 2 is 6/10 genuine, with 4 real true negatives: events `356291`
  and `356027` use the **plural noun** `layihələr-` ("projects" — e.g. "layihələrin idarə olunması" =
  "management of projects"), which shares its first 8 characters with the **verb** stem
  `layihələn-`/`layihələm-` ("to design") but diverges at the 9th (`r` vs `n`/`m`); event `356048` uses
  the possessive `layihəsi` ("its project"); event `355959` names an institute whose own name contains
  "Layihə-Konstruktor" ("Design-Construction..."), unrelated to the tender's actual subject (evacuation
  services). This is the real precision boundary the classifier in `packages/tender/design_tender_signal.py`
  is built against.

## Resolved — see `docs/decisions/OPEN-QUESTIONS.md` for the full record

- ~~VÖEN/monetary value contradiction~~ — confirmed resolved: list resource has neither field (buyer VÖEN
  or money), details resource has both. Not a contradiction; two different subresources with different
  shapes, exactly what `FR-TND-07` (independent subresource status) anticipates.
- ~~Events-list query contract not captured~~ — confirmed resolved: see the contract above. Unblocks task
  1.B (resumable pagination), which has not started.

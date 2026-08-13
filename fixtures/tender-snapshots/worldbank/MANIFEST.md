# World Bank Projects API frozen fixtures — capture manifest

Real, live captures against `https://search.worldbank.org/api/v2/projects` (INT-01, INT-02, FR-TND-10
— empirical contract, not fabricated data). Captured 2026-08-05, task 2.B
(`TENDER_INTELLIGENCE_SPEC.md` §5.2).

| File | Method | URL | HTTP status | sha256 |
|---|---|---|---|---|
| `az_donor_pipeline_page_os0.raw.json` | GET | `https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=AZ&rows=10&os=0` | 200 | `f3d896a03364c8eacefd9121c5ccca121fabbeac337387f73a1b31024d7756c2` |
| `az_donor_pipeline_page_os10.raw.json` | GET | `https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=AZ&rows=10&os=10` | 200 | `33a6f8e379da24021cc1d3fa48c213bfa7fe52abf41ee085fc13b08b77d5d5ba` |
| `az_v3_with_status_page_os0.raw.json` | GET | `https://search.worldbank.org/api/v3/projects?format=json&rows=100&fl=id,project_name,status,last_stage_reached_name,boardapprovaldate,borrower,impagency,totalamt,proj_last_upd_date,public_disclosure_date&apilang=en&countrycode_exact=AZ&os=0` | 200 | `120bcf64dbd951e857fc6574be141f95adc886752ba2109c35ba29add6b18b1b` |

Files are the exact raw response bytes, unmodified — layer-1 raw evidence
(`docs/adr/0003-data-authority-and-provenance.md`). Do not hand-edit them; a re-capture creates a new
dated file, never an edit of these.

## 2026-08-12 addendum — `v2` confirmed stale; `v3` capture added

The `v2` endpoint captured above went stale for Azerbaijan sometime around early/mid-2024 (confirmed via
a dedicated verification session, `docs/decisions/OPEN-QUESTIONS.md`, 2026-08-12 entries) — a re-fetch of
the exact same `v2` query on 2026-08-12 returned the identical `total: 79`/status breakdown as the
2026-08-05 capture above, byte-for-byte on the count, while the real `projects.worldbank.org` site had
moved on (95 total projects, `P505208` re-approved Active, two new Pipeline projects). `az_v3_with_status_page_os0.raw.json`
is a real, live capture of the *current* World Bank data for Azerbaijan via the `v3` endpoint, captured
2026-08-12, with an explicit `fl=` field-list parameter (reverse-engineered from `projects.worldbank.org`'s
own network traffic via `read_network_requests` — the site's JS requests `status`/`last_stage_reached_name`
explicitly; `v3`'s default field projection omits them, which is why earlier ad hoc `v3` probes that
session appeared to show no status field at all). `total: 95`, breakdown `{Pipeline: 2, Active: 3,
Closed: 72, Dropped: 18}`, matching the live site exactly at capture time. This fixture is evidence for
a *future* connector-migration task (`docs/superpowers/plans/2026-08-12-worldbank-v3-contract-discovery.md`)
— it does not itself change `packages/tender/worldbank_connector.py`, which still reads `v2` as of this
addendum.

## What these confirm

- Azerbaijan has 79 total World Bank projects on record (`total: "79"` in both pages). Statuses
  observed across the full set (fetched separately during reconnaissance, not itself a frozen fixture):
  4 `Active`, 61 `Closed`, 13 `Dropped`, 1 `Pipeline`. The one `Pipeline`-status record (`P505208`,
  "Azerbaijan Scaling-Up Renewable Energy Project", `totalamt: "250,000,000"`, not present in either of
  these two 10-row pages — it appears later in the full 79-record set) is the genuine early-signal case
  this task targets: it has no `boardapprovaldate`, no `borrower`, no `impagency` (all three keys
  entirely absent from that record, not merely null) because the project has not yet been approved.
  This is real API behavior, not a gap in this fixture.
- Top-level pagination fields have mixed real types: `rows` is a JSON number (`10`), while `os`, `page`,
  `total` are JSON strings (`"0"`/`"1"`/`"79"`) — verified by inspecting the parsed JSON, not assumed.
- Field presence across all 79 real AZ records (checked during reconnaissance across the full set, not
  just these two 10-row pages) is genuinely heterogeneous — e.g. `borrower` appears in 28/79, `impagency`
  in 33/79, `boardapprovaldate` in 62/79, `sector2` in 51/79, `closingdate` in 55/79. `sector1.Name` and
  `mjtheme_namecode[].name` are non-empty in most records (71/79, 70/79) but genuinely blank strings in
  some, independent of status. This is why task 2.B's contract needs an `optional` field concept that
  task 1.A's eTender contracts never needed (eTender's resources had a fixed shape every time).
- The two pages captured here contain 20 genuinely distinct project ids (no overlap) — `P181649` through
  `P122943` on page 1 (`os=0`), `P125741` through `P104985` on page 2 (`os=10`) — proving real, distinct
  content for the "resume after page-1 failure, don't skip/duplicate page 2" pagination test, the same
  reason task 1.B captured distinct real BOM-line pages.

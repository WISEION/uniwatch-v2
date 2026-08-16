# fixtures/legacy-snapshots/

Contract document for the **one and only** way legacy (v1) data may ever enter this
repository: a bounded, human-exported JSON snapshot, produced *out-of-band* by a person
who has access to the legacy system, then dropped into this directory after explicit
review. Nothing in this repo ever reads or connects to the legacy system directly —
`tools/check_v1_untouched.py` enforces that no code, config, test, or migration in this
repo holds a legacy path literal or credential (FR-MIG-04, NEG-01, NEG-02). A snapshot
file here is evidence a human carried across the boundary by hand, not something any
job or connector fetched.

## What this is for

`packages/tender/shadow_comparison.py` (FR-MIG-03, master plan Section24.4, Phase 6
task 6.A) compares a legacy snapshot against v2's own already-ingested records for the
same bounded source + date range — count, IDs, status, key details, BOQ
presence/completeness — and classifies every discrepancy into one of four buckets
(`v1_loss`, `v2_defect`, `source_drift`, `expected_semantic_difference`), or reports it
honestly as unresolved when neither side's evidence settles which bucket applies.
`compare_snapshots()` is a pure function; it does not know or care where the list of
dicts came from. This document fixes the shape a real export must have so that the
function can consume it.

## Snapshot file shape

A snapshot file is a JSON object:

```json
{
  "source": "etender",
  "date_range": { "from": "2026-07-01", "to": "2026-07-31" },
  "exported_at": "2026-08-14T09:00:00",
  "exported_by": "a human identity/process, not a system credential",
  "records": [ /* one object per tender record, shape below */ ]
}
```

Only `records` is consumed directly by `compare_snapshots()` (as `v1_snapshot`); the
caller job that loads this file is expected to also carry `source`/`date_range` forward
so the eventual comparison run (and its exit-gate report, Phase 6 task 6.E) can state
exactly which bounded slice was checked — this module never infers scope on its own.

Each entry in `records` matches the shape `shadow_comparison.py`'s module docstring
documents, reproduced here for a legacy exporter who has never opened that file:

```json
{
  "source_record_id": "355920",
  "record_kind": "design_tender",
  "status": "open",
  "key_details": {
    "buyer_organization_name": "...",
    "event_name": "...",
    "publish_date": "2026-07-03"
  },
  "captured_at": "2026-07-15T00:00:00",
  "boq": {
    "present": true,
    "completeness_status": "complete",
    "line_count": 4135
  }
}
```

- `source_record_id` — required, string. The same identity a v2 record for this same
  logical tender would carry, so the two sides can be matched by a plain set
  intersection. If the legacy system's own primary key differs in format from v2's
  (e.g. zero-padded vs not), the export is responsible for normalizing to whatever key
  v2 uses — `compare_snapshots()` does no fuzzy/heuristic ID matching, exactly like
  `packages/decision/matching.py`'s material match documents its own heuristic scope
  rather than silently guessing wider.
- `record_kind` — optional, string or `null`. Only needed when this bounded slice mixes
  more than one kind of record and the caller wants `compare_snapshots()`'s
  `v1_covers_record_kinds`/`v2_covers_record_kinds` scope arguments to distinguish
  in-scope absences (`v1_loss`/`v2_defect`) from genuinely out-of-scope ones
  (`expected_semantic_difference`). Leave `null` if the export can't tell — the
  comparison then reports the affected discrepancy as unresolved rather than guessing.
- `status` — required key (value may be `null`), the legacy system's own status label
  for this record at export time.
- `key_details` — required, flat object of scalar fields. Only include fields the
  export can state with confidence — a field the legacy exporter cannot fill in
  confidently should be omitted entirely (a genuinely missing key), never filled with a
  placeholder value; a present-but-different set of keys between the two sides is
  itself informative (`shadow_comparison.py` reports it as `expected_semantic_difference`
  — a structural schema difference, not a value drift).
- `captured_at` — optional, ISO-8601 string or `null`. When present on both sides, lets
  `compare_snapshots()` tell a genuine source-data change (`source_drift`) apart from an
  unexplained value mismatch. Omit/`null` when the legacy export cannot state a real
  capture timestamp for this specific record — a fabricated timestamp would let a real
  defect masquerade as drift.
- `boq` — `null` when this record kind has no BOQ concept in the legacy system at all;
  otherwise an object with `present` (bool, required), `completeness_status` (string or
  `null` — `null` means the legacy system tracked no completeness concept even though a
  BOQ existed), and `line_count` (int or `null`).

## What must never land here

- Real legacy data, checked in without an explicit human review of that specific file
  and PR — this directory holds a *contract*, not a data drop.
- A live connection, credential, or path literal referencing the legacy system's own
  storage — `tools/check_v1_untouched.py` scans this whole repository (this directory
  included) for exactly that.
- A silently fabricated field value standing in for something the export genuinely does
  not know (AGENTS.md hard ban #3) — omit the field/leave it `null` instead, and let
  `shadow_comparison.py`'s honest-unresolved path surface it.

## Files here

- `example_v1_snapshot.synthetic.json` — a synthetic worked example (watermarked
  `"_synthetic": true` at the top level and inside every record's `key_details`,
  same discipline `packages/vendor/synthetic_provider.py` already applies to its own
  fixtures). Every ID, organization name, and date in it is fabricated for
  illustration; it is not, and must never be mistaken for, a real export.

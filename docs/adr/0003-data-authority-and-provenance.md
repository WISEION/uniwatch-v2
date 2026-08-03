# ADR-0003 — Data authority and provenance: four immutable layers

**Status:** Accepted
**Date:** 2026-08-04
**Requirements:** DM-01, DM-02, DM-03, DM-04, DM-05, DM-06, INV-01, INV-02, INV-04, INV-05, INV-11, INV-12, master plan §8

## Context

v1's core, repeated failure mode (PRD/audit): BOQ reported `complete` after loading only page 1 (P001); a rejected human link decision was silently restored by a later ingestion run (P003, RN-04); details/BOQ changes were invisible to history (P108); no optimistic concurrency existed on important edits (P115). All of these are one root cause: no enforced separation between "what the source said," "what we derived from it," and "what a human decided." v2 must make that separation structural, not conventional.

## Decision

Every significant record moves through exactly four layers (master plan §8.1), and a lower layer never overwrites a higher one:

1. **Raw immutable evidence** — the exact source response or document, as received, checksummed (`raw_snapshot_id` + checksum). Never edited or deleted; a re-fetch creates a new raw snapshot.
2. **Normalized fact** — typed representation derived from raw evidence, carrying `parser_version`/`normalizer_version`, without erasing the raw provenance link. Changing the parser creates a new normalized version, not an in-place rewrite (`DM-02`).
3. **Derived signal/score** — computed from normalized facts, versioned by the rule/model that produced it.
4. **Human decision** — append-only, carrying actor, role, reason, and the input snapshot the human decided against (`FR-DEC-01`, `INV-05`).

**Layer 3 never writes itself as layer 4, and layer 1/2 (ingestion) never overwrites layer 4 (`INV-01`, `DM-04`).** An auto-match is always a `candidate` row in its own append-only table, distinct from the `human decision` table; re-ingestion appends new candidates, it never updates or deletes an existing human decision row.

Every significant record additionally carries, as first-class fields (not derived-on-read):

- `id` (internal immutable identifier), `source_id`, `source_record_id`, `source_url`/document id;
- `captured_at`, `effective_at`, `observed_at` (`DM-03`) — kept distinct, never collapsed into a single timestamp;
- `data_origin` ∈ `{real, synthetic, legacy, derived}`;
- `reality_status` ∈ `{verified, source_asserted, unverified, missing, synthetic}`;
- `freshness_status` ∈ `{fresh, stale, expired, unknown}`;
- `completeness_status` ∈ `{complete, partial, failed, unknown}` — `complete` is set only after proven reconciliation, never assumed from a page-1 response (`INV-04`; this is exactly the P001 failure mode);
- `quality_flags` with a link to the exception queue where relevant.

One business fact = one authoritative entity (`DM-01`, `INV-02`) — no second domain keeps its own mutable copy "for convenience"; it references the authoritative record instead (see ADR-0001).

Important edits (human-authored, business-effect-bearing) use optimistic concurrency — an ETag/version precondition, not last-write-wins (`INV-12`).

Datastore: PostgreSQL, schema owned by versioned migrations with a ledger; schema changes and backfills are explicit, separate operations, never implicit side effects of application startup (`DM-06` — detailed in `migrations/README.md` and ADR for FR-PLT-12, tracked as part of this same Phase 0 task).

## Consequences

- Every table that holds "layer 1/2/3" data needs an immutable/versioned design from the start (append or new-version-row, not `UPDATE`) — retrofitting this after Phase 1 ingestion code exists would be expensive; it must be right in the first migrations.
- The human-decision tables are physically separate from the candidate/derived tables in every domain that has both (tender↔project linking in Phase 2, Bid/No-Bid in Phase 4) — this is why P003/P004/P005 need a domain-invariant contract now even though their UI/API lands later (see `docs/reports/PLAN-MISSION-1.md` §5, remark #1).
- `completeness_status = complete` requires a reconciliation proof object (expected vs. observed pages/rows/checksum) to exist before the flag is set — this is a hard gate in the BOQ import code, not a best-effort label.

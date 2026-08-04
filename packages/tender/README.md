# packages/tender

Tender ingestion, raw/normalized versioning, BOQ completeness, signals, tender↔project linking (`FR-TND-*`, `FR-DQ-*`, `FR-JOB-*` for the ingestion side). Never reads `packages/vendor` internals directly (`docs/adr/0001-modular-monolith-boundaries.md`).

Phase 1 (raw snapshot, normalized versioning, resumable BOQ pagination, schema drift, exception queue) is done. Phase 2 task 2.A adds atomic BOQ line decomposition (`boq_line_model.py`, `boq_lines_store.py`) — unit canonicalization, preliminaries/provisional-sum/prime-cost typing, hidden spec-requirement extraction (`TENDER_INTELLIGENCE_SPEC.md` §5.1, P308).

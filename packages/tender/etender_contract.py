"""Concrete eTender source contracts (INT-01). Built directly from the
real, live-captured fixtures in fixtures/tender-snapshots/etender/ (see
MANIFEST.md) — not from official documentation, which does not exist for
this source. `budgetCategoryCode`, `cpvCode`, `recreatedFromRfxId`,
`recreatedFromEventId`, `recreatedFromDocumentNumber` were captured as
`null`; a future capture with them populated is a data variation, not
schema drift (see schema_drift.py's null-value rule)."""

from __future__ import annotations

from .source_contract import FieldSpec, SourceContract

EVENT_DETAILS_CONTRACT = SourceContract(
    name="etender.event_details",
    identity_query_keys=("id",),
    fields=(
        FieldSpec("id", "number"),
        FieldSpec("rfxId", "number"),
        FieldSpec("eventId", "number"),
        FieldSpec("tenderName", "string"),
        FieldSpec("organizationName", "string"),
        FieldSpec("organizationVoen", "string"),
        FieldSpec("envelopeDate", "number"),
        FieldSpec("endDate", "number"),
        FieldSpec("publishDate", "number"),
        FieldSpec("startDate", "number"),
        FieldSpec("budgetCategoryCode", "null"),
        FieldSpec("address", "string"),
        FieldSpec("cpvCode", "null"),
        FieldSpec("eventType", "number"),
        FieldSpec("isRedirectionAvailable", "boolean"),
        FieldSpec("minNumberOfSuppliers", "number"),
        FieldSpec("estimatedAmount", "number"),
        FieldSpec("recreatedFromRfxId", "null"),
        FieldSpec("recreatedFromEventId", "null"),
        FieldSpec("documentNumber", "string"),
        FieldSpec("recreatedFromDocumentNumber", "null"),
        FieldSpec("evaluatedFinalScore", "number"),
        FieldSpec("categoryCodes", "array"),
    ),
)

BOM_LINES_PAGE_CONTRACT = SourceContract(
    name="etender.bom_lines_page",
    identity_query_keys=("event_id", "PageNumber"),
    fields=(
        FieldSpec("currentPage", "number"),
        FieldSpec("totalPages", "number"),
        FieldSpec("pageSize", "number"),
        FieldSpec("itemsInPage", "number"),
        FieldSpec("totalItems", "number"),
        FieldSpec("items", "array"),
        FieldSpec("hasPreviousPage", "boolean"),
        FieldSpec("hasNextPage", "boolean"),
        FieldSpec("firstItem", "number"),
        FieldSpec("lastItem", "number"),
    ),
)

# Captured from fixtures/tender-snapshots/etender/events_list_page1.raw.json
# (unfiltered, default EventStatus=1, page 1 — the 2026-08-04 follow-up
# discovery session, see docs/decisions/OPEN-QUESTIONS.md). No buyer VOEN
# and no monetary field on list items — confirmed empirically, not a gap
# in this contract (see MANIFEST.md).
#
# identity_query_keys is deliberately just PageNumber here: this task only
# proves the ingest mechanism against the one captured (default-filter)
# page, not full filter-aware list pagination — that job/params identity
# model belongs to task 1.B (resumable pagination), which owns the real
# identity_query_keys for every filter combination the worker can request.
EVENTS_LIST_PAGE_CONTRACT = SourceContract(
    name="etender.events_list_page",
    identity_query_keys=("PageNumber",),
    fields=(
        FieldSpec("currentPage", "number"),
        FieldSpec("totalPages", "number"),
        FieldSpec("pageSize", "number"),
        FieldSpec("itemsInPage", "number"),
        FieldSpec("totalItems", "number"),
        FieldSpec("items", "array"),
        FieldSpec("hasPreviousPage", "boolean"),
        FieldSpec("hasNextPage", "boolean"),
        FieldSpec("firstItem", "number"),
        FieldSpec("lastItem", "number"),
    ),
)

# Per-item shape inside BOM_LINES_PAGE_CONTRACT's `items` array (INT-01,
# INT-02). Verified against every item across all 3 captured pages of
# event 355920's BOQ (see MANIFEST.md) -- categoryCode is constant across
# every item in this fixture (a page/tender-level classification, not a
# per-line distinguishing code), kept anyway because it is the only real
# field mapping to TENDER_INTELLIGENCE_SPEC.md §5.1's `code` concept.
BOM_LINE_ITEM_CONTRACT = SourceContract(
    name="etender.bom_lines_page.item",
    identity_query_keys=("id",),
    fields=(
        FieldSpec("id", "number"),
        FieldSpec("name", "string"),
        FieldSpec("description", "string"),
        FieldSpec("unitOfMeasure", "string"),
        FieldSpec("quantity", "number"),
        FieldSpec("categoryCode", "string"),
    ),
)

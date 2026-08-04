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

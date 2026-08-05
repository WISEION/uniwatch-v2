"""Concrete eTender source contracts (INT-01). Built directly from the
real, live-captured fixtures in fixtures/tender-snapshots/etender/ (see
MANIFEST.md) — not from official documentation, which does not exist for
this source. `budgetCategoryCode`, `cpvCode`, `recreatedFromRfxId`,
`recreatedFromEventId`, `recreatedFromDocumentNumber` were captured as
`null`; a future capture with them populated is a data variation, not
schema drift (see schema_drift.py's null-value rule)."""

from __future__ import annotations

from .source_contract import FieldSpec, SourceContract

# eTender returns the same paged-list envelope around every list resource
# (BOM lines, events, procurement plans) — verified identical across every
# captured fixture (see MANIFEST.md). Only each resource's `items` shape
# differs, which is what the per-item contracts below cover.
PAGED_LIST_ENVELOPE_FIELDS = (
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
)

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
    fields=PAGED_LIST_ENVELOPE_FIELDS,
)

# Captured from fixtures/tender-snapshots/etender/events_list_page1.raw.json
# (unfiltered, default EventStatus=1, page 1 — the 2026-08-04 follow-up
# discovery session, see docs/decisions/OPEN-QUESTIONS.md). No buyer VOEN
# and no monetary field on list items — confirmed empirically, not a gap
# in this contract (see MANIFEST.md).
#
# identity_query_keys covers every real query parameter this resource
# accepts (the full set discovered in the 2026-08-04 follow-up session),
# not just PageNumber — task 2.B's design-tender signal slice needs to page
# through a *filtered* search (Keyword=layihə) without colliding under the
# same identity_key as an unfiltered page with the same PageNumber. Closes
# the "events-list filter-aware identity, if needed in Phase 2" gap left
# open by task 1.E.
EVENTS_LIST_PAGE_CONTRACT = SourceContract(
    name="etender.events_list_page",
    identity_query_keys=(
        "EventType",
        "PageSize",
        "PageNumber",
        "EventStatus",
        "Keyword",
        "buyerOrganizationName",
        "documentNumber",
        "publishDateFrom",
        "publishDateTo",
        "AwardedparticipantName",
        "AwardedparticipantVoen",
        "DocumentViewType",
        "IsArchived",
    ),
    fields=PAGED_LIST_ENVELOPE_FIELDS,
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

# Captured from fixtures/tender-snapshots/etender/app_list_page1_2026.raw.json and
# app_list_zaqatala_2026.raw.json (task 2.B, procurement-plan signal slice). API discovered by static
# analysis of eTender's Angular bundle (main.f5154a38aaa91629.js), not documentation -- confirmed live
# 2026-08-05. Year/PageNumber/BuyerOrganizationName are all part of identity from the start (unlike
# EVENTS_LIST_PAGE_CONTRACT, which had to be widened after the fact) -- a filtered and unfiltered page
# for the same Year/PageNumber must not collide under the same identity_key.
APP_LIST_PAGE_CONTRACT = SourceContract(
    name="etender.app_list_page",
    identity_query_keys=("Year", "PageNumber", "BuyerOrganizationName"),
    fields=PAGED_LIST_ENVELOPE_FIELDS,
)

# Per-item shape inside APP_LIST_PAGE_CONTRACT's `items` array. Verified against every item across
# both captured pages (see MANIFEST.md) -- identical key-set in both, no optional fields observed yet.
APP_ITEM_CONTRACT = SourceContract(
    name="etender.app_list_page.item",
    identity_query_keys=("id",),
    fields=(
        FieldSpec("id", "number"),
        FieldSpec("organizationName", "string"),
        FieldSpec("year", "number"),
        FieldSpec("createDate", "string"),
    ),
)

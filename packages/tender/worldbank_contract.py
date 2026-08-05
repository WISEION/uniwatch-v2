"""Concrete World Bank Projects API source contracts (INT-01). Built
directly from a real, live capture against
https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=AZ
(see fixtures/tender-snapshots/worldbank/MANIFEST.md) — not from official
API documentation, which does not enumerate every field this endpoint
actually returns.

Unlike eTender's fixed-shape resources (etender_contract.py), this API's
project records genuinely vary in which optional fields are present
depending on project status (a Pipeline-stage project has no
`boardapprovaldate`/`borrower`/`impagency` because those facts don't exist
yet, not because of a parsing gap) — hence FieldSpec(..., optional=True)
on those fields."""

from __future__ import annotations

from .source_contract import FieldSpec, SourceContract

DONOR_PIPELINE_PAGE_CONTRACT = SourceContract(
    name="worldbank.donor_pipeline_page",
    identity_query_keys=("countrycode_exact", "os"),
    fields=(
        FieldSpec("rows", "number"),
        FieldSpec("os", "string"),
        FieldSpec("page", "string"),
        FieldSpec("total", "string"),
        FieldSpec("projects", "object"),
        FieldSpec("facets", "object"),
    ),
)

# Per-item shape inside DONOR_PIPELINE_PAGE_CONTRACT's `projects` object
# values (INT-01, INT-02). This declares the FULL observed shape (every
# field the two captured fixture pages actually return), not just the
# subset signal_model.py reads -- same convention as etender_contract.py's
# EVENT_DETAILS_CONTRACT, so an unrelated new field appearing later is real
# drift, not noise from an intentionally partial contract.
#
# Required vs optional is decided from the WIDER 79-record AZ reconnaissance
# done for this task (2026-08-05, see MANIFEST.md), not just these 20
# fixture records -- some fields (board_approval_month, boardapprovaldate,
# supplementprojectflg) happen to be present in all 20 fixture records but
# are known, from that wider check, to be genuinely absent on some real
# records (e.g. Pipeline-status project P505208 has no boardapprovaldate at
# all). Marking them required here would pass today's fixtures but flag a
# false drift the first time a Pipeline-stage or Dropped-stage project
# appears in a captured page.
DONOR_PIPELINE_PROJECT_CONTRACT = SourceContract(
    name="worldbank.donor_pipeline_page.project",
    identity_query_keys=("id",),
    fields=(
        FieldSpec("id", "string"),
        FieldSpec("project_name", "string"),
        FieldSpec("status", "string"),
        FieldSpec("projectstatusdisplay", "string"),
        FieldSpec("totalamt", "string"),
        FieldSpec("totalcommamt", "string"),
        FieldSpec("country_namecode", "string"),
        FieldSpec("countryname", "array"),
        FieldSpec("countrycode", "array"),
        FieldSpec("countryshortname", "string"),
        FieldSpec("regionname", "string"),
        FieldSpec("source", "array"),
        FieldSpec("mjthemecode", "string"),
        FieldSpec("mjtheme_namecode", "array"),
        FieldSpec("theme1", "string"),
        FieldSpec("sector1", "object"),
        FieldSpec("url", "string"),
        FieldSpec("teamleadname", "string"),
        FieldSpec("lendinginstr", "string"),
        FieldSpec("lendinginstrtype", "string"),
        FieldSpec("lendprojectcost", "string"),
        FieldSpec("prodline", "string"),
        FieldSpec("prodlinetext", "string"),
        FieldSpec("productlinetype", "string"),
        FieldSpec("proj_and_ln_country", "array"),
        FieldSpec("projectdocs", "array"),
        FieldSpec("curr_ibrd_commitment", "string"),
        FieldSpec("curr_ida_commitment", "string"),
        FieldSpec("curr_total_commitment", "string"),
        FieldSpec("ibrdcommamt", "string"),
        FieldSpec("idacommamt", "string"),
        # Optional -- genuinely absent on some real records (see docstring above).
        FieldSpec("borrower", "string", optional=True),
        FieldSpec("impagency", "string", optional=True),
        FieldSpec("boardapprovaldate", "string", optional=True),
        FieldSpec("board_approval_month", "string", optional=True),
        FieldSpec("closingdate", "string", optional=True),
        FieldSpec("approvalfy", "string", optional=True),
        FieldSpec("p2a_flag", "string", optional=True),
        FieldSpec("p2a_updated_date", "string", optional=True),
        FieldSpec("supplementprojectflg", "string", optional=True),
        FieldSpec("envassesmentcategorycode", "string", optional=True),
        FieldSpec("grantamt", "string", optional=True),
        FieldSpec("sector", "array", optional=True),
        FieldSpec("sector2", "object", optional=True),
        FieldSpec("sector3", "object", optional=True),
        FieldSpec("sector_namecode", "array", optional=True),
        FieldSpec("sectorcode", "array", optional=True),
        FieldSpec("mjsector_namecode", "array", optional=True),
        FieldSpec("theme2", "string", optional=True),
        FieldSpec("theme3", "string", optional=True),
        FieldSpec("theme4", "string", optional=True),
        FieldSpec("theme_list", "array", optional=True),
        FieldSpec("theme_namecode", "array", optional=True),
        FieldSpec("themecode", "string", optional=True),
        FieldSpec("ln_country_id", "array", optional=True),
        FieldSpec("ln_country_id_desc", "array", optional=True),
    ),
)

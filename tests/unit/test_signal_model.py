"""INV-15, INV-17: a Signal must carry the fact tuple (value, source_ref via
raw_snapshot_id, observed_at, ttl_class, confidence) plus a minimal object
binding -- built from real World Bank Projects API records captured
2026-08-05 (see fixtures/tender-snapshots/worldbank/MANIFEST.md)."""

from __future__ import annotations

from packages.tender.signal_model import build_donor_pipeline_signal


def test_pipeline_stage_project_with_no_approval_yet():
    # Real record shape -- a genuine Pipeline-status project with
    # borrower/impagency/boardapprovaldate all absent (not merely null).
    project = {
        "id": "P505208",
        "project_name": "Azerbaijan Scaling-Up Renewable Energy Project",
        "status": "Pipeline",
        "projectstatusdisplay": "Pipeline",
        "totalamt": "250,000,000",
        "countryname": ["Republic of Azerbaijan"],
        "countrycode": ["AZ"],
        "regionname": "Europe and Central Asia",
        "source": ["IBRD"],
        "mjthemecode": "2",
        "mjtheme_namecode": [{"name": "", "code": "2"}],
        "sector1": {"Name": "", "Percent": 0},
        "url": "https://projects.worldbank.org/en/projects-operations/project-detail/P505208",
        "teamleadname": "Roger Coma Cunill,Florian Kitt",
        "lendinginstr": "Investment Project Financing",
    }
    signal = build_donor_pipeline_signal(
        project, raw_snapshot_id=42, observed_at="2026-08-05T12:00:00+00:00", correlation_id="corr-1"
    )
    assert signal.signal_type == "donor_pipeline_project"
    assert signal.source == "worldbank_projects_api"
    assert signal.raw_snapshot_id == 42
    assert signal.value["project_id"] == "P505208"
    assert signal.value["total_amount_usd_text"] == "250,000,000"
    assert signal.value["board_approval_date"] is None
    assert signal.observed_at == "2026-08-05T12:00:00+00:00"
    assert signal.ttl_class == "funding_decision"
    assert signal.confidence == "official_source"
    # Honest absence -- neither key exists on this real record, not fabricated.
    assert signal.object_customer is None
    assert signal.object_region == "Republic of Azerbaijan"
    # mjtheme_namecode[0]["name"] is blank on this real record -- falls back to the code.
    assert signal.object_project_type == "2"


def test_active_project_with_named_theme_and_agency():
    # Real record shape -- project_name/impagency/theme name all populated.
    project = {
        "id": "P174379",
        "project_name": "Regional Connectivity and Development Project",
        "status": "Active",
        "projectstatusdisplay": "Active",
        "totalamt": "65,000,000",
        "countryname": ["Republic of Azerbaijan"],
        "countrycode": ["AZ"],
        "regionname": "Europe and Central Asia",
        "source": ["IBRD"],
        "mjthemecode": "5",
        "mjtheme_namecode": [{"name": "Public Administration", "code": "5"}],
        "sector1": {"Name": "Rural and Inter-Urban Roads", "Percent": 100},
        "url": "https://projects.worldbank.org/en/projects-operations/project-detail/P174379",
        "teamleadname": "Some Team Lead",
        "lendinginstr": "Investment Project Financing",
        "borrower": "Ministry of Finance",
        "impagency": "State Roads Agency",
        "boardapprovaldate": "2021-05-01T00:00:00Z",
    }
    signal = build_donor_pipeline_signal(
        project, raw_snapshot_id=43, observed_at="2026-08-05T12:00:00+00:00", correlation_id="corr-2"
    )
    assert signal.object_customer == "State Roads Agency"  # impagency preferred over borrower
    assert signal.object_project_type == "Public Administration"  # named theme preferred over code
    assert signal.value["board_approval_date"] == "2021-05-01T00:00:00Z"

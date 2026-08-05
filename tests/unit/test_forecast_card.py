"""Unit tests for the pure forecast-card assembler (TENDER_INTELLIGENCE_SPEC.md
§5.4, P311)."""

from packages.tender.forecast_card import build_forecast_card


def test_non_composite_object_has_no_card():
    rows = [
        {
            "signal_type": "design_tender",
            "source": "etender",
            "raw_snapshot_id": 1,
            "value": {"event_id": 100},
            "observed_at": "2026-08-01T00:00:00+00:00",
        },
    ]
    assert build_forecast_card("Siyəzən", rows) is None


def test_composite_object_without_budget_signal_has_no_budget_estimate():
    rows = [
        {
            "signal_type": "design_tender",
            "source": "etender",
            "raw_snapshot_id": 1,
            "value": {"event_id": 100},
            "observed_at": "2026-08-01T00:00:00+00:00",
        },
        {
            "signal_type": "procurement_plan",
            "source": "etender",
            "raw_snapshot_id": 2,
            "value": {"app_id": 200},
            "observed_at": "2026-08-02T00:00:00+00:00",
        },
    ]
    card = build_forecast_card("Zaqatala", rows)

    assert card is not None
    assert card.object_region == "Zaqatala"
    assert card.is_composite is True
    assert card.signal_types == frozenset({"design_tender", "procurement_plan"})
    assert card.budget_estimate is None
    assert len(card.evidence_chain) == 2
    assert card.evidence_chain[0]["signal_type"] == "design_tender"
    assert card.evidence_chain[0]["raw_snapshot_id"] == 1
    assert card.evidence_chain[0]["observed_at"] == "2026-08-01T00:00:00+00:00"
    assert card.evidence_chain[1]["signal_type"] == "procurement_plan"


def test_composite_object_with_donor_pipeline_signal_has_budget_estimate():
    rows = [
        {
            "signal_type": "design_tender",
            "source": "etender",
            "raw_snapshot_id": 1,
            "value": {"event_id": 100},
            "observed_at": "2026-08-01T00:00:00+00:00",
        },
        {
            "signal_type": "donor_pipeline_project",
            "source": "worldbank_projects_api",
            "raw_snapshot_id": 3,
            "value": {
                "total_amount_usd_text": "250,000,000",
                "url": "https://projects.worldbank.org/en/projects-operations/project-detail/P999999",
            },
            "observed_at": "2026-08-03T00:00:00+00:00",
        },
    ]
    card = build_forecast_card("Zaqatala", rows)

    assert card is not None
    assert card.budget_estimate == {
        "source": "donor_pipeline_project",
        "total_amount_usd_text": "250,000,000",
        "url": "https://projects.worldbank.org/en/projects-operations/project-detail/P999999",
    }

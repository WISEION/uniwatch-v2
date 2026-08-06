"""Unit tests for ReputationFact (TENDER_INTELLIGENCE_SPEC.md Section6.2,
task 3.B). Event-type categories are taken directly from Section6.2's own
examples: "держит ли цену после выигрыша" (price_held_after_win / its
negative counterpart price_broken_after_win), "держит ли сроки"
(delivered_on_time / missed_deadline -- missed_deadline is P313's own
worked example), "качество/сертификаты/рекламации"
(certification_verified / quality_complaint), "финансовая дисциплина"
(financial_discipline_breach), "поведение под давлением... продал ли
чужую бронь в дефицит" (resold_reserved_stock_under_pressure)."""

from __future__ import annotations

import pytest

from packages.vendor.reputation_model import (
    NEGATIVE_EVENT_TYPES,
    POSITIVE_EVENT_TYPES,
    ReputationFact,
    is_negative_event,
)


def test_every_negative_event_type_is_classified_negative():
    assert all(is_negative_event(event_type) for event_type in NEGATIVE_EVENT_TYPES)


def test_every_positive_event_type_is_classified_positive():
    assert all(not is_negative_event(event_type) for event_type in POSITIVE_EVENT_TYPES)


def test_unknown_event_type_raises_instead_of_guessing():
    with pytest.raises(ValueError):
        is_negative_event("not-a-real-event-type")


def test_constructing_a_fact_with_an_unknown_event_type_raises():
    with pytest.raises(ValueError):
        ReputationFact(
            data_realm="vendor-sandbox",
            watermark="SYNTHETIC",
            vendor_name="Test Vendor",
            event_type="not-a-real-event-type",
            project_ref=None,
            source_ref="test",
            observed_at="2026-08-06T00:00:00+00:00",
            ttl_days=30,
        )


def test_a_valid_fact_constructs_cleanly():
    fact = ReputationFact(
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        vendor_name="Test Vendor",
        event_type="missed_deadline",
        project_ref="project-x",
        source_ref="voice-note-2026-08-06",
        observed_at="2026-08-06T00:00:00+00:00",
        ttl_days=90,
    )
    assert fact.event_type == "missed_deadline"
    assert fact.project_ref == "project-x"

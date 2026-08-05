"""Real items captured 2026-08-05
(fixtures/tender-snapshots/etender/app_list_zaqatala_2026.raw.json) ground
the region-canonicalization proof: this signal type must reuse the exact
same canonicalize_region() as the design-tender slice, since that's what
makes the real cross-category intersection possible."""

from __future__ import annotations

from packages.tender.procurement_plan_signal import build_procurement_plan_signal


def test_build_signal_from_real_zaqatala_plan():
    item = {
        "id": 16820,
        "organizationName": "ZAQATALA RAYON GİGİYENA VƏ EPİDEMİOLOGİYA MƏRKƏZİ.",
        "year": 2026,
        "createDate": "2026-08-05T12:13:51.8766677",
    }
    signal = build_procurement_plan_signal(
        item, raw_snapshot_id=201, observed_at="2026-08-05T12:00:00+00:00", correlation_id="corr-app-1"
    )
    assert signal.signal_type == "procurement_plan"
    assert signal.source == "etender"
    assert signal.raw_snapshot_id == 201
    assert signal.value["app_id"] == 16820
    assert signal.value["year"] == 2026
    assert signal.ttl_class == "procurement_plan"
    assert signal.confidence == "official_source"
    assert signal.object_customer == "ZAQATALA RAYON GİGİYENA VƏ EPİDEMİOLOGİYA MƏRKƏZİ."
    # The real cross-category intersection: same canonicalizer, same region as the
    # design-tender slice's real "ZAQATALA RAYONU İCRA HAKİMİYYƏTİ" signals.
    assert signal.object_region == "Zaqatala"


def test_build_signal_region_none_for_non_regional_organization():
    item = {
        "id": 99999,
        "organizationName": "Azərbaycan Respublikası Dövlət Neft Fondu",
        "year": 2026,
        "createDate": "2026-08-05T12:00:00",
    }
    signal = build_procurement_plan_signal(
        item, raw_snapshot_id=202, observed_at="2026-08-05T12:00:00+00:00", correlation_id="corr-app-2"
    )
    assert signal.object_region is None

"""Unit tests for the pure Vendor/Offer domain model (FR-VND-05)."""

from packages.vendor.vendor_model import Offer, Vendor


def test_vendor_holds_realm_and_watermark_explicitly():
    vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Test Vendor", provider_type="synthetic", seed=1)
    assert vendor.data_realm == "vendor-sandbox"
    assert vendor.watermark == "SYNTHETIC"


def test_offer_holds_every_fr_vnd_05_field():
    offer = Offer(
        vendor_name="Test Vendor",
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        material="rebar-12mm",
        price=850.0,
        currency="AZN",
        vat_rate=18.0,
        uom="ton",
        uom_canonical_qty=1.0,
        moq=5.0,
        capacity=200.0,
        inventory=150.0,
        valid_from="2026-08-06T00:00:00+00:00",
        valid_until="2026-09-05T00:00:00+00:00",
        evidence_source="synthetic-generator",
        observed_at="2026-08-06T00:00:00+00:00",
        adverse_case=None,
    )
    assert offer.price == 850.0
    assert offer.currency == "AZN"
    assert offer.adverse_case is None

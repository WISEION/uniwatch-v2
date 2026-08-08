"""Shared parametrized contract test for every FR-VND-04 `SupplyProvider`
implementation (PLAN-MISSION-3.md §4's exit-gate criterion: "два разных
fake provider удовлетворяют контракту", requires a contract-test-suite
log on both providers, not two independently-written unit suites that
happen to agree by construction). `test_provider_contract.py` only proves
a fake stub class satisfies the `Protocol` structurally -- this file runs
all three REAL providers (`SyntheticProvider`, `CsvProvider`,
`NapkinOcrProvider`) through the identical set of assertions, so a future
fourth provider is proven against the same bar mechanically, not by
eyeballing separate test files."""

from __future__ import annotations

import json

import pytest

from packages.vendor.csv_provider import CsvProvider
from packages.vendor.napkin_provider import NapkinOcrProvider
from packages.vendor.provider_contract import SupplyProvider
from packages.vendor.synthetic_provider import SyntheticProvider
from packages.vendor.vendor_model import Offer, Vendor

_AS_OF = "2026-08-08T00:00:00+00:00"

_CSV_CONTENT = (
    "vendor_name,material,price,currency,vat_rate,uom,uom_canonical_qty,moq,capacity,inventory,valid_from,valid_until\n"
    "Contract Test Vendor,cement M400,120.0,AZN,0.18,t,1.0,1.0,100.0,40.0,"
    "2026-08-01T00:00:00+00:00,2026-09-01T00:00:00+00:00\n"
)


class _FakeOcrEngine:
    def parse_document(self, image_bytes: bytes, *, mime_type: str) -> str:
        return json.dumps(
            {
                "vendor_name": "Napkin Contract Vendor",
                "items": [
                    {
                        "material": "cement M400",
                        "price": 120.0,
                        "currency": "AZN",
                        "vat_rate": 18.0,
                        "uom": "t",
                        "uom_canonical_qty": 1.0,
                        "moq": 1.0,
                        "capacity": 100.0,
                        "inventory": 40.0,
                        "valid_from": "2026-08-01T00:00:00+00:00",
                        "valid_until": "2026-09-01T00:00:00+00:00",
                    }
                ],
            }
        )


def _providers() -> list[tuple[str, SupplyProvider]]:
    return [
        ("synthetic", SyntheticProvider(seed=1)),
        ("csv", CsvProvider(csv_content=_CSV_CONTENT)),
        (
            "napkin_ocr",
            NapkinOcrProvider(
                ocr_engine=_FakeOcrEngine(),
                image_bytes=b"fake-photo-bytes",
                mime_type="image/jpeg",
                evidence_id=1,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
            ),
        ),
    ]


@pytest.mark.parametrize("name,provider", _providers(), ids=[p[0] for p in _providers()])
def test_generate_returns_the_contract_shape(name: str, provider: SupplyProvider) -> None:
    vendors, offers = provider.generate(as_of=_AS_OF)
    assert isinstance(vendors, list)
    assert isinstance(offers, list)
    assert len(vendors) >= 1
    assert len(offers) >= 1
    assert all(isinstance(v, Vendor) for v in vendors)
    assert all(isinstance(o, Offer) for o in offers)


@pytest.mark.parametrize("name,provider", _providers(), ids=[p[0] for p in _providers()])
def test_every_offer_carries_sandbox_realm_and_synthetic_watermark(name: str, provider: SupplyProvider) -> None:
    """ADR-0004/FR-VND-06: no provider, regardless of input shape, may
    produce anything but sandbox-realm data until the real-onboarding
    legal gate opens."""
    _vendors, offers = provider.generate(as_of=_AS_OF)
    for offer in offers:
        assert offer.data_realm == "vendor-sandbox"
        assert offer.watermark == "SYNTHETIC"


@pytest.mark.parametrize("name,provider", _providers(), ids=[p[0] for p in _providers()])
def test_every_offer_has_a_non_empty_evidence_source_and_valid_executable_status(name: str, provider: SupplyProvider) -> None:
    _vendors, offers = provider.generate(as_of=_AS_OF)
    for offer in offers:
        assert offer.evidence_source
        assert offer.executable_status in ("reserved", "confirmed", "reported", "unknown")


@pytest.mark.parametrize("name,provider", _providers(), ids=[p[0] for p in _providers()])
def test_generate_is_deterministic_for_the_same_as_of(name: str, provider: SupplyProvider) -> None:
    """FR-VND-02 (seed reproducibility) applies to every provider, not
    just the synthetic one -- a CSV/napkin provider is deterministic
    trivially (same input bytes -> same output), which this proves rather
    than assumes."""
    first = provider.generate(as_of=_AS_OF)
    second = provider.generate(as_of=_AS_OF)
    assert first == second

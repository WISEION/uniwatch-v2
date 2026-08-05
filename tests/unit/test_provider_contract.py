"""Unit test for the FR-VND-04 provider adapter contract: any class
implementing `generate(as_of) -> (vendors, offers)` satisfies the
Protocol, whether it's the synthetic provider or a future CSV/ERP/API/
portal one. Provider-specific config (e.g. a synthetic seed, a CSV path)
belongs to each provider's own constructor, not this shared method --
a CSV parser has no meaningful "seed", so the shared contract must not
force one onto every provider."""

from packages.vendor.provider_contract import SupplyProvider
from packages.vendor.vendor_model import Offer, Vendor


class _FakeProvider:
    def generate(self, *, as_of: str) -> tuple[list[Vendor], list[Offer]]:
        return [], []


def test_a_conforming_class_satisfies_the_protocol():
    provider: SupplyProvider = _FakeProvider()
    vendors, offers = provider.generate(as_of="2026-08-06T00:00:00+00:00")
    assert vendors == []
    assert offers == []

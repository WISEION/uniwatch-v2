"""Unit test for the FR-VND-04 provider adapter contract: any class
implementing `generate(seed, as_of) -> (vendors, offers)` satisfies the
Protocol, whether it's the synthetic provider or a future CSV/ERP/API/
portal one."""

from packages.vendor.provider_contract import SupplyProvider
from packages.vendor.vendor_model import Offer, Vendor


class _FakeProvider:
    def generate(self, *, seed: int, as_of: str) -> tuple[list[Vendor], list[Offer]]:
        return [], []


def test_a_conforming_class_satisfies_the_protocol():
    provider: SupplyProvider = _FakeProvider()
    vendors, offers = provider.generate(seed=1, as_of="2026-08-06T00:00:00+00:00")
    assert vendors == []
    assert offers == []

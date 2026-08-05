"""Provider adapter contract (TENDER_INTELLIGENCE_SPEC.md §6.1, FR-VND-04):
one interface every supply-side provider implements -- the synthetic
provider (this task) and future CSV/ERP/API/portal providers (later
tasks, FR-VND-04 requires at least 2 total in Phase 3, not necessarily
this one task). Downstream SCG/matching code (task 3.D, a later phase)
depends only on this Protocol, never on a concrete provider class."""

from __future__ import annotations

from typing import Protocol

from .vendor_model import Offer, Vendor


class SupplyProvider(Protocol):
    def generate(self, *, seed: int, as_of: str) -> tuple[list[Vendor], list[Offer]]: ...

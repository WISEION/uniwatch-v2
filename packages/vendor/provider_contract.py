"""Provider adapter contract (TENDER_INTELLIGENCE_SPEC.md §6.1, FR-VND-04):
one interface every supply-side provider implements -- the synthetic
provider and the CSV provider (both in packages/vendor), and future
ERP/API/portal providers. Downstream SCG/matching code (task 3.D, a later
phase) depends only on this Protocol, never on a concrete provider class.

Provider-specific configuration (a synthetic seed, a CSV's content/path,
future ERP connection credentials) belongs to each provider's own
constructor, not this shared method -- a CSV parser has no meaningful
"seed", so forcing one onto every provider would leak one provider's
implementation detail into a contract meant to be provider-agnostic.
`as_of` is the one parameter every provider genuinely needs (a reference
time for evidence/validity timestamping, regardless of input shape)."""

from __future__ import annotations

from typing import Protocol

from .vendor_model import Offer, Vendor


class SupplyProvider(Protocol):
    def generate(self, *, as_of: str) -> tuple[list[Vendor], list[Offer]]: ...

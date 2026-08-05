"""Deterministic synthetic supply-side generator (TENDER_INTELLIGENCE_SPEC.md
§6.1, FR-VND-01, FR-VND-02, FR-VND-03, P312). Structurally incapable of
producing anything but sandbox-realm, SYNTHETIC-watermarked data --
data_realm/watermark are hardcoded here, never a parameter a caller could
override (FR-VND-06, ADR-0004: "strict isolation, not a soft label").

Determinism (FR-VND-02): `generate()` takes an explicit `seed` and an
explicit `as_of` reference time -- it never calls `datetime.now()` or the
module-level `random` singleton, so the same (seed, as_of) pair always
produces byte-identical output, regardless of when or how many times it's
called.

Covers 2 of FR-VND-03's 7 named adverse cases this task
(`stale_offer`, `moq_conflict`) -- the remaining 5 (mixed UOM,
currency/VAT mismatch, capacity shortfall, expiring evidence, partial
fulfillment) are real, un-invented future work, recorded in
docs/decisions/OPEN-QUESTIONS.md, not stubbed here."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from .vendor_model import Offer, Vendor


class SyntheticProvider:
    def generate(self, *, seed: int, as_of: str) -> tuple[list[Vendor], list[Offer]]:
        rng = random.Random(seed)
        as_of_dt = datetime.fromisoformat(as_of)

        vendors: list[Vendor] = []
        offers: list[Offer] = []

        def _vendor(name: str) -> Vendor:
            vendor = Vendor(
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                name=name,
                provider_type="synthetic",
                seed=seed,
            )
            vendors.append(vendor)
            return vendor

        # Normal case: valid, non-expired offer, MOQ within capacity.
        normal_vendor = _vendor("Synthetic Rebar Supplier")
        offers.append(
            Offer(
                vendor_name=normal_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="rebar-12mm",
                price=round(rng.uniform(800.0, 900.0), 2),
                currency="AZN",
                vat_rate=18.0,
                uom="ton",
                uom_canonical_qty=1.0,
                moq=5.0,
                capacity=200.0,
                inventory=150.0,
                valid_from=as_of_dt.isoformat(),
                valid_until=(as_of_dt + timedelta(days=30)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case=None,
            )
        )

        # Adverse case: stale_offer -- valid_until already before as_of.
        stale_vendor = _vendor("Synthetic Cement Supplier (stale)")
        offers.append(
            Offer(
                vendor_name=stale_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="cement-42.5",
                price=round(rng.uniform(150.0, 200.0), 2),
                currency="AZN",
                vat_rate=18.0,
                uom="ton",
                uom_canonical_qty=1.0,
                moq=2.0,
                capacity=500.0,
                inventory=300.0,
                valid_from=(as_of_dt - timedelta(days=60)).isoformat(),
                valid_until=(as_of_dt - timedelta(days=5)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case="stale_offer",
            )
        )

        # Adverse case: moq_conflict -- MOQ exceeds the vendor's own capacity.
        conflict_vendor = _vendor("Synthetic Aggregate Supplier (moq conflict)")
        offers.append(
            Offer(
                vendor_name=conflict_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="gravel-20mm",
                price=round(rng.uniform(30.0, 50.0), 2),
                currency="AZN",
                vat_rate=18.0,
                uom="m3",
                uom_canonical_qty=1.0,
                moq=500.0,
                capacity=100.0,
                inventory=40.0,
                valid_from=as_of_dt.isoformat(),
                valid_until=(as_of_dt + timedelta(days=30)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case="moq_conflict",
            )
        )

        return vendors, offers

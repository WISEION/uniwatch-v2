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

Covers all 7 of FR-VND-03's named adverse cases (`stale_offer`,
`moq_conflict`, `mixed_uom`, `currency_vat_mismatch`, `capacity_shortfall`,
`expiring_evidence`, `partial_fulfillment`). Each is *represented* here --
FR-VND-03's other half ("...и обрабатывается решением явно", handled by
an explicit decision) is not: nothing downstream yet reacts to an
adverse_case label, that is task 3.C/3.D matching/availability logic, not
this generator (recorded in docs/decisions/OPEN-QUESTIONS.md)."""

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

        # Adverse case: mixed_uom -- quoted in a non-canonical unit (kg,
        # not this material's canonical ton), a real conversion factor
        # instead of 1.0.
        mixed_uom_vendor = _vendor("Synthetic Rebar Supplier (mixed uom)")
        offers.append(
            Offer(
                vendor_name=mixed_uom_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="rebar-12mm",
                price=round(rng.uniform(0.8, 0.9), 4),
                currency="AZN",
                vat_rate=18.0,
                uom="kg",
                uom_canonical_qty=0.001,
                moq=5000.0,
                capacity=200000.0,
                inventory=150000.0,
                valid_from=as_of_dt.isoformat(),
                valid_until=(as_of_dt + timedelta(days=30)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case="mixed_uom",
            )
        )

        # Adverse case: currency_vat_mismatch -- quoted in a foreign
        # currency with a non-standard VAT rate; downstream costing
        # (task 3.D's TCO) must not silently assume AZN/18% for every offer.
        currency_vat_vendor = _vendor("Synthetic Import Cement Supplier (currency/VAT mismatch)")
        offers.append(
            Offer(
                vendor_name=currency_vat_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="cement-imported-52.5",
                price=round(rng.uniform(60.0, 80.0), 2),
                currency="USD",
                vat_rate=0.0,
                uom="ton",
                uom_canonical_qty=1.0,
                moq=10.0,
                capacity=1000.0,
                inventory=600.0,
                valid_from=as_of_dt.isoformat(),
                valid_until=(as_of_dt + timedelta(days=30)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case="currency_vat_mismatch",
            )
        )

        # Adverse case: capacity_shortfall -- on-hand inventory exceeds
        # ongoing supply capacity; once this stock sells, replenishment
        # lags behind (a real forward-looking supply constraint, distinct
        # from moq_conflict's own moq > capacity self-contradiction).
        capacity_shortfall_vendor = _vendor("Synthetic Steel Supplier (capacity shortfall)")
        offers.append(
            Offer(
                vendor_name=capacity_shortfall_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="steel-beam-ipe200",
                price=round(rng.uniform(900.0, 1000.0), 2),
                currency="AZN",
                vat_rate=18.0,
                uom="ton",
                uom_canonical_qty=1.0,
                moq=10.0,
                capacity=50.0,
                inventory=120.0,
                valid_from=as_of_dt.isoformat(),
                valid_until=(as_of_dt + timedelta(days=30)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case="capacity_shortfall",
            )
        )

        # Adverse case: expiring_evidence -- still formally valid
        # (valid_until in the future, unlike stale_offer) but the evidence
        # itself (observed_at) is more than 20 days old and should be
        # re-verified (INV-15/17-style TTL freshness concern).
        expiring_evidence_vendor = _vendor("Synthetic Timber Supplier (expiring evidence)")
        offers.append(
            Offer(
                vendor_name=expiring_evidence_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="timber-formwork-18mm",
                price=round(rng.uniform(15.0, 25.0), 2),
                currency="AZN",
                vat_rate=18.0,
                uom="m2",
                uom_canonical_qty=1.0,
                moq=50.0,
                capacity=2000.0,
                inventory=1200.0,
                valid_from=(as_of_dt - timedelta(days=45)).isoformat(),
                valid_until=(as_of_dt + timedelta(days=10)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=(as_of_dt - timedelta(days=25)).isoformat(),
                adverse_case="expiring_evidence",
            )
        )

        # Adverse case: partial_fulfillment -- on-hand inventory covers
        # less than half of stated capacity; the vendor could theoretically
        # produce up to `capacity`, but current stock could only partially
        # fulfill an order sized at capacity.
        partial_vendor = _vendor("Synthetic Pipe Supplier (partial fulfillment)")
        offers.append(
            Offer(
                vendor_name=partial_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="hdpe-pipe-110mm",
                price=round(rng.uniform(20.0, 30.0), 2),
                currency="AZN",
                vat_rate=18.0,
                uom="m",
                uom_canonical_qty=1.0,
                moq=100.0,
                capacity=300.0,
                inventory=80.0,
                valid_from=as_of_dt.isoformat(),
                valid_until=(as_of_dt + timedelta(days=30)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case="partial_fulfillment",
            )
        )

        return vendors, offers

"""Vendor synthetic-sandbox domain model (TENDER_INTELLIGENCE_SPEC.md
§6.1, FR-VND-05, ADR-0004). Pure dataclasses, no DB, no network -- same
shape as packages/tender/signal_model.py.

`data_realm`/`watermark` are explicit fields on every Vendor/Offer, never
inferred -- INV-11's "no hidden fallback/synthetic state" applies here
exactly as it does to tender signals. `SyntheticProvider`/`CsvProvider`
hardcode `data_realm="vendor-sandbox"`/`watermark="SYNTHETIC"` -- they are
structurally incapable of anything else (ADR-0004). `NapkinOcrProvider`
(task 3.A, real napkin ingestion) is the one exception: Phase 3's own
explicit deviation (TENDER_INTELLIGENCE_SPEC.md §6 header note,
2026-08-04) moves real ingestion of ALREADY-KNOWN existing vendors into
Phase 3 without a separate legal gate, so that provider requires the
caller to state `data_realm`/`watermark` explicitly per capture rather
than hardcoding either -- see napkin_provider.py. No code path in this
session has actually invoked it with `vendor-production`/`REAL` (no real
vendor photo has been supplied yet); this is a proven capability, not a
claim that real data exists anywhere in this codebase today."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Vendor:
    data_realm: str
    watermark: str
    name: str
    provider_type: str
    seed: int | None


@dataclass(frozen=True)
class Offer:
    vendor_name: str
    data_realm: str
    watermark: str
    material: str
    price: float
    currency: str
    vat_rate: float
    uom: str
    uom_canonical_qty: float
    moq: float
    capacity: float
    inventory: float
    valid_from: str
    valid_until: str
    evidence_source: str
    observed_at: str
    adverse_case: str | None
    # Raw, vendor-declared/source-observed tier (TENDER_INTELLIGENCE_SPEC.md
    # §6.3, task 3.C): "reserved" | "confirmed" | "reported" | "unknown" --
    # see packages/vendor/availability_model.py for the tier ordering and
    # the reputation-weighted effective status derived from it.
    executable_status: str

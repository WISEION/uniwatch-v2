"""Vendor synthetic-sandbox domain model (TENDER_INTELLIGENCE_SPEC.md
§6.1, FR-VND-05, ADR-0004). Pure dataclasses, no DB, no network -- same
shape as packages/tender/signal_model.py.

`data_realm`/`watermark` are explicit fields on every Vendor/Offer, never
inferred -- INV-11's "no hidden fallback/synthetic state" applies here
exactly as it does to tender signals. Every instance this phase's code
constructs is `data_realm="vendor-sandbox"`/`watermark="SYNTHETIC"` --
`vendor-production`/`REAL` exist as valid values (matching the database
CHECK constraint) but nothing in this codebase produces them yet; real
vendor onboarding is a separate legal/privacy/security gate, out of scope
here."""

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

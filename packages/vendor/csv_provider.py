"""CSV provider (TENDER_INTELLIGENCE_SPEC.md §6.1, FR-VND-04's second
required Phase 3 provider): parses a vendor-supplied CSV price list into
the same Vendor/Offer shape SyntheticProvider produces, proving the
provider-adapter abstraction supports a genuinely different input shape
(a given file, not a pseudo-random generator) -- not a claim about any
real vendor's actual data. Still data_realm="vendor-sandbox"/
watermark="SYNTHETIC": the real vendor onboarding legal/privacy/security
gate hasn't opened (ADR-0004), so every provider's output stays
sandbox-realm regardless of input shape until that gate does.

`executable_status` (task 3.C, TENDER_INTELLIGENCE_SPEC.md §6.3) is
hardcoded to "reported" for every row -- same discipline as `adverse_case`
being hardcoded `None` below: a CSV price list is, by definition, a
vendor's own unverified submission (no legal lock, no independent physical
confirmation), which is exactly what the "reported" tier means. There is
no CSV column that could honestly supply "reserved"/"confirmed" instead."""

from __future__ import annotations

import csv
import io

from .vendor_model import Offer, Vendor

REQUIRED_COLUMNS = (
    "vendor_name",
    "material",
    "price",
    "currency",
    "vat_rate",
    "uom",
    "uom_canonical_qty",
    "moq",
    "capacity",
    "inventory",
    "valid_from",
    "valid_until",
)


class CsvParseError(Exception):
    """The given CSV content is missing a required column, or a row's
    value can't be parsed into the expected type -- always this one typed
    error, never a bare csv/ValueError leaking to the caller."""


class CsvProvider:
    def __init__(self, *, csv_content: str) -> None:
        self._csv_content = csv_content

    def generate(self, *, as_of: str) -> tuple[list[Vendor], list[Offer]]:
        reader = csv.DictReader(io.StringIO(self._csv_content))
        if reader.fieldnames is None:
            return [], []
        missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise CsvParseError(f"CSV is missing required column(s): {', '.join(missing)}")

        vendors: list[Vendor] = []
        offers: list[Offer] = []
        for row in reader:
            vendor = Vendor(
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                name=row["vendor_name"],
                provider_type="csv",
                seed=None,
            )
            vendors.append(vendor)
            try:
                offers.append(
                    Offer(
                        vendor_name=row["vendor_name"],
                        data_realm="vendor-sandbox",
                        watermark="SYNTHETIC",
                        material=row["material"],
                        price=float(row["price"]),
                        currency=row["currency"],
                        vat_rate=float(row["vat_rate"]),
                        uom=row["uom"],
                        uom_canonical_qty=float(row["uom_canonical_qty"]),
                        moq=float(row["moq"]),
                        capacity=float(row["capacity"]),
                        inventory=float(row["inventory"]),
                        valid_from=row["valid_from"],
                        valid_until=row["valid_until"],
                        evidence_source="csv-upload",
                        observed_at=as_of,
                        adverse_case=None,
                        executable_status="reported",
                    )
                )
            except ValueError as exc:
                raise CsvParseError(f"CSV row for vendor {row['vendor_name']!r} has an invalid value: {exc}") from exc

        return vendors, offers

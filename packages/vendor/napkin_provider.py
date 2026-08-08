"""Real napkin-ingestion provider (task 3.A, TENDER_INTELLIGENCE_SPEC.md
§6.1, P312/P313): the "photo of a price list" half of napkin ingestion --
implements SupplyProvider the same way CsvProvider does, turning an OCR
engine's extracted text into the same Vendor/Offer shape every other
provider produces.

Unlike SyntheticProvider/CsvProvider, this provider does NOT hardcode
data_realm/watermark: Phase 3's own explicit, owner-confirmed deviation
(TENDER_INTELLIGENCE_SPEC.md §6's header note, dated 2026-08-04) moves
REAL supplier ingestion into Phase 3 for Unico QSC's already-known,
already-existing vendors specifically (not a search for new suppliers,
so the real-onboarding legal gate ADR-0004 describes for *new* vendors
does not apply here) -- a real captured photo of a real known vendor's
price list is legitimately `vendor-production`/`REAL`, not synthetic. The
caller must say which realm applies (no default -- FR-VND-06's "strict
isolation, not a soft label" extends to never guessing this), and this
provider validates the pairing itself at construction (fail fast, before
a confusing DB CHECK-constraint error much later at store time). No
photo has actually been run through this in REAL mode in this session
(no real vendor artifact has been supplied yet) -- this is a proven
capability, not a claim that real data has been produced anywhere in
this codebase.

NAPKIN_EXTRACTION_PROMPT and the JSON shape this parser expects are THIS
TASK'S OWN INVENTION -- Unlimited-OCR's own README names a general
Markdown/JSON output capability, not a price-list-specific extraction
schema, and no real captured napkin photo has been run through a real
model in this session to validate against (the exact Ollama registry tag
is unconfirmed -- see ollama_ocr_engine.py's docstring). Same honest
limitation as csv_provider.py's own invented 12-column CSV schema: a
real, testable mechanism, not a claim that it has been proven against a
real vendor's actual napkin.

`executable_status` is hardcoded "reported" for every row, same reasoning
as csv_provider.py: an OCR'd photo of a napkin/price list is, by
definition, an unverified vendor claim -- no legal lock, no independent
physical confirmation, regardless of which realm it belongs to."""

from __future__ import annotations

import json

from .ocr_engine import OcrEngine
from .vendor_model import Offer, Vendor

NAPKIN_EXTRACTION_PROMPT = (
    "Extract every price-list line item from this document image as JSON, "
    "exactly matching this shape, with no other text before or after the "
    'JSON: {"vendor_name": string, "items": [{"material": string, '
    '"price": number, "currency": string, "vat_rate": number (percent, '
    'e.g. 18 not 0.18), "uom": string, "uom_canonical_qty": number, "moq": '
    'number, "capacity": number, "inventory": number, "valid_from": ISO '
    '8601 date string, "valid_until": ISO 8601 date string}]}. If a field '
    "is not stated in the image, use null -- never invent a value."
)

REQUIRED_ITEM_FIELDS = (
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

_VALID_REALM_PAIRS = {
    ("vendor-sandbox", "SYNTHETIC"),
    ("vendor-production", "REAL"),
}


class NapkinParseError(Exception):
    """The OCR engine's output isn't valid JSON, or is missing a required
    field/vendor_name -- always this one typed error, never a silently
    dropped row or a bare json.JSONDecodeError/KeyError leaking out."""


class NapkinOcrProvider:
    def __init__(
        self,
        *,
        ocr_engine: OcrEngine,
        image_bytes: bytes,
        mime_type: str,
        evidence_id: int,
        data_realm: str,
        watermark: str,
    ) -> None:
        if (data_realm, watermark) not in _VALID_REALM_PAIRS:
            raise ValueError(
                f"invalid data_realm/watermark pairing: ({data_realm!r}, {watermark!r}) -- "
                f"must be one of {sorted(_VALID_REALM_PAIRS)}"
            )
        self._ocr_engine = ocr_engine
        self._image_bytes = image_bytes
        self._mime_type = mime_type
        self._evidence_id = evidence_id
        self._data_realm = data_realm
        self._watermark = watermark

    def generate(self, *, as_of: str) -> tuple[list[Vendor], list[Offer]]:
        raw_text = self._ocr_engine.parse_document(self._image_bytes, mime_type=self._mime_type)
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise NapkinParseError(f"OCR output is not valid JSON: {exc}") from exc

        if not isinstance(payload, dict) or not payload.get("vendor_name"):
            raise NapkinParseError(f"OCR output is missing a non-empty 'vendor_name': {raw_text!r}")
        vendor_name = payload["vendor_name"]
        items = payload.get("items")
        if not isinstance(items, list):
            raise NapkinParseError(f"OCR output is missing an 'items' list: {raw_text!r}")

        vendor = Vendor(
            data_realm=self._data_realm,
            watermark=self._watermark,
            name=vendor_name,
            provider_type="napkin-ocr",
            seed=None,
        )
        evidence_source = f"napkin-ocr:{self._evidence_id}"
        offers: list[Offer] = []
        for item in items:
            if not isinstance(item, dict):
                raise NapkinParseError(f"OCR output item for vendor {vendor_name!r} is not an object: {item!r}")
            missing = [f for f in REQUIRED_ITEM_FIELDS if item.get(f) is None]
            if missing:
                raise NapkinParseError(
                    f"OCR output item for vendor {vendor_name!r} is missing required field(s): {', '.join(missing)}"
                )
            try:
                offers.append(
                    Offer(
                        vendor_name=vendor_name,
                        data_realm=self._data_realm,
                        watermark=self._watermark,
                        material=str(item["material"]),
                        price=float(item["price"]),
                        currency=str(item["currency"]),
                        vat_rate=float(item["vat_rate"]),
                        uom=str(item["uom"]),
                        uom_canonical_qty=float(item["uom_canonical_qty"]),
                        moq=float(item["moq"]),
                        capacity=float(item["capacity"]),
                        inventory=float(item["inventory"]),
                        valid_from=str(item["valid_from"]),
                        valid_until=str(item["valid_until"]),
                        evidence_source=evidence_source,
                        observed_at=as_of,
                        adverse_case=None,
                        executable_status="reported",
                    )
                )
            except (TypeError, ValueError) as exc:
                raise NapkinParseError(f"OCR output item for vendor {vendor_name!r} has an invalid value: {exc}") from exc

        return [vendor], offers

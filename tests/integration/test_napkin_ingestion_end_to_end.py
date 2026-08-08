"""End-to-end proof of the real napkin-ingestion mechanism (task 3.A,
P312/P313): photo bytes -> immutable evidence row -> OCR engine (fake, for
this test) -> parsed Vendor/Offer -> real database round-trip, same shape
as tests/integration/test_vendor_store.py's synthetic-provider round-trip.
Only the OCR engine is faked here -- everything else (evidence storage,
parsing, DB persistence) is the real mechanism this task built."""

from __future__ import annotations

import json

from packages.vendor.napkin_evidence import save_napkin_evidence
from packages.vendor.napkin_provider import NapkinOcrProvider
from packages.vendor.vendor_store import list_offers_by_data_realm, store_offer, store_vendor

AS_OF = "2026-08-08T00:00:00+00:00"

_PHOTO_BYTES = b"\xff\xd8\xff\xe0-fake-jpeg-bytes-standing-in-for-a-real-napkin-photo"


class _FakeOcrEngine:
    def parse_document(self, image_bytes: bytes, *, mime_type: str) -> str:
        assert image_bytes == _PHOTO_BYTES
        assert mime_type == "image/jpeg"
        return json.dumps(
            {
                "vendor_name": "Rəşid Materials",
                "items": [
                    {
                        "material": "arm-12",
                        "price": 950.0,
                        "currency": "AZN",
                        "vat_rate": 18.0,
                        "uom": "t",
                        "uom_canonical_qty": 1.0,
                        "moq": 5.0,
                        "capacity": 300.0,
                        "inventory": 200.0,
                        "valid_from": "2026-08-01T00:00:00+00:00",
                        "valid_until": "2026-08-31T00:00:00+00:00",
                    }
                ],
            }
        )


async def test_napkin_photo_becomes_evidence_and_a_real_offer_row(engine):
    async with engine.begin() as conn:
        evidence_id = await save_napkin_evidence(
            conn,
            capture_kind="photo",
            raw_bytes=_PHOTO_BYTES,
            mime_type="image/jpeg",
            correlation_id="corr-napkin-1",
        )

    provider = NapkinOcrProvider(
        ocr_engine=_FakeOcrEngine(),
        image_bytes=_PHOTO_BYTES,
        mime_type="image/jpeg",
        evidence_id=evidence_id,
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
    )
    vendors, offers = provider.generate(as_of=AS_OF)

    async with engine.begin() as conn:
        vendor_ids = {}
        for vendor in vendors:
            vendor_ids[vendor.name], _api_key = await store_vendor(conn, vendor)
        for offer in offers:
            await store_offer(conn, vendor_ids[offer.vendor_name], offer)

        rows = await list_offers_by_data_realm(conn, data_realm="vendor-sandbox")

    matching = [r for r in rows if r["evidence_source"] == f"napkin-ocr:{evidence_id}"]
    assert len(matching) == 1
    assert matching[0]["material"] == "arm-12"
    assert matching[0]["executable_status"] == "reported"
    assert matching[0]["watermark"] == "SYNTHETIC"

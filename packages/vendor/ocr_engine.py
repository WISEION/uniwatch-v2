"""OCR engine adapter contract (TENDER_INTELLIGENCE_SPEC.md §6.1, task 3.A,
P312): one interface any document-parsing backend implements, same
provider-agnostic discipline as provider_contract.py's `SupplyProvider` --
downstream code (napkin_provider.py) depends only on this Protocol, never
on a concrete engine class, so a future replacement engine is a new
adapter, not a rewrite of the parsing logic that consumes it."""

from __future__ import annotations

from typing import Protocol


class OcrEngineError(Exception):
    """Any failure turning image bytes into text: engine unreachable,
    non-success response, or a response shape the adapter doesn't
    recognize -- always this one typed error, never a bare
    httpx/network exception leaking to the caller."""


class OcrEngine(Protocol):
    def parse_document(self, image_bytes: bytes, *, mime_type: str) -> str:
        """Returns the engine's raw structured text output (Markdown or
        JSON, per the backend's own documented output format) for one
        document image. Raises OcrEngineError on any failure -- never
        returns an empty string or None to mean failure."""
        ...

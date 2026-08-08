"""Ollama-backed OCR engine (task 3.A real napkin-ingestion, replacing the
prior "not started" gap -- TENDER_INTELLIGENCE_SPEC.md §6.1, P312). Calls
Ollama's own real, stable `/api/generate` multimodal endpoint (`images`
as a base64 list, `stream: false`) -- this is Ollama's own long-documented
generic contract, independent of which vision model is loaded behind it.

What this does NOT claim: a specific, confirmed-working Ollama registry
tag for Baidu's Unlimited-OCR model. This session tried `ollama pull
unlimited-ocr` and `ollama pull baidu/unlimited-ocr` against a real local
Ollama 0.32.5 instance; both failed with "pull model manifest: file does
not exist" -- no public registry tag was found. `OcrSettings.ocr_model_name`
is therefore a required setting with no guessed default (see
ocr_settings.py) -- whoever pulls the real weights (under Ollama, vLLM, or
llama.cpp per the model's own README) configures the exact tag/name that
actually resolves in their environment; this engine is generic against
any Ollama-served vision model, not hardcoded to an unverified string.

Deliberately calls `httpx` directly here rather than routing through
packages/platform/egress: that module exists to validate fetches to
attacker-influenceable EXTERNAL sources (SSRF defense) and its IP-blocking
logic would always reject a local/private OCR service address by design
-- this is an internal, operator-configured infra dependency, the same
category as the DB connection in packages/platform/db.py, not an
ingestion connector reaching into arbitrary external hosts.

Synchronous, not async: `provider_contract.py`'s `SupplyProvider.generate`
is deliberately sync (matching SyntheticProvider/CsvProvider, both pure
functions), so `OcrEngine.parse_document` stays sync too rather than
forcing NapkinOcrProvider to bridge async from inside a sync contract
method. Offloading this blocking HTTP call from an async caller (a future
worker job) is that caller's responsibility when napkin ingestion is
wired into one -- out of scope here, same as CSV/synthetic providers not
being wired into a job yet either."""

from __future__ import annotations

import base64

import httpx

from .ocr_engine import OcrEngineError

DEFAULT_PROMPT = (
    "Extract this document as clean Markdown or JSON, preserving every "
    "table, heading, and line item exactly as written. Do not summarize "
    "or omit any row."
)


class OllamaOcrEngine:
    def __init__(
        self,
        *,
        base_url: str,
        model_name: str,
        prompt: str = DEFAULT_PROMPT,
        timeout: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not model_name:
            raise ValueError(
                "OllamaOcrEngine requires an explicit model_name -- no confirmed "
                "Ollama registry tag exists for this task's OCR backend yet, see "
                "this module's docstring; set OCR_MODEL_NAME once you've pulled "
                "real weights under a tag that resolves in your environment."
            )
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._prompt = prompt
        self._timeout = timeout
        self._client = client

    def parse_document(self, image_bytes: bytes, *, mime_type: str) -> str:
        encoded = base64.b64encode(image_bytes).decode("ascii")
        owns_client = self._client is None
        http_client = self._client or httpx.Client()
        try:
            response = http_client.post(
                f"{self._base_url}/api/generate",
                json={
                    "model": self._model_name,
                    "prompt": self._prompt,
                    "images": [encoded],
                    "stream": False,
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise OcrEngineError(f"OCR engine unreachable at {self._base_url}: {exc}") from exc
        finally:
            if owns_client:
                http_client.close()

        if response.status_code != 200:
            raise OcrEngineError(f"OCR engine returned status {response.status_code}: {response.text}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise OcrEngineError(f"OCR engine returned non-JSON response: {exc}") from exc

        text = payload.get("response")
        if not isinstance(text, str) or not text:
            raise OcrEngineError(f"OCR engine response missing a non-empty 'response' field: {payload!r}")
        return text

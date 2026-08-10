"""Unit tests for packages/vendor/ollama_ocr_engine.py. httpx.MockTransport
stands in for a real local Ollama instance -- no real network, no real
model weights needed here (that honest gap -- no confirmed Ollama
registry tag for Unlimited-OCR exists in this session -- is recorded in
the module's own docstring and in docs/decisions/OPEN-QUESTIONS.md, not
worked around by pretending a fake response proves the real model works)."""

from __future__ import annotations

import base64
import json

import httpx
import pytest

from packages.platform.ocr_engine import OcrEngineError
from packages.platform.ollama_ocr_engine import OllamaOcrEngine


def test_requires_an_explicit_model_name():
    with pytest.raises(ValueError):
        OllamaOcrEngine(base_url="http://localhost:11434", model_name="")


def test_parse_document_sends_base64_image_and_model_name_to_generate_endpoint():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"model": "some-vlm", "response": "extracted text", "done": True})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    engine = OllamaOcrEngine(base_url="http://localhost:11434", model_name="some-vlm", client=client)

    result = engine.parse_document(b"fake-image-bytes", mime_type="image/png")

    assert result == "extracted text"
    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["body"]["model"] == "some-vlm"
    assert captured["body"]["stream"] is False
    assert captured["body"]["images"] == [base64.b64encode(b"fake-image-bytes").decode("ascii")]


def test_raises_typed_error_on_non_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="model not loaded")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    engine = OllamaOcrEngine(base_url="http://localhost:11434", model_name="some-vlm", client=client)

    with pytest.raises(OcrEngineError):
        engine.parse_document(b"bytes", mime_type="image/png")


def test_raises_typed_error_on_non_json_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    engine = OllamaOcrEngine(base_url="http://localhost:11434", model_name="some-vlm", client=client)

    with pytest.raises(OcrEngineError):
        engine.parse_document(b"bytes", mime_type="image/png")


def test_raises_typed_error_on_missing_response_field():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "some-vlm", "done": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    engine = OllamaOcrEngine(base_url="http://localhost:11434", model_name="some-vlm", client=client)

    with pytest.raises(OcrEngineError):
        engine.parse_document(b"bytes", mime_type="image/png")


def test_raises_typed_error_on_network_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    engine = OllamaOcrEngine(base_url="http://localhost:11434", model_name="some-vlm", client=client)

    with pytest.raises(OcrEngineError):
        engine.parse_document(b"bytes", mime_type="image/png")

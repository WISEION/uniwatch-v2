"""OCR engine configuration. Lives in packages/platform (not a
vendor-domain package) because a second domain now needs the identical
OcrEngine Protocol -- packages/decision's Execution Ledger napkin
ingestion (Phase 4, task 4.C, TENDER_INTELLIGENCE_SPEC.md Section7.3) --
and packages/decision must never import packages/vendor directly
(ADR-0001 domain boundary). This is exactly the "cross-cutting...
shared LIBRARY" packages/platform already is for DATABASE_URL etc.
(CLAUDE.md), not domain scoring/business-decision logic itself.

`ollama_base_url` defaults to Ollama's own well-known standard local port
(a fixed product constant, not an invented business value -- the same
kind of default DATABASE_URL already uses for Postgres's own standard
port). `ocr_model_name` has NO default: there is no universally-correct
Ollama model tag for this task's OCR backend to guess at (this session
tried `ollama pull unlimited-ocr` and `ollama pull baidu/unlimited-ocr`
against a real local Ollama instance -- both failed with "manifest does
not exist", i.e. no confirmed public registry tag exists yet for
Unlimited-OCR specifically). Leaving this unset is a real, loud
configuration error (AGENTS.md hard ban #3: no silent fallback) --
OllamaOcrEngine raises rather than guessing a plausible-looking string."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OcrSettings:
    ollama_base_url: str = field(default_factory=lambda: os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"))
    ocr_model_name: str = field(default_factory=lambda: os.environ.get("OCR_MODEL_NAME", ""))


def get_ocr_settings() -> OcrSettings:
    return OcrSettings()

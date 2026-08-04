"""Confirms BOM_LINE_ITEM_CONTRACT matches every item's real key set
observed across all 3 captured BOQ pages of event 355920 -- not a guessed
shape."""

from __future__ import annotations

import json
from pathlib import Path

from packages.tender.etender_contract import BOM_LINE_ITEM_CONTRACT

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


def test_contract_field_names_match_every_real_captured_item_exactly():
    declared = {f.name for f in BOM_LINE_ITEM_CONTRACT.fields}
    for page in (1, 2, 3):
        payload = json.loads((FIXTURES / f"event_355920_bomlines_page{page}.raw.json").read_bytes())
        for item in payload["items"]:
            assert set(item.keys()) == declared

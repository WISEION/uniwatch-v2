"""Shared access to the frozen real-source captures under `fixtures/`
(tests/README.md). Every test that replays a real eTender or World Bank
capture resolves the same two directories and, for the events-list
endpoint, sends the same full query-parameter set -- kept here once so a
re-capture or a new query key is a one-line change, not a hunt through
every test module.

Importable as a plain module because pytest puts `tests/` on `sys.path`
(the conftest.py next to this file)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "tender-snapshots"

ETENDER_FIXTURES = _FIXTURES / "etender"
WORLDBANK_FIXTURES = _FIXTURES / "worldbank"

# Every query key eTender's events endpoint accepts (all of them are part
# of the resource's identity -- see EVENTS_LIST_PAGE_CONTRACT), at the
# source's own defaults: an unfiltered, open-events search.
EVENTS_LIST_QUERY_PARAMS: dict[str, Any] = {
    "EventType": "",
    "PageSize": 10,
    "EventStatus": 1,
    "Keyword": "",
    "buyerOrganizationName": "",
    "documentNumber": "",
    "publishDateFrom": "",
    "publishDateTo": "",
    "AwardedparticipantName": "",
    "AwardedparticipantVoen": "",
    "DocumentViewType": "",
    "IsArchived": False,
}

# The design/TEO-tender slice (task 2.B): the same search, narrowed by the
# source's own server-side keyword filter.
DESIGN_TENDER_QUERY_PARAMS: dict[str, Any] = {**EVENTS_LIST_QUERY_PARAMS, "Keyword": "layihə"}


def raw_fixture(directory: Path, name: str) -> bytes:
    return (directory / name).read_bytes()


def json_fixture(directory: Path, name: str) -> dict[str, Any]:
    return json.loads(raw_fixture(directory, name))

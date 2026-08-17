"""Source-freshness alert (Phase 6, task 6.C, NFR-OPS-02). Lives in
packages/tender, not packages/platform/alerts.py, because it reads
raw_snapshots (tender-owned) -- packages/platform never depends on a domain
package (AGENTS.md §3). Fires only on "this source has never successfully
fetched anything" -- a genuinely boolean, threshold-free condition -- not a
staleness window, since D-SLO/TBD-01/TBD-02 (the numeric freshness window)
remain open and this project never invents a number (AGENTS.md hard ban #2).

_KNOWN_SOURCES is a hardcoded list because no connector registry exists in
this codebase (each source is a fully separate, independently-added
connector module, per CLAUDE.md's tender-ingestion description) -- adding a
new connector requires adding its source string here too. Recorded as a
known limitation in docs/decisions/OPEN-QUESTIONS.md's 2026-08-17 entry, not
silently assumed to self-update."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.alerts import AlertResult

from .raw_snapshot import last_fetched_at_by_source

_KNOWN_SOURCES = ("etender", "worldbank_projects_api")


async def source_never_succeeded(conn: AsyncConnection) -> AlertResult:
    seen = await last_fetched_at_by_source(conn)
    never_seen = [source for source in _KNOWN_SOURCES if source not in seen]
    if never_seen:
        return AlertResult(
            name="source_never_succeeded",
            firing=True,
            detail=f"source(s) with zero recorded fetches: {', '.join(never_seen)}",
        )
    return AlertResult(name="source_never_succeeded", firing=False, detail="every known source has at least one recorded fetch")

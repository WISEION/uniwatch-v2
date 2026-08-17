"""Live alert gate (Phase 6, task 6.C, NFR-OPS-02). Mirrors
scripts/check_invariants.py's shape exactly: runs every check in
packages/platform/alerts.py::ALL_ALERTS plus
packages/tender/freshness_alerts.py::source_never_succeeded against
DATABASE_URL and prints one line per check. Exits non-zero if any alert is
firing -- safe to wire into a periodic ops check the same way
check_invariants.py is wired into the post-deploy gate."""

from __future__ import annotations

import asyncio
import sys

from packages.platform.alerts import ALL_ALERTS
from packages.platform.db import connection_scope, get_engine
from packages.platform.settings import get_settings
from packages.tender.freshness_alerts import source_never_succeeded

_ALL_CHECKS = (*ALL_ALERTS, source_never_succeeded)


async def main() -> int:
    settings = get_settings()
    engine = get_engine(settings.database_url)
    any_firing = False
    try:
        async with connection_scope(engine) as conn:
            for check in _ALL_CHECKS:
                result = await check(conn)
                status = "FIRING" if result.firing else "ok"
                print(f"[{status}] {result.name}: {result.detail}")
                if result.firing:
                    any_firing = True
    finally:
        await engine.dispose()

    if any_firing:
        print("one or more alerts are firing")
        return 1
    print("no alerts firing")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""Live DB invariant gate (Phase 6, task 6.B's Task 2; master plan §22 Gate 5's
"DB invariants" line, NEG-06).

Runs every check registered in `packages/platform/invariant_checks.py`
against `DATABASE_URL` (via `packages/platform/settings.py`, same
convention as `scripts/migrate.py`) and prints one pass/fail line per check.
Exits non-zero if any check failed, so this is safe to wire straight into a
post-deploy CI/ops gate: a failing invariant blocks the "deployment verified"
signal the same way a failing test blocks CI, per NEG-06 ("green CI is not
production deployment authorization" -- Gate 5 is the separate, distinct
post-deploy verification step).

Read-only: this script never issues DDL/DML, only the `SELECT`-only queries
`invariant_checks.py`'s functions run.
"""

from __future__ import annotations

import asyncio
import sys

from packages.platform.db import connection_scope, get_engine
from packages.platform.invariant_checks import ALL_CHECKS
from packages.platform.settings import get_settings


async def main() -> int:
    settings = get_settings()
    engine = get_engine(settings.database_url)
    all_passed = True
    try:
        async with connection_scope(engine) as conn:
            for check in ALL_CHECKS:
                result = await check(conn)
                status = "PASS" if result.passed else "FAIL"
                print(f"[{status}] {result.name}: {result.detail}")
                if not result.passed:
                    all_passed = False
    finally:
        await engine.dispose()

    if not all_passed:
        print("one or more DB invariants failed")
        return 1
    print("all DB invariants passed")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

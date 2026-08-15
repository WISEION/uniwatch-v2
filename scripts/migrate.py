"""Explicit migration-apply command.

`migrations/README.md` rule 1 and `packages/platform/migrations_runner.py`'s
own module docstring are both explicit: the schema never changes as a side
effect of application startup -- `apply_all()` is only ever invoked by an
explicit migration command or a test fixture, never by
`apps/api_tender/main.py`, `apps/api_vendor/main.py`, or `apps/worker/main.py`.

This is that explicit command. `docker-compose.local.yml`'s one-shot
`migrate` service runs it (reusing the `apps/worker` image, with this as a
`command:` override) so `api_tender`/`api_vendor`/`worker` only ever start
against an already-migrated schema, and never call `apply_all()` themselves.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from packages.platform.migrations_runner import MigrationRunner
from packages.platform.settings import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


async def main() -> None:
    settings = get_settings()
    runner = MigrationRunner(settings.asyncpg_dsn, MIGRATIONS_DIR)
    applied = await runner.apply_all(applied_by="docker-compose-migrate")
    if not applied:
        print("no pending migrations")
        return
    for migration in applied:
        print(f"applied {migration.version:04d}_{migration.description}")


if __name__ == "__main__":
    asyncio.run(main())

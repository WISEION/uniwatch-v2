from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from testcontainers.postgres import PostgresContainer

from packages.platform.db import get_engine, get_sessionmaker
from packages.platform.migrations_runner import MigrationRunner

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as pg:
        yield pg


@pytest.fixture(scope="session")
def _database_url(postgres_container) -> str:
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def _asyncpg_base_dsn(postgres_container) -> str:
    return postgres_container.get_connection_url().replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest_asyncio.fixture
async def asyncpg_dsn(_asyncpg_base_dsn) -> str:
    """A fresh, empty (unmigrated) schema on the shared container, per test."""
    conn = await asyncpg.connect(_asyncpg_base_dsn)
    try:
        await conn.execute("DROP SCHEMA public CASCADE")
        await conn.execute("CREATE SCHEMA public")
    finally:
        await conn.close()
    return _asyncpg_base_dsn


@pytest_asyncio.fixture
async def migrated_asyncpg_dsn(asyncpg_dsn) -> str:
    runner = MigrationRunner(asyncpg_dsn, MIGRATIONS_DIR)
    await runner.apply_all()
    return asyncpg_dsn


@pytest_asyncio.fixture
async def engine(_database_url, migrated_asyncpg_dsn):
    engine = get_engine(_database_url)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def sessionmaker(engine):
    return get_sessionmaker(engine)

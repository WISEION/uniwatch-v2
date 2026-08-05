"""`DATABASE_URL` is required configuration: no credentialed default in
source, no silent fallback (AGENTS.md §2 rule 3)."""

from __future__ import annotations

import pytest

from packages.platform.settings import MissingSetting, Settings, get_settings


def test_missing_database_url_raises(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(MissingSetting):
        get_settings()


def test_empty_database_url_raises(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "")
    with pytest.raises(MissingSetting):
        get_settings()


def test_database_url_comes_from_the_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@db:5432/x")
    assert get_settings().database_url == "postgresql+asyncpg://u:p@db:5432/x"


def test_asyncpg_dsn_strips_the_driver_qualifier():
    settings = Settings(database_url="postgresql+asyncpg://u:p@db:5432/x")
    assert settings.asyncpg_dsn == "postgresql://u:p@db:5432/x"

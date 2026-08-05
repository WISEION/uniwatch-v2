"""Environment-based configuration. No config framework dependency — a plain
dataclass keeps `packages/platform` dependency-light (AGENTS.md: minimal and
fixed dependencies).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


class MissingSetting(RuntimeError):
    def __init__(self, name: str):
        super().__init__(f"required environment variable {name} is not set")
        self.name = name


@dataclass(frozen=True)
class Settings:
    # SQLAlchemy-style URL, used by the async engine (packages/platform/db.py).
    # Required: there is no built-in default, because a default URL ships
    # credentials in source and silently points a misconfigured deployment at
    # the wrong database instead of failing (AGENTS.md §2 rule 3).
    database_url: str = field(default_factory=lambda: _required_env("DATABASE_URL"))
    # Version the running code was built for (FR-PLT-12 rule 2: startup
    # compares this against the ledger's current_version and refuses to
    # start on mismatch instead of auto-migrating).
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "8")))
    # Explicit trusted reverse-proxy CIDRs (FR-PLT-07). Empty by default —
    # deny-by-default extends to "no proxy is trusted until configured".
    trusted_proxy_cidrs: tuple[str, ...] = field(
        default_factory=lambda: tuple(c.strip() for c in os.environ.get("TRUSTED_PROXY_CIDRS", "").split(",") if c.strip())
    )

    @property
    def asyncpg_dsn(self) -> str:
        """Raw asyncpg DSN (no SQLAlchemy driver qualifier), for the
        migration runner which talks to Postgres directly."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise MissingSetting(name)
    return value


def get_settings() -> Settings:
    return Settings()

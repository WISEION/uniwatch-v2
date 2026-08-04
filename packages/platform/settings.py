"""Environment-based configuration. No config framework dependency — a plain
dataclass keeps `packages/platform` dependency-light (AGENTS.md: minimal and
fixed dependencies).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # SQLAlchemy-style URL, used by the async engine (packages/platform/db.py).
    database_url: str = field(
        default_factory=lambda: os.environ.get(
            "DATABASE_URL",
            "postgresql+asyncpg://uniwatch:uniwatch@localhost:5432/uniwatch",
        )
    )
    # Version the running code was built for (FR-PLT-12 rule 2: startup
    # compares this against the ledger's current_version and refuses to
    # start on mismatch instead of auto-migrating).
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "3")))
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


def get_settings() -> Settings:
    return Settings()

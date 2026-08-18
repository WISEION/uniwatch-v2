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
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "24")))
    # Explicit trusted reverse-proxy CIDRs (FR-PLT-07). Empty by default —
    # deny-by-default extends to "no proxy is trusted until configured".
    trusted_proxy_cidrs: tuple[str, ...] = field(
        default_factory=lambda: tuple(c.strip() for c in os.environ.get("TRUSTED_PROXY_CIDRS", "").split(",") if c.strip())
    )
    # Base URL of the Vendor service (ADR-0006: separate deployable process).
    # No default -- unlike DATABASE_URL, there is no universally-correct
    # local default port convention for this cross-service call the way
    # Postgres's 5432 is; an unset value should fail loudly the first time
    # something actually tries to reach the vendor service, not silently
    # point at a guessed URL (AGENTS.md hard ban #3).
    vendor_service_base_url: str = field(default_factory=lambda: os.environ.get("VENDOR_SERVICE_BASE_URL", ""))
    # Browser origins allowed to call this API cross-origin (apps/web is
    # always a different origin from apps/api_tender/apps/api_vendor in
    # this topology -- even docker-compose.local.yml's nginx serves the
    # built SPA as a pure static file server with no reverse proxy to the
    # APIs, per apps/web/nginx.conf, so the browser calls api_tender/
    # api_vendor's own origin directly in every environment, not just local
    # dev). Explicit allowlist, never a wildcard -- the session cookie
    # requires allow_credentials=True, which CORS itself forbids combining
    # with "*" (deny-by-default, same posture as trusted_proxy_cidrs
    # above). Dev default covers this project's two known local origins:
    # the Vite dev server (5173) and the compose-built static app (8080).
    cors_allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            o.strip()
            for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",")
            if o.strip()
        )
    )

    @property
    def asyncpg_dsn(self) -> str:
        """Raw asyncpg DSN (no SQLAlchemy driver qualifier), for the
        migration runner which talks to Postgres directly."""
        return self.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def get_settings() -> Settings:
    return Settings()

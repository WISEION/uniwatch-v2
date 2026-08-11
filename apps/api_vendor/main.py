"""FastAPI app factory for the Vendor service (ADR-0006: Tender and Vendor
are separate deployable processes, not routers on one app -- see
apps/api_tender/main.py for the other side). The generic bootstrap
sequence lives in packages/platform/app_factory.py, shared with
apps/api_tender/main.py; only the title and router list differ here."""

from __future__ import annotations

from fastapi import FastAPI

from packages.platform.app_factory import build_app
from packages.platform.settings import Settings

from .routers import internal, offers


def create_app(settings: Settings | None = None) -> FastAPI:
    return build_app(
        title="UNIWatch v2 API — Vendor",
        routers=[internal.router, offers.router],
        settings=settings,
    )


app = create_app()

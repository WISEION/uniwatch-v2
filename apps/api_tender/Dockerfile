# apps/api_tender Dockerfile -- Tender service (ADR-0006: a separately
# deployable FastAPI process from apps/api_vendor, never routers bundled
# into the same app). Follows docs/operations/container-conventions.md:
# non-root user before CMD, minimal base image, no secrets baked in
# (DATABASE_URL etc. come from the environment at runtime --
# packages/platform/settings.py), and no writable path required inside the
# container (read-only-root-filesystem compatible).

FROM python:3.12-slim AS builder
WORKDIR /app
# Only what pyproject.toml's setuptools package discovery
# ([tool.setuptools.packages.find] include = ["packages*", "apps*"]) needs
# to resolve this project's *runtime* dependency set (fastapi, uvicorn,
# pydantic, sqlalchemy[asyncio], asyncpg) -- dev extras (pytest, ruff,
# mypy, testcontainers) are never installed into this image.
COPY pyproject.toml ./
COPY packages ./packages
COPY apps ./apps
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
RUN groupadd --gid 10001 uniwatch \
    && useradd --uid 10001 --gid uniwatch --no-create-home --home-dir /nonexistent \
       --shell /usr/sbin/nologin uniwatch
WORKDIR /app
COPY --from=builder /install /usr/local
# The code that actually runs lives here, at /app -- not the copy pip put
# under /usr/local's site-packages above (that copy exists only so `pip
# install .` in the builder stage could resolve this project's third-party
# dependencies). Running `python -m ...` from this WORKDIR resolves
# apps.api_tender.main against /app first, so packages/platform/app_factory.py's
# readiness check -- which locates migrations/ relative to its own
# `__file__` -- finds the real migrations/ directory copied in below,
# rather than an empty site-packages tree.
COPY packages ./packages
COPY apps ./apps
COPY migrations ./migrations
USER uniwatch
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
EXPOSE 8001
CMD ["python", "-m", "uvicorn", "apps.api_tender.main:app", "--host", "0.0.0.0", "--port", "8001"]

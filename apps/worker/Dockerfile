# apps/worker Dockerfile -- standalone durable-job worker process
# (NFR-ARC-03: long-running/network IO never happens inside an
# apps/api_tender or apps/api_vendor request handler; it happens here).
# Follows docs/operations/container-conventions.md: non-root user before
# CMD, minimal base image, no secrets baked in (DATABASE_URL etc. come
# from the environment at runtime -- packages/platform/settings.py), and
# no writable path required inside the container (read-only-root-filesystem
# compatible).

FROM python:3.12-slim AS builder
WORKDIR /app
# Only what pyproject.toml's setuptools package discovery
# ([tool.setuptools.packages.find] include = ["packages*", "apps*"]) needs
# to resolve this project's *runtime* dependency set (fastapi, uvicorn,
# pydantic, sqlalchemy[asyncio], asyncpg) -- dev extras (pytest, ruff,
# mypy, testcontainers) are never installed into this image. fastapi/uvicorn
# are unused by the worker itself but are pinned as one project-wide
# dependency set in pyproject.toml, not split per-app.
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
# apps.worker.main against /app first.
COPY packages ./packages
COPY apps ./apps
COPY migrations ./migrations
# scripts/migrate.py is the "explicit migration command" migrations/README.md
# and packages/platform/migrations_runner.py's own docstring require --
# apply_all() must never be called by apps/worker/main.py itself.
# docker-compose.local.yml's one-shot `migrate` service reuses this same
# image with a command override to run it.
COPY scripts ./scripts
USER uniwatch
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-m", "apps.worker.main"]

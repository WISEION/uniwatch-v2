# Container build conventions (non-root, read-only)

**Status:** Convention recorded (0.A/0.C); implemented (Phase 6 task 6.A) in `apps/api_tender/Dockerfile`, `apps/api_vendor/Dockerfile`, `apps/worker/Dockerfile`, `apps/web/Dockerfile`, and `docker-compose.local.yml` — this document remains the rule those files follow, not a substitute for reading them.
**Requirements:** `NFR-SEC-08`; `docs/architecture/threat-model.md` T7.

## Why

v1's release-note failures (`RN-11`/`RN-12`, and the general v1 audit finding on container hygiene) show that a container running as root with a writable filesystem turns a single application-level bug into host/lateral-movement persistence. The rule is structural, not a checklist item to remember per-Dockerfile.

## Rules

1. **Non-root.** Every image (`apps/api_tender`, `apps/api_vendor` — separate deployable services per `docs/adr/0006-tender-vendor-service-separation.md` — `apps/worker`, and eventually `apps/web`'s build/serve stage) creates and switches to an unprivileged user before the final `CMD`/`ENTRYPOINT`. No process in this repo's containers runs as `root` in the running container, even though the build stage may need root for package installation.
2. **Read-only root filesystem at runtime.** The container's root filesystem is mounted read-only; any path a process legitimately needs to write to (temp files, a Unix socket, etc.) is an explicit writable volume/tmpfs mount, not "the whole filesystem, just in case." A process that turns out to need an undocumented writable path is a bug to fix (narrow the mount), not a reason to drop this rule.
3. **No secrets baked into the image.** Credentials/config come from the environment or a mounted secret at runtime (`packages/platform/settings.py` already reads `DATABASE_URL` etc. from the environment) — never `COPY`'d into a layer, where they would remain in image history even if a later layer removes the file.
4. **Minimal base image.** Prefer a slim/distroless-class base over a full OS image, to reduce the attack surface available to an attacker who does get code execution inside the container.

## What this does not decide yet

- ~~The exact base image tag/distribution~~ — decided (Phase 6 task 6.A):
  `python:3.12-slim` for `apps/api_tender`, `apps/api_vendor`, `apps/worker`
  (matching `pyproject.toml`'s `requires-python = ">=3.12"`). `apps/web` is a
  two-stage build: `node:20-alpine` to run `npm run build`, then
  `nginxinc/nginx-unprivileged:1.27-alpine` to serve the static output —
  that specific nginx image, not the stock one, because it already runs as
  non-root by default. See each `apps/*/Dockerfile`.
- Orchestration-level enforcement (e.g. a Kubernetes `PodSecurityStandard`/
  admission policy) is still not applicable, but for a different reason
  than before: `D-HOST` is now resolved (owner, 2026-08-14) to
  local-network-only — no cloud provider, no Kubernetes, per
  `docs/decisions/OPEN-QUESTIONS.md`. `docker-compose.local.yml` enforces
  rule 2 directly at the one orchestration layer this topology actually
  has (`read_only: true` on every app service, with an explicit tmpfs mount
  only where `apps/web`'s nginx stage genuinely needs one) — that is as far
  as "orchestration-level enforcement" goes for a single-compose-file local
  topology, and is not a substitute for an admission-policy-style gate if a
  future `D-HOST` change ever reintroduces an orchestrator.
- Image digest pinning at **deploy time** (`NFR-SEC-09`, T8 in the threat
  model) is still open — Phase 6 task 6.B's job. What Phase 6 task 6.A
  answers is the **build-time** half: CI's `build-images` job
  (`.github/workflows/ci.yml`) computes each image's content digest and
  records it in `release-manifest.json`
  (`docs/operations/release-manifest.md`) for every commit. 6.B is where a
  production-authorization gate actually checks a digest being deployed
  against that manifest.

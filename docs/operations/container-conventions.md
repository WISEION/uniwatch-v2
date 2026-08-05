# Container build conventions (non-root, read-only)

**Status:** Convention recorded (0.A/0.C). No Dockerfile exists yet in this repo — this document is the rule any Dockerfile written from 0.B onward must follow; it is not itself an implementation.
**Requirements:** `NFR-SEC-08`; `docs/architecture/threat-model.md` T7.

## Why

v1's release-note failures (`RN-11`/`RN-12`, and the general v1 audit finding on container hygiene) show that a container running as root with a writable filesystem turns a single application-level bug into host/lateral-movement persistence. The rule is structural, not a checklist item to remember per-Dockerfile.

## Rules

1. **Non-root.** Every image (`apps/api_tender`, `apps/api_vendor` — separate deployable services per `docs/adr/0006-tender-vendor-service-separation.md` — `apps/worker`, and eventually `apps/web`'s build/serve stage) creates and switches to an unprivileged user before the final `CMD`/`ENTRYPOINT`. No process in this repo's containers runs as `root` in the running container, even though the build stage may need root for package installation.
2. **Read-only root filesystem at runtime.** The container's root filesystem is mounted read-only; any path a process legitimately needs to write to (temp files, a Unix socket, etc.) is an explicit writable volume/tmpfs mount, not "the whole filesystem, just in case." A process that turns out to need an undocumented writable path is a bug to fix (narrow the mount), not a reason to drop this rule.
3. **No secrets baked into the image.** Credentials/config come from the environment or a mounted secret at runtime (`packages/platform/settings.py` already reads `DATABASE_URL` etc. from the environment) — never `COPY`'d into a layer, where they would remain in image history even if a later layer removes the file.
4. **Minimal base image.** Prefer a slim/distroless-class base over a full OS image, to reduce the attack surface available to an attacker who does get code execution inside the container.

## What this does not decide yet

- The exact base image tag/distribution — a 0.B (when the first Dockerfile is written) decision.
- Orchestration-level enforcement (e.g. a Kubernetes `PodSecurityStandard`/admission policy that rejects a non-conforming image) — depends on `D-HOST` (owner decision on hosting), out of Phase 0/1 scope.
- Image digest pinning at deploy time (`NFR-SEC-09`, T8 in the threat model) — a Phase 6 production-deployment concern, not a build-convention concern.

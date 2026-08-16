# Release manifest (image content digests)

**Requirements:** `NFR-SEC-09` (image digest integrity) — seeds the "Image
digest integrity" line in `.ci/README.md`'s Gate 3/4 stub table.

CI's `build-images` job (`.github/workflows/ci.yml`) builds each of the four
service Dockerfiles (`apps/api_tender/Dockerfile`, `apps/api_vendor/Dockerfile`,
`apps/worker/Dockerfile`, `apps/web/Dockerfile`) from the commit under test
and writes `release-manifest.json` as a build artifact, recording each
image's content digest (`docker inspect --format='{{.Id}}'` on the freshly
built local image). `D-HOST` is local-network-only (no cloud provider,
`docs/decisions/OPEN-QUESTIONS.md`) and there is no registry to push these
images to yet, so this is a local content digest, not a registry
distribution digest.

## Shape

```json
{
  "commit_sha": "<the commit this workflow run built from>",
  "images": {
    "api_tender": "sha256:...",
    "api_vendor": "sha256:...",
    "worker": "sha256:...",
    "web": "sha256:..."
  },
  "built_at": "<ISO-8601 UTC timestamp>"
}
```

## What consumes this

Nothing yet. This file only records the fact "commit X produced these four
image digests" as a downloadable CI artifact — it does not itself enforce
anything. Phase 6 task 6.B is where a production-authorization gate reads
a manifest like this one and checks "the digest about to be deployed
matches the digest built from the commit that was actually reviewed"
(`INV-14`, `docs/architecture/threat-model.md` T8, and hard ban #6: green
CI is not production deployment authorization on its own). That gate,
any registry push, and deploy-time pinning to a specific host are
explicitly out of scope here — this task is pipeline mechanics only
(Dockerfiles + compose + this CI artifact).

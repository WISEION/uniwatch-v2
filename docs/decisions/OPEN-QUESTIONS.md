# OPEN-QUESTIONS — deviation and assumption log

Every deviation from PRD v1.0 / master development plan (2026-07-28), and every new assumption made during implementation, is recorded here at the time it is made — never decided silently (kickoff TZ, "Порядок работы" item 3; `AGENTS.md` §4).

Format per entry:

```markdown
## YYYY-MM-DD — short title

**Context:** what task/phase surfaced this.
**Deviation/assumption:** what was decided and why the source docs did not already cover it.
**Source conflict (if any):** which documents disagree, and which one won per the priority order (PRD > master plan > source map / v1 audit).
**Owner follow-up needed:** yes/no — if yes, link to the relevant `D-*`/`TBD-*` in `docs/CONTEXT.md`.
```

The blocking-but-not-now owner questions (`D-HOST`, `D-IDP`, `D-SRC`, `D-LANG`) and the never-defaulted `TBD-01..05` are tracked in `docs/CONTEXT.md`, not duplicated here — this file is for deviations discovered during build, not the pre-known open list from planning.

## 2026-08-04 — CI runner platform

**Context:** Task 0.D (qa), wiring the Fast/Full CI gates (`docs/reports/PLAN-MISSION-1.md` §2).

**Deviation/assumption:** Neither the PRD nor the master development plan names a CI vendor/platform anywhere in their gate model (Gate 0-5, master plan §22) — they describe what each gate checks, not what runs it. `.github/workflows/ci.yml` (GitHub Actions) was added as the concrete runner. This is a low-risk implementation choice (a common default, easy to replace, no lock-in to any hosting decision), not a re-interpretation of a locked requirement.

**Source conflict (if any):** None — the source docs are simply silent on CI vendor. Not a PRD-vs-master-plan disagreement.

**Owner follow-up needed:** No. Distinct from `D-HOST` (production hosting: local network/private cloud/public cloud) — a CI runner choice does not imply or constrain that decision. If a different CI platform is later preferred, `.github/workflows/ci.yml` is the only file that needs to change; the gate *contents* (`.ci/README.md`) are platform-agnostic.

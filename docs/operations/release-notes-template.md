# Release notes — template

**Status:** Template only. No release has happened yet as of this document —
do not fill this in with real content until an actual release runs through
`docs/operations/runbook.md`. Copy this file to a dated release-notes file
per release (e.g. `docs/operations/releases/2026-MM-DD-release-notes.md`)
and fill in each section; do not edit this template in place with real data.
**Requirements:** master plan §22 Gate 3's "release notes and known
limitations" line. Pulls the *shape* of this project's existing
honest-gap-recording convention (`AGENTS.md` §2.2, `docs/decisions/OPEN-QUESTIONS.md`,
this file's own "known limitations" section below) into a release-facing
document — it does not duplicate the detailed per-task history that already
lives in `docs/reports/WORKLOG.md`.

---

## Release: `<release identifier, e.g. 2026-MM-DD or vX.Y>`

### Commit range / release manifest reference

- Commit range: `<base commit>..<release commit SHA>`
- Release manifest: the `release-manifest.json` CI artifact
  (`.github/workflows/ci.yml`'s `build-images` job,
  `docs/operations/release-manifest.md`'s shape) for this exact commit SHA —
  link or attach the specific artifact used, not "the latest one," since a
  later commit's manifest would not match what was actually authorized.
- Deployment authorization record: `<reference to the specific
  `deployment_authorizations` row `scripts/authorize_deployment.py` wrote
  for this release — see "Who authorized this release" below>`

### What changed

`<Short prose summary of what this release contains — a few sentences to a
short paragraph, written for someone deciding whether this release affects
them, not a changelog dump.>`

For the detailed per-task history behind this summary — what was built, in
what order, by which task/phase — see `docs/reports/WORKLOG.md`'s entries
covering this commit range. This section does not duplicate that log; it
summarizes it.

### Known limitations

Follow this project's existing convention of recording honest gaps rather
than omitting them. Use whichever of the following apply — delete headings
with nothing to report, do not leave a heading with invented content under
it:

- **Features deferred.** Anything intentionally not in this release (e.g.
  scoped to a later phase per `docs/reports/PLAN-MISSION-*.md`) — name the
  feature and where it is tracked, not just "coming later."
- **Open `D-*`/`TBD-*` decisions relevant to this release.** Any owner
  decision or numeric value still open (per `docs/decisions/OPEN-QUESTIONS.md`)
  that affects what this release can or cannot do — reference the decision
  ID and what it blocks, do not restate or guess its eventual value.
- **Known defects.** Anything found but not fixed in this release, with
  severity and whether it is already tracked elsewhere.
- **Data/coverage caveats.** E.g. synthetic-only data realms still in
  effect (`packages/vendor`, ADR-0004), BOQ completeness status for sources
  covered by this release, or any `reality_status`/`freshness_status`/
  `completeness_status` caveat a reader of this release should know about
  before relying on it.

### Who authorized this release

- **Approver:** `<identity>` — distinct from the release's initiator
  (`<identity>`), per `INV-14`/`docs/adr/0005-authority-model.md`'s
  `FR-AUT-06`.
- **Authorization record:** the `deployment_authorizations` row
  `scripts/authorize_deployment.py` wrote when run against this release's PR
  number (`docs/operations/runbook.md` step 5) — reference its identifier/
  timestamp here so the authorization is traceable from the release notes
  themselves, not only from the database.
- **What was checked:** distinct-approver identity, commit↔digest match
  against the release manifest referenced above, and DB schema
  compatibility — per `scripts/authorize_deployment.py`'s scope
  (`docs/operations/runbook.md` step 5). This is not a substitute for the
  code review that already happened on the PR before CI went green.

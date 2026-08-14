# Phase 5, Task 5.D — АЛГОРИТМ: frontend — Implementation Plan

> **For agentic workers:** executed inline, same session. No subagent handoff.

**Goal:** `PLAN-MISSION-5.md` §3 task 5.D. This is the first HTTP API and the first line of code in
`apps/web` in the whole repo — 5.A/5.B/5.C built a pure backend with zero HTTP surface. Two things must
exist before any UI can exist at all: (1) an API layer over `packages/algorithm`'s already-real
store/validator/engine, (2) `apps/web` itself, which today is only a README.

**Scope actually built this session (real, tested):**
1. `apps/api_tender/routers/algoritm.py` — graphs/versions/nodes/edges CRUD-ish, `validate` (edit-time
   check, `FR-ALG-01`), `submit-for-approval`, `activate`, `kill-switch`, generic `transition`, `fork`,
   transition history, simulation run + read-back + case-traces, version comparison, research-dossier
   create/read/link. Every route is a thin wrapper over already-existing `packages/algorithm` functions —
   no new business logic.
2. `apps/web` — real Vite + React + TypeScript + Vitest + Testing Library scaffold (first frontend code in
   this repo). **Outline/table view only** (`FR-ALG-07`'s accessible alternative) — node/edge list as an
   HTML table, add/edit/delete via forms, inline validation-issue display, a simulation panel (run against
   pasted/sample cases, see terminal/reason-code distribution and per-case traces — the "why accepted"
   trace view), approval/transition history, JSON export (a browser download of the version's raw
   nodes/edges/transitions). Full keyboard operability (native `<table>`/`<button>`/`<form>` elements,
   no custom drag targets) — this is what makes it WCAG-2.2-AA-reachable without extra ARIA choreography.

**Explicitly out of scope, recorded as gaps (not "the real thing" quietly reduced):**
- **Canvas editor** (drag-and-drop, zoom, minimap, node-properties-panel-on-a-graph, live impact counters,
  search-by-node/role/input/reason) — master plan §12.5 names canvas as the *primary* form and the outline
  as the *accessible alternative*; this session builds only the alternative. Building a real canvas means
  choosing and integrating a graph-rendering library, a substantially separate effort with its own tech
  decision — not attempted here. The outline view is a complete, real, usable UI on its own (the spec's
  own words: "доступная табличная/outline альтернатива" is not "a degraded canvas," it is the other
  sanctioned form), just not the primary one.
- **Version diff view** — needs a real diff algorithm over two node/edge sets; not built. `GET` routes for
  both versions exist, so a future task can build this without new backend work.
- **Export to PDF/human-readable Markdown** — only machine-readable JSON export is built. PDF/Markdown
  rendering is a separate, real effort (templating, layout) deferred, not faked with a placeholder file.
- **Live impact counters** — would require a live production evaluation stream (Phase 6+ shadow/production
  concept); nothing in this codebase evaluates a policy against live traffic yet.

**Tech choices this task makes and records (implementation detail, not a locked PRD decision — same
posture `docs/decisions/OPEN-QUESTIONS.md`'s 2026-08-04 CI-runner-platform entry already used for a
comparable "PRD names the framework family, not the exact tool" gap):** Vite (build tool), Vitest +
`@testing-library/react` (test runner — mirrors `pytest`'s role on the Python side), plain `fetch` (no
data-fetching library) and plain CSS (no component library) — all deliberately minimal, since `PLAN-MISSION-5.md`
locks React/TypeScript but nothing more specific, and this is the first frontend code in the repo (no
existing convention to follow or violate).

**Requirement IDs in play:** `FR-ALG-01` (edit-time validation), `FR-ALG-07`/`FR-UX-02` (outline/keyboard
alternative, `P1`), master plan §12.5 (interface bullets — partially built, per above). `NFR-ARC-01`
(React/TypeScript, already locked).

---

## Task 1: `apps/api_tender/routers/algoritm.py` + registration

**Files:** create router; update `apps/api_tender/main.py`; create `tests/integration/test_algoritm_api.py`.

**Steps:**
- [ ] Pydantic request/response models mirroring `PolicyNode`/`PolicyEdge`'s own fields (no new shape
      invented — the wire format is the domain model's own fields).
- [ ] Routes, each a thin wrapper, permission strings `algorithm.policy.read`/`algorithm.policy.write`/
      `algorithm.policy.approve`/`algorithm.policy.activate`/`algorithm.simulation.read`/
      `algorithm.simulation.write` (new strings — permissions are ungoverned free text in this codebase,
      granted per role via `role_permissions`, same as every existing route's permission string):
      `POST /policy-graphs`, `GET /policy-graphs/{id}/versions`, `POST /policy-graphs/{id}/versions`,
      `GET /policy-versions/{id}`, `POST /policy-versions/{id}/nodes`, `POST /policy-versions/{id}/edges`,
      `POST /policy-versions/{id}/validate`, `POST /policy-versions/{id}/submit-for-approval`,
      `POST /policy-versions/{id}/activate`, `POST /policy-versions/{id}/kill-switch`,
      `POST /policy-versions/{id}/transition`, `POST /policy-versions/{id}/fork`,
      `GET /policy-versions/{id}/transitions`, `POST /policy-versions/{id}/simulate` (accepts a list of
      case payloads inline, runs `run_simulation`, records via `record_simulation_run`, returns the run),
      `GET /simulation-runs/{id}`, `GET /simulation-runs/{id}/case-traces`,
      `POST /policy-versions/{id}/compare/{other_id}`, `POST /research-dossiers`,
      `GET /research-dossiers/{id}`, `POST /policy-versions/{id}/link-dossier`.
- [ ] Domain `ValueError`s (from `PolicyNode.__post_init__`, `ImmutableVersionError`,
      `InvalidTransitionError`, `GraphInvalidError`, `MakerCheckerViolation`) map to `ApiError` 4xx at the
      route boundary — never an uncaught 500 (same discipline `calibration.py`'s `_validated_outcome`
      already applies).
- [ ] Register `algoritm.router` in `apps/api_tender/main.py`.
- [ ] Integration tests over real HTTP (`httpx.ASGITransport`, same fixture shape as
      `test_calibration_api.py`): create graph→draft→nodes→edges→validate (clean and with a deliberate
      dangling reference)→submit-for-approval (rejected, then accepted after fixing)→activate (maker/checker
      violation, then success with a second identity)→kill-switch→transitions history; simulate a small
      graph and read back the run + case traces; compare two versions; permission-denied path (403 for a
      user without the relevant permission, matching `user_without_permissions`'s existing pattern).

## Task 2: `apps/web` scaffold

**Files:** `apps/web/package.json`, `vite.config.ts`, `tsconfig*.json`, `index.html`, `src/main.tsx`,
`src/vitest.setup.ts`, `.gitignore` entry for `apps/web/node_modules`/`dist`.

**Steps:**
- [ ] Minimal, real Vite+React+TS app — `npm create vite` shape, hand-written rather than scaffolded
      interactively (no network access needed for the template itself; dependencies installed via
      `npm install` against the real registry).
- [ ] Vitest + `@testing-library/react` + `jsdom` wired as the test runner (`npm test`).
- [ ] Update `apps/web/README.md` to reflect "outline view implemented; canvas not yet" honestly, replacing
      the current "not implemented yet" blanket statement.

## Task 3: Outline/table policy-graph view

**Files:** `apps/web/src/api/algoritmClient.ts` (thin `fetch` wrapper, one function per route), `src/
PolicyOutline.tsx` (main view: version picker, node/edge table, add-node/add-edge forms, validation-issue
list), `src/SimulationPanel.tsx` (paste/build cases, run, show distribution + per-case trace path/
final_state — the "why accepted" view), `src/TransitionHistory.tsx`, `src/exportJson.ts`
(client-side JSON blob download, no backend export endpoint needed), plus a `.test.tsx` per component.

**Steps:**
- [ ] `PolicyOutline`: fetches nodes/edges for a `policy_version_id`, renders as an accessible `<table>`
      (`<th scope="col">`, one row per node/edge), forms to add a node/edge (native `<form>`/`<input>`/
      `<select>`, real `<label>` associations — no custom widgets to keyboard-trap), a "Validate" button
      showing `ValidationIssue`s inline next to the node they reference.
- [ ] `SimulationPanel`: a textarea for case JSON (or a small case builder form for the common
      `{case_id, inputs}` shape), "Run simulation" button, results table (status/terminal/reason codes per
      case) with an expandable row showing `path`/`final_state` — the literal "почему принято" trace.
- [ ] `TransitionHistory`: read-only table of `policy_version_transitions`.
- [ ] `exportJson`: one button, fetches nodes+edges+transitions, triggers a `Blob`/`URL.createObjectURL`
      download — machine-readable export only (human-readable PDF/Markdown deferred per Global Constraints).
- [ ] Component tests (Testing Library): table renders fetched nodes; add-node form submits and calls the
      right API function; validation issues render; every interactive element is reachable via `Tab` and
      operable via `Enter`/`Space` (Testing Library's `userEvent`, not a full axe/WCAG scanner — a real
      automated accessibility *scanner* pass is 5.E's job, this task proves keyboard reachability of what
      it built).

## Task 4: close-out

**Steps:**
- [ ] Backend: full gate (`pytest -m "not live_network"`, `ruff format --check`, `ruff check`, `mypy`,
      `check_v1_untouched.py`) green.
- [ ] Frontend: `npm test` (Vitest) green, `npm run build` (tsc + vite build) succeeds with no type errors.
- [ ] `docs/reports/WORKLOG.md` + `docs/decisions/OPEN-QUESTIONS.md` entries recording: the canvas/version-
      diff/PDF-export/live-impact-counter gaps, the Vite/Vitest tech-choice record, and the "outline is a
      complete alternative form, not a degraded canvas" framing.

# Phase 5, Task 5.B — АЛГОРИТМ: backend-core compiler/validator — Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention (see `docs/reports/WORKLOG.md`). No subagent handoff. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `docs/reports/PLAN-MISSION-5.md` §3 task 5.B's five rows on top of task 5.A's already-shipped
domain schema/lifecycle/research-dossier/source-registry (`packages/algorithm/policy_model.py`,
`policy_lifecycle.py`, `policy_store.py`, `research_dossier_model.py`/`_store.py`). 5.A built the
*container*; this task builds the *gates* — the graph must actually be validated, financial policies must
actually be blocked from `approved` without a real dossier, and activation must actually require two
distinct identities. Nothing here activates a real financial policy or invents a coefficient — `D-FIN`/
`TBD-04` remain exactly as untouched as 5.A left them.

**Scope, per `PLAN-MISSION-5.md` §3 task 5.B's table:**
1. Validator: unreachable nodes, cycles without bounded retry/human exit, input/output type mismatch,
   missing fallback/owner — blocking at edit-time and before submission for approval (`FR-ALG-01`,
   `FR-ALG-03`, master plan §12.6).
2. Branch coverage: every Rule-node branch has a test case; uncovered branches block approval
   (`FR-ALG-04`).
3. Compiler invariants: financial nodes have a research dossier; ML/Hybrid nodes stay
   not-activatable-until-Phase-8; hard constraints aren't hidden in soft weights; side effects go only
   through outbox (`FR-ALG-20`, `FR-ALG-08`, master plan §12.6).
4. Kill switch: immediately stops new evaluations of a version; in-flight ones finish in a defined way;
   transition log preserved (`FR-ALG-13`, `FR-ALG-14`).
5. Maker/checker activation: financial policy requires two distinct identities; a policy's designer
   cannot activate their own policy (`FR-ALG-12`, `FR-AUT-02`, `docs/adr/0005-authority-model.md`).

**Explicitly out of scope (5.C-5.E, not started here):** simulation/backtest engine, canvas/outline
frontend, and the 5.E QA suite proving the exit-gate criteria end-to-end (rollback rehearsal, kill-switch
rehearsal, accessibility). This task builds the mechanism that gates a version's progress through its
lifecycle — it does not simulate a policy against real/synthetic cases, and it activates zero real
financial policies (there are none to activate — `D-FIN`/`TBD-04` untouched).

**Architecture:** Three new files in `packages/algorithm/`: `policy_validator.py` (pure, no DB — mirrors
`policy_lifecycle.py`'s pure-function style, unit-tested directly), extensions to `policy_store.py`
(three new named functions layered on the existing `transition_version_status` primitive, which is left
behaviorally unchanged so 5.A's own tests keep passing unmodified), and one new migration
(`0020_algoritm_activation_guard.sql` — schema version 19→20, since master's own later merge already
used the numbers up to `0019`/schema `19`; see Task 0). No new package, no new app-layer routes (Phase 5
has no HTTP surface yet — the builder's frontend is 5.D, and nothing in `PLAN-MISSION-5.md` §3 task 5.B
asks for an API layer).

**Tech Stack:** unchanged from 5.A — Python 3.12, SQLAlchemy 2.0 async + `asyncpg`, PostgreSQL via
`testcontainers`, pytest/pytest-asyncio.

## Global Constraints

- **No invented coefficients, weights, or thresholds.** `D-FIN`/`TBD-04` remain untouched. This task
  gates *whether a version can progress*, never *what a financial policy's numbers are*.
- **Enforcement points are this task's own explicit reading of `PLAN-MISSION-5.md`'s terse phrasing, not
  spec text — recorded here and at close-out, same discipline 5.A used for its lifecycle-transition
  table.** `FR-ALG-03` says validation blocks "перед отправкой на утверждение" (before submission for
  approval) — read literally as the one unambiguous moment that phrase can mean: the `risk_review →
  approved` transition. `FR-ALG-12` says financial policy "активируется" (is activated) only with
  maker/checker — read as the `approved → active` transition specifically (activation, not approval).
  These two gates therefore live at two different transitions:
  - `submit_for_approval()` (new function) — runs the full validator (structural graph checks + branch
    coverage + financial-dossier-exists-and-is-approved + required-roles-exist), then calls the existing
    `transition_version_status(..., to_status="approved")` only if clean. Raises `GraphInvalidError`
    (carrying every issue found, not just the first) otherwise.
  - `activate_version()` (new function) — enforces maker/checker (financial-impact version's activator
    must differ from its `created_by`) and "only one active version per graph" (auto-suspends the
    graph's current active version, if any, before activating the target), then calls the existing
    `transition_version_status(..., to_status="active")`.
  - `transition_version_status()` itself is **not** modified — every other transition (`draft→simulation`,
    `→rejected`, `active→suspended/retired`, `suspended→active/retired`) goes through it directly,
    unchanged from 5.A, so 5.A's existing tests keep passing without edits.
  - `FR-ALG-01`'s "проверка ... на этапе редактирования" (checking at edit time) is satisfied by making
    the same structural validator (`policy_validator.validate_graph`) a plain, DB-free function any
    future editor UI (5.D) or API layer can call on-demand against an in-progress draft's nodes/edges —
    it does not itself gate any store write; only `submit_for_approval`'s call to it is a blocking gate.
- **Phase 5's node-type set has no `Terminal`/`Notification-escalation` type** (master plan §12.2 lists
  eight node types; `PLAN-MISSION-5.md` §1 and 5.A's own `ACTIVATABLE_NODE_TYPES` restrict this phase to
  four: `human`/`rule`/`gate`/`data_quality`). Two `§12.6` checklist items are read against that narrower
  set, not against the full eight-type model:
  - "один или явно допустимые start nodes" / "достижимый terminal" → a **start node** is any node with no
    incoming edge; a **terminal** is any node with no outgoing edge (a graph sink). No separate node type
    is needed to mark either — degree in the edge set is sufficient and invents no new field.
  - "все side effects идут через outbox" is **not mechanically checked in this task** — nothing in
    Phase 5's four node types carries an explicit side-effect/notification concept (that's the
    `Notification/escalation` type, not adopted into this phase's schema), so there is no field to check
    this against yet. Recorded as a real, honest gap for whenever that node type is built, not silently
    invented or skipped without a trace.
  - "hard constraints не спрятаны в soft weights" / "веса суммируются по утверждённой схеме" are **also
    not mechanically checked** — no weighting/scoring schema exists anywhere in this codebase
    (`coefficients_and_rationale`/`formula_or_decision_table` stay opaque JSON per 5.A's own ADR-0007
    rationale); checking this would require inventing the exact structure `D-FIN`/`TBD-04` forbid
    inventing. Recorded as a gap, same posture.
- **Cycle validity rule (this task's own reading, no spec algorithm given):** a cycle in the node graph is
  valid only if at least one node in it is either `node_type == "human"` (a human can always break out) or
  carries a `retry_policy` with a positive integer `max_attempts` **and** a `fallback_node_key` that
  references a real node outside the cycle. A cycle satisfying neither is flagged
  `unbounded_cycle_no_exit`.
- **Edge type-compatibility rule (this task's own reading):** for a direct edge `from → to`, any key
  present in **both** `from.output_contract` and `to.input_contract` must carry the same type string; a
  mismatch on a shared key is flagged. This checks *conflicts*, not full contract coverage — the spec
  gives no exact matching algorithm, and inventing 100%-coverage semantics (e.g. requiring every
  `input_contract` key be satisfied by some upstream edge) would go beyond what `12.6` actually states.
- **Branch coverage needs one small, additive, documented convention on the already-opaque
  `test_cases` field — not a schema change.** 5.A deliberately left `test_cases` as
  `tuple[dict[str, Any], ...]` with no fixed shape. `FR-ALG-04` cannot be checked at all without *some*
  way to say which test case covers which branch, so this task establishes: a `Rule` node's test-case
  dict **may** carry an optional `"covers_condition"` key naming an outgoing edge's `condition_label`.
  Coverage requires: every distinct non-null `condition_label` among a Rule node's outgoing edges has at
  least one test case whose `covers_condition` matches it; edges with no `condition_label` (a single
  unconditional branch) just require the node to have at least one test case at all. This is recorded
  here and at close-out as a necessary, minimal convention — not a fabricated requirement, and not a
  migration (still plain JSONB).
- **Kill switch's "in-flight evaluations complete in a defined way" is not built — there is no evaluation
  engine in this codebase yet** (nothing executes a policy graph against a real case; that starts in
  5.C/later). `kill_switch()` only does the half that already has something to act on: it is a
  reason-mandatory, clearly-named wrapper around the existing `active → suspended` transition. Recorded
  as a real, honest gap rather than a fabricated in-flight-completion mechanism.
- **Rollback works only against a `suspended` version, per 5.A's own fixed lifecycle table.** 5.A's
  `ALLOWED_TRANSITIONS` gives `retired` zero outgoing transitions — deliberately not touched here (5.A's
  own docstring flags that table as revisable "if 5.B/5.C's real compiler/simulation needs surface a
  different shape," but revising it is a bigger, separate decision than this task's own scope). Concretely:
  `activate_version()` called against a version whose current status is `suspended` is exactly "rollback
  to a previously-active version" (the `suspended → active` edge 5.A already allows); called against a
  `retired` version, `can_transition` already rejects it via the existing `InvalidTransitionError` — so
  rollback-from-retired is impossible by construction, and `retired` stays genuinely permanent. Recorded
  as a deliberate scope limit, not an oversight.
- **"Only one active version per policy_graph at a time" did not exist before this task and is added
  structurally, not just checked in application code** — same "structural, not just documented"
  discipline 5.A used for content immutability. A partial unique index
  (`policy_versions (policy_graph_id) WHERE status = 'active'`) is the real guarantee; `activate_version`'s
  app-level auto-suspend of the previous active version is a courtesy that keeps the common path from
  ever hitting that constraint, not the enforcement mechanism itself.
- **Maker/checker identity source:** `docs/adr/0005-authority-model.md` — "the identity who
  designed/authored a policy cannot be the one who activates it." Read as: `changed_by` (the activator)
  must differ from the target version's own `created_by` (the designer/author, already a required field
  on `PolicyVersion` since 5.A — no new field needed). Applies only when the version being activated
  contains at least one `financial_impact=True` node (`FR-ALG-12`'s own qualifier — non-financial
  policies activate with a single actor).
- Requirement IDs in play: `FR-ALG-01`/`FR-ALG-03`/`FR-ALG-04`/`FR-ALG-08`/`FR-ALG-12`/`FR-ALG-13`/
  `FR-ALG-14`/`FR-ALG-20` (`PLAN-MISSION-5.md` §3 task 5.B's own citations), `FR-AUT-02` (ADR-0005),
  `INV-13`/`INV-14` (per §0's read confirmation, unchanged from 5.A).

---

## Task 0: confirm current schema version

**Files:** none changed — investigation only.

**Steps:**
- [ ] Check `packages/platform/settings.py`'s current `EXPECTED_SCHEMA_VERSION` and the highest-numbered
      file in `migrations/` on `master` right now (the `docs/phase5-algoritm-scope-decision` merge that
      landed via PR #31 while this session's earlier merge work was in flight did not add a migration,
      but re-confirm before assuming `18` is still current, per this repo's own 2.A-follow-up precedent
      about hardcoded schema-version drift).

## Task 1: `packages/algorithm/policy_validator.py` — pure structural + coverage checks

**Files:**
- Create: `packages/algorithm/policy_validator.py`
- Create: `tests/unit/test_policy_validator.py`

**Steps:**
- [ ] `ValidationIssue` (frozen dataclass: `code: str`, `message: str`, `node_key: str | None`).
- [ ] `validate_graph_structure(nodes, edges) -> tuple[ValidationIssue, ...]`:
      - dangling references (`edges[].from_node_key`/`to_node_key`, `nodes[].fallback_node_key` must each
        name a real `node_key` in the same version) — checked first, since every other check assumes
        valid references.
      - start nodes (no incoming edge) exist — zero start nodes is itself an error
        (`no_start_node`).
      - every node reachable from the start-node set (BFS/DFS) — unreached nodes reported individually
        (`unreachable_node`).
      - at least one terminal (no outgoing edge) reachable from a start node (`no_reachable_terminal`).
      - every cycle (Tarjan SCC or equivalent) satisfies the cycle-validity rule from Global Constraints;
        violations reported per cycle (`unbounded_cycle_no_exit`).
      - edge type-compatibility per the Global Constraints rule (`io_type_mismatch`).
- [ ] `check_branch_coverage(nodes, edges) -> tuple[ValidationIssue, ...]`: for every `node_type == "rule"`
      node, gather its outgoing edges' `condition_label`s; for each distinct non-null label, require a
      matching `covers_condition` in that node's `test_cases`; report `uncovered_branch` per missing
      label. A rule node with outgoing edges but zero `test_cases` reports `no_test_cases` regardless of
      labels.
- [ ] `validate_graph(nodes, edges) -> tuple[ValidationIssue, ...]` — concatenates both of the above; this
      is the one function 5.D's future editor (or `submit_for_approval`) actually calls.
- [ ] Unit tests: a minimal valid graph (passes clean); one fixture per issue code above (dangling
      reference, no start node, unreachable node, no reachable terminal, an unbounded human-free/
      retry-free cycle *and* a valid bounded-retry cycle that should NOT be flagged, an I/O type mismatch,
      an uncovered Rule branch, a covered one that should NOT be flagged).

## Task 2: `packages/algorithm/policy_store.py` — `submit_for_approval`

**Files:**
- Update: `packages/algorithm/policy_store.py` (`GraphInvalidError` exception; `submit_for_approval`)
- Update: `tests/integration/test_policy_store.py`

**Steps:**
- [ ] `submit_for_approval(conn, *, policy_version_id, changed_by, reason=None)`: loads nodes/edges via
      the existing `list_nodes`/`list_edges`, runs `policy_validator.validate_graph`, then two DB-backed
      checks this task adds:
      - every non-null `required_role` among the version's nodes exists in `roles` (plain `SELECT`
        against the table `packages/platform/rbac/store.py` already reads — no cross-package business-
        logic import, just a table both packages may read, same as any other platform-owned table);
        missing roles reported as `unknown_role` issues.
      - every `financial_impact=True` node requires the *version's own* `research_dossier_id` to be set
        **and** the referenced `research_dossiers.approved_at` to be non-null; missing/unapproved reported
        as `missing_approved_dossier`.
      - if any issues (structural, coverage, or these two): raise `GraphInvalidError(issues)` — a tuple of
        every issue, not just the first (matching this codebase's existing "surface everything, not the
        first error" pattern in e.g. `boq_summary.py`). Nothing is written to the DB on failure.
      - if clean: calls the existing `transition_version_status(..., to_status="approved")` unchanged.
- [ ] Integration tests: a graph with an unreachable node is rejected without a status change; a
      `financial_impact` node with no dossier is rejected; the same node with a dossier whose
      `approved_at IS NULL` is still rejected; a clean graph with a `financial_impact` node and a real
      approved dossier transitions to `approved`; a Rule node with an uncovered branch is rejected, and
      adding a `covers_condition`-matching test case then lets it through.

## Task 3: `packages/algorithm/policy_store.py` — `activate_version` + kill switch + rollback

**Files:**
- Update: `packages/algorithm/policy_store.py` (`MakerCheckerViolation`; `activate_version`;
  `kill_switch`)
- Update: `tests/integration/test_policy_store.py`

**Steps:**
- [ ] `activate_version(conn, *, policy_version_id, changed_by, reason=None)`: loads the version's
      `created_by`/`policy_graph_id` and its nodes; if any node is `financial_impact=True` and
      `changed_by == created_by`, raises `MakerCheckerViolation`. Otherwise: finds the graph's current
      `active` version (if any, and different from the target) and transitions it to `suspended` first
      (reason auto-noted as superseded-by-activation, a factual system note, not a fabricated business
      reason), then calls `transition_version_status(..., to_status="active")` on the target. Relies on
      `can_transition` to reject activating a version that isn't currently `approved`/`suspended` (already
      true from 5.A, unchanged).
- [ ] `kill_switch(conn, *, policy_version_id, changed_by, reason)`: `reason` is a required positional/
      keyword `str` (not `| None` — unlike every other transition function, a kill switch always needs a
      recorded reason); requires current status `== "active"` (else raises `ValueError` — killing a
      non-running version isn't the operation this function models); calls
      `transition_version_status(..., to_status="suspended", reason=reason)`.
- [ ] Integration tests: activating a financial-impact version with the same `changed_by` as
      `created_by` raises `MakerCheckerViolation`; a different identity succeeds; activating a second
      version of the same graph auto-suspends the first (assert via `list_versions_by_graph`); rollback
      (`activate_version` called against a `suspended` version) succeeds and re-suspends whatever was
      active; `kill_switch` on a non-active version raises; on an active version it transitions to
      `suspended` and the transition log records the given reason.

## Task 4: migration — one-active-version-per-graph guard

**Files:**
- Create: `migrations/00NN_algoritm_activation_guard.sql` (`NN` = confirmed current-highest + 1 from
  Task 0)
- Update: `packages/platform/settings.py` (`EXPECTED_SCHEMA_VERSION` bump)
- Update: every test hardcoding the prior schema version (repeat of 5.A's own Task 1 checklist —
  `tests/integration/test_api_tender_health.py`, `test_api_vendor_health.py`,
  `test_migrations_runner.py`, confirmed exhaustively via `grep`, not assumed to be the same three files
  5.A touched)

**Steps:**
- [ ] `CREATE UNIQUE INDEX policy_versions_one_active_per_graph ON policy_versions (policy_graph_id)
      WHERE status = 'active';` — the real, structural guarantee `activate_version`'s app-level
      auto-suspend is a courtesy on top of, not a replacement for.
- [ ] `grep -rn "EXPECTED_SCHEMA_VERSION\|expected_version=\|current_version() ==" tests/ packages/` before
      editing, so no hardcoded-version site is missed (this is exactly the class of mistake 2.A's own
      WORKLOG follow-up flagged).

## Task 5: close-out

**Steps:**
- [ ] Full gate (`pytest -m "not live_network"`, `ruff format --check`, `ruff check`, `mypy`,
      `check_v1_untouched.py`) green.
- [ ] `docs/reports/WORKLOG.md` entry + `docs/decisions/OPEN-QUESTIONS.md` entry recording every Global
      Constraints interpretation above (enforcement-point choice, start/terminal-as-degree reading,
      cycle-validity rule, edge-type-compatibility rule, the `covers_condition` convention, the two
      explicitly-unchecked §12.6 items — outbox side effects and hard-constraints-in-soft-weights — the
      kill-switch in-flight-completion gap, and the suspended-only rollback scope limit) as this task's
      own deviations, same discipline as 5.A's close-out.

---

## What remains after this task (for 5.C/5.D/5.E, not started here)

- No evaluation/execution engine exists — `validate_graph`/`submit_for_approval`/`activate_version` gate
  lifecycle progress, but nothing in this codebase runs a policy graph against a real or synthetic case
  yet (that is 5.C's simulation/backtest engine).
- No API layer/UI exposes any of this (5.D).
- Rollback/kill-switch *rehearsal* (proving the behavior end-to-end as an exit-gate artifact) and
  accessibility are 5.E, not this task.
- `outbox`-routed side effects and hard-constraint/soft-weight separation remain unchecked pending a
  node type / scoring schema this task deliberately does not invent.

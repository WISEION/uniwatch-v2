# Phase 5, Task 5.C — АЛГОРИТМ: simulation/backtest engine — Implementation Plan

> **For agentic workers:** executed inline, in the same session that wrote it — this repo's established
> convention (`docs/reports/WORKLOG.md`). No subagent handoff. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Build `docs/reports/PLAN-MISSION-5.md` §3 task 5.C's three rows on top of 5.A's schema and 5.B's
validator/compiler (`packages/algorithm/policy_model.py`, `policy_validator.py`, `policy_store.py`).
5.A/5.B built the graph *container* and its *gates*; this task is the first thing in the whole codebase
that actually **runs** a policy graph against a case and records what happened. `D-FIN`/`TBD-04` remain
exactly as untouched as 5.B left them — nothing here invents a weight, threshold, or FX rate.

**Scope, per `PLAN-MISSION-5.md` §3 task 5.C's table:**
1. Simulation engine: synthetic vendor cases (Phase 3), frozen real tender snapshots (Phase 1/2, without
   touching the source), historical outcomes (Phase 4, when they exist), candidate policy vs active policy
   comparison (`FR-ALG-05`, master plan §12.7).
2. Sensitivity analysis: influence of changing weights/thresholds on the outcome distribution (`FR-ALG-06`).
3. Cost/revenue impact range (not false precision), false-positive/negative review queue, human override
   rate, rollback rehearsal log (master plan §12.7).

**Explicitly out of scope (5.D/5.E, not started here):** canvas/outline frontend, the 5.E QA suite
(rollback rehearsal *test*, kill-switch rehearsal *test*, accessibility). This task builds the engine and
its persistence; it exposes no HTTP API (Phase 5 has none yet — same posture as 5.A/5.B).

**Architecture:**
- `packages/algorithm/simulation_engine.py` (new, pure, no DB) — `SimulationCase`, `CaseTrace`,
  `run_case()`, `run_simulation()`, `compare_versions()`. Mirrors `policy_validator.py`'s pure-function,
  unit-tested-directly style.
- `packages/algorithm/simulation_store.py` (new) — persists `algorithm_simulation_runs` (master plan
  §14.5's own name for this table). Aggregates traces into distributions/ranges at write time; exposes
  read queries including the side-by-side review-queue view.
- `packages/decision/simulation_case_builder.py` (new) — converts already-real decision-layer facts
  (`packages/decision/bid_readiness.py`'s `BidReadinessCandidate`, `packages/decision/calibration_model.py`'s
  `TenderOutcome`) into the generic `SimulationCase` shape `packages/algorithm` consumes. Lives in
  `packages/decision`, not `packages/algorithm`, because `packages/algorithm` "does not own business facts"
  (`AGENTS.md` §3) — it must stay ignorant of what a BOQ or a vendor offer is.
- One new migration: `0020_algoritm_simulation_runs.sql` (schema version 19→20).

**Tech Stack:** unchanged — Python 3.12, SQLAlchemy 2.0 async + `asyncpg`, PostgreSQL via `testcontainers`,
pytest/pytest-asyncio.

## Global Constraints

- **The fundamental gap this task inherits from 5.B: no node carries executable logic.** `PolicyNode` has
  no formula/decision-table/weight field — `test_cases` is deliberately opaque JSON (5.A), and 5.B only
  added `covers_condition` for branch-coverage bookkeeping. There is nothing in this schema a simulation
  engine could numerically *evaluate*. Building an engine that invents branching logic (a parser for
  `preconditions` strings, a scoring formula from `research_dossier`'s opaque `coefficients_and_rationale`)
  would violate hard ban #2 and `D-FIN`/`TBD-04`. This task's engine is therefore a **test-case-replay
  engine, not a formula executor**: a node's real behavior for a given case is *the human-declared example*
  in its own `test_cases`, not a computed value. This is a deliberate reading, recorded here and at
  close-out, not a lesser version of "the real thing" quietly substituted for it.
- **No new key invented — `test_cases`' existing `"input"`/`"expected_output"` scaffolding (already present,
  unused, in 5.B's own test fixtures, e.g. `tests/unit/test_policy_validator.py`'s
  `{"input": {}, "expected_output": {}, "covers_condition": ...}`) is what this task actually wires up,
  not a new field.** A test case *matches* the engine's running case `state` (see below) when every key in
  its own `"input"` dict is present in `state` with an equal value (subset match; keys the test case
  doesn't mention are irrelevant to it). No schema change — still plain JSONB.
- **Running `state`, not a static case:** `run_case` keeps a `state: dict[str, Any]` seeded from
  `SimulationCase.inputs`. When a branch node's matching test case is found, that test case's own
  `expected_output` (if present) is merged into `state` before moving on — a later node's `input` match can
  therefore depend on an earlier node's declared output, the same producer/consumer relationship 5.B's
  `io_type_mismatch` check already validates structurally between adjacent nodes' contracts. A node with a
  single unconditional outgoing edge and exactly one test case whose `input` matches current `state` also
  merges its `expected_output` (no ambiguity to resolve, just state propagation); zero or non-matching test
  cases leave `state` unchanged and still take the sole edge.
- **Deterministic-edge shortcut:** a node with exactly one outgoing edge whose `condition_label IS NULL`
  needs no test-case lookup to determine *which edge* — the graph itself is unconditional there (state
  merge per above still applies). Lookup is only needed to pick *which* edge at a branch point (2+ outgoing
  edges, or an edge carrying a `condition_label`).
- **Human nodes: an explicit override beats a replayed example.** A `SimulationCase` may carry
  `human_overrides: dict[node_key, condition_label]` — a case-supplied stand-in for "what the human said" at
  a given Human node (this is what makes "historical outcomes" simulable at all: the recorded record already
  contains what actually happened). If no override is supplied for a Human node at a branch point and no
  test case matches either, the trace stops there with status `awaiting_human` — never a guessed branch
  (hard ban #3).
- **Every other undetermined case (no override, not a Human node, zero or 2+ matching distinct
  `covers_condition` values, a test case naming an edge that doesn't exist) is `status="undetermined"` with
  a specific reason code of this task's own naming (`no_matching_test_case`, `ambiguous_test_cases`,
  `test_case_covers_unknown_edge`) — never silently defaulted to any particular edge.**
- **A hard step cap (`len(nodes) * 2`) guards against a pathological walk** (5.B's validator already
  requires every cycle to have a human exit or a bounded-retry exit, but simulation does not re-run the
  validator — a caller who feeds it an unvalidated graph gets `undetermined`/`step_limit_exceeded`, not an
  infinite loop).
- **`FR-ALG-06` (sensitivity analysis) is recorded as an honest gap, not built.** Its own text is "influence
  of *changing weights/thresholds*" — no weight or threshold representation exists anywhere in this
  codebase (the same gap 5.B's close-out already recorded for the compiler's "hard constraints not hidden
  in soft weights" check). Building a substitute (e.g., perturbing which test case "wins" as a proxy for
  weight sensitivity) would invent a semantic the spec never gave. `FR-ALG-06` is `P1` (not `P0`, unlike
  `FR-ALG-05`) — deferring it is consistent with this repo's existing precedent of shipping the
  `P0` mechanism and recording the `P1`/invention-blocked gap rather than shipping a fabricated substitute.
- **"Candidate vs active policy" and "distribution/subgroup results" need no correspondence to be
  invented** — running the same `list[SimulationCase]` through two node/edge sets and diffing
  `terminal_node_key`/`reason_codes` per case, or grouping already-produced traces by any case-declared
  input field, is purely structural. `compare_versions()`/`run_simulation(..., subgroup_by=...)` do exactly
  this and nothing more.
- **"Cost/revenue impact range" only aggregates numbers the case source already computed for real
  reasons** (`BidReadinessCandidate.summary.total_priced_amount`, `TenderOutcome.our_submitted_amount`/
  `winner_amount`) — the engine never derives a new monetary figure. Ranges (min/max/median) are grouped by
  `(terminal_node_key, currency)`, **never summed across currencies** (same discipline
  `packages/decision/matching.py` already applies — no FX rate is invented, `D-TAX`). A case with a
  `monetary_amount` but no declared `monetary_currency` is excluded from every range and counted separately
  (`monetary_amount_uncurrencied_count`) rather than silently mixed in.
- **"False-positive/negative review queue" and "human override rate" are NOT auto-classified.** Deciding
  whether a given simulated terminal/reason-code combination "agrees" with a real-world
  `actual_outcome_label` (e.g. `TenderOutcome.outcome` = `"lost"`) would require inventing a correspondence
  between free-text reason codes and free-text outcome labels — a business rule no source document
  supplies. This task instead follows this codebase's own precedent
  (`packages/decision/calibration_summary.py`: "arithmetic gives a delta, a human makes the call") —
  `simulation_store.list_case_traces()` returns every case's simulated result *and* its declared
  `actual_outcome_label` side by side, unclassified; a human reviewing the run decides what counts as a
  miss. No new table for this — it is a read over the run's own persisted `case_traces` column.
- **"Rollback rehearsal log" needs no new code.** 5.B's `policy_version_transitions` (append-only, every
  transition including a `suspended → active` rollback) already *is* this log — `policy_store.
  list_transitions_by_version()` already reads it. 5.E's future rehearsal test is what turns this into a
  proven exit-gate artifact; this task adds nothing here.
- Requirement IDs in play: `FR-ALG-05` (`P0`), `FR-ALG-06` (`P1`, recorded gap), master plan §12.7's own
  bullet list (`PLAN-MISSION-5.md` §3 task 5.C's citations). `D-FIN`/`TBD-04`/`D-TAX` untouched.

---

## Task 0: confirm current schema version

**Files:** none changed — investigation only.

**Steps:**
- [ ] Re-confirm `packages/platform/settings.py`'s `EXPECTED_SCHEMA_VERSION` and the highest-numbered file
      in `migrations/` on `master` right now (expected `19`/`0019_algoritm_activation_guard.sql` per this
      session's own earlier read — re-check before assuming, per 2.A-follow-up precedent).

## Task 1: `packages/algorithm/simulation_engine.py` — pure test-case-replay engine

**Files:**
- Create: `packages/algorithm/simulation_engine.py`
- Create: `tests/unit/test_simulation_engine.py`

**Steps:**
- [ ] `SimulationCase` (frozen dataclass): `case_id: str`, `inputs: dict[str, Any]`,
      `human_overrides: dict[str, str] = field(default_factory=dict)`,
      `monetary_amount: Decimal | None = None`, `monetary_currency: str | None = None`,
      `actual_outcome_label: str | None = None`.
- [ ] `CaseTrace` (frozen dataclass): `case_id`, `status: str` (`completed` / `awaiting_human` /
      `undetermined`), `path: tuple[str, ...]` (node keys visited in order), `terminal_node_key: str | None`,
      `reason_codes: tuple[str, ...]`, `undetermined_reason: str | None`, `final_state: dict[str, Any]`
      (the running `state` at wherever the walk stopped — the raw material a future 5.D "why accepted" trace
      view would render), `monetary_amount`, `monetary_currency`, `actual_outcome_label` (last three copied
      through from the input case so a stored trace is self-contained).
- [ ] `_find_start_node(nodes, edges) -> str`: same incoming-adjacency computation as
      `policy_validator._build_adjacency` (fallback edges count as incoming too); raises `ValueError` if
      zero or more than one — `run_case`/`run_simulation` assume an already-`validate_graph`-clean graph,
      same precondition `policy_store.submit_for_approval` already enforces before a version can progress.
- [ ] `_matching_test_case(node, state) -> dict | None`: the node's own `test_cases` filtered to those whose
      `"input"` dict is a subset-match of `state` (missing/absent `"input"` never matches).
- [ ] `_select_next_edge(node, outgoing_edges, state, human_overrides) -> tuple[edge | None, str | None,
      dict | None]` (edge chosen, or `None` + an `undetermined_reason`/`"awaiting_human"` sentinel, plus the
      winning test case's `expected_output` to merge if any): implements the deterministic-shortcut,
      human-override, and test-case-matching rules from Global Constraints, in that priority order.
- [ ] `run_case(nodes, edges, case: SimulationCase) -> CaseTrace`: walks from the start node with
      `state = dict(case.inputs)`, calling `_select_next_edge` at every node, merging any returned
      `expected_output` into `state`, appending to `path`, stopping at: a terminal (zero outgoing edges) →
      `completed`; the `awaiting_human` sentinel → `awaiting_human`; any other undetermined sentinel →
      `undetermined`; step cap exceeded → `undetermined`/`step_limit_exceeded`.
- [ ] `run_simulation(nodes, edges, cases: list[SimulationCase]) -> tuple[CaseTrace, ...]`: `run_case` over
      every case, in order.
- [ ] `compare_versions(nodes_a, edges_a, nodes_b, edges_b, cases) -> tuple[VersionComparison, ...]`:
      `VersionComparison` (frozen dataclass: `case_id`, `terminal_a`, `terminal_b`, `reason_codes_a`,
      `reason_codes_b`, `agrees: bool`) — runs both, pairs by `case_id`, flags disagreement on
      `terminal_node_key` or `reason_codes`.
- [ ] Unit tests: linear graph (no branch) walks straight through; a Rule node with 2 test cases (each
      declaring `inputs`+`covers_condition`) routes two different cases down two different edges; a case
      matching zero test cases at a branch → `undetermined`/`no_matching_test_case`; a case matching two
      test cases with different `covers_condition` → `undetermined`/`ambiguous_test_cases`; a Human node
      with a matching `human_overrides` entry routes correctly and *overrides* what a test case would have
      said; a Human node with neither an override nor a matching test case → `awaiting_human`; a
      pathological unbounded-cycle-shaped input (deliberately not run through the validator first) hits the
      step cap and reports `undetermined`/`step_limit_exceeded` rather than hanging;
      `compare_versions` reports agreement/disagreement correctly on two hand-built small graphs sharing
      case IDs.

## Task 2: `migrations/0020_algoritm_simulation_runs.sql`

**Files:**
- Create: `migrations/0020_algoritm_simulation_runs.sql`
- Update: `packages/platform/settings.py` (`EXPECTED_SCHEMA_VERSION` bump)
- Update: every test hardcoding the prior schema version (`grep -rn "EXPECTED_SCHEMA_VERSION\|
  expected_version=\|current_version() =="  tests/ packages/` first, per 5.B's own Task 4 precedent — do
  not assume the same three files as before are still the only hits)

**Steps:**
- [ ] `algorithm_simulation_runs`: `id serial PK`, `policy_version_id int NOT NULL REFERENCES
      policy_versions(id)`, `compared_against_version_id int NULL REFERENCES policy_versions(id)`,
      `case_set_label text NOT NULL`, `case_source text NOT NULL CHECK (case_source IN
      ('synthetic_vendor','frozen_real_tender','historical_outcome','mixed'))`, `case_count int NOT NULL`,
      `completed_count int NOT NULL`, `awaiting_human_count int NOT NULL`, `undetermined_count int NOT
      NULL`, `terminal_distribution jsonb NOT NULL`, `reason_code_distribution jsonb NOT NULL`,
      `subgroup_distribution jsonb NULL`, `monetary_range jsonb NULL`,
      `monetary_amount_uncurrencied_count int NOT NULL DEFAULT 0`, `case_traces jsonb NOT NULL`,
      `run_by text NOT NULL`, `run_at timestamptz NOT NULL DEFAULT now()`, `notes text NULL`.
- [ ] No update/delete path for this table in application code — a simulation run is itself immutable
      historical evidence of what a version did against a given case set at a given time (same
      no-mutation-function discipline as `policy_nodes`/`policy_edges`).

## Task 3: `packages/algorithm/simulation_store.py`

**Files:**
- Create: `packages/algorithm/simulation_store.py`
- Create: `tests/integration/test_simulation_store.py`

**Steps:**
- [ ] `record_simulation_run(conn, *, policy_version_id, case_set_label, case_source, traces:
      tuple[CaseTrace, ...], run_by, compared_against_version_id=None, notes=None) -> int`: computes
      `terminal_distribution`/`reason_code_distribution` (counts), `monetary_range` (min/max/median per
      `(terminal_node_key, currency)`, excluding uncurrencied amounts into their own counter), inserts one
      row with `case_traces` as a JSON array of the traces' own fields.
- [ ] `record_comparison_run(conn, *, policy_version_id, compared_against_version_id, case_set_label,
      comparisons: tuple[VersionComparison, ...], run_by) -> int`: same table, `case_source='mixed'`,
      `case_traces` stores the comparison pairs instead of single traces (distinguishable by a
      `"kind": "comparison"` marker in the stored JSON — no schema change, same jsonb column).
- [ ] `get_simulation_run(conn, *, run_id) -> dict[str, Any] | None`.
- [ ] `list_simulation_runs_by_version(conn, *, policy_version_id) -> list[dict[str, Any]]`.
- [ ] `list_case_traces(conn, *, run_id) -> list[dict[str, Any]]`: the review-queue/override-rate surface —
      returns every stored case's simulated result and `actual_outcome_label` side by side, unclassified
      (per Global Constraints).
- [ ] Integration tests: recording a run with a mix of `completed`/`awaiting_human`/`undetermined` traces
      produces correct counts and distributions; monetary range groups correctly by currency and excludes
      an uncurrencied amount into its own counter (assert it is *not* silently folded into any range);
      `list_case_traces` round-trips `actual_outcome_label` for a case that has one and `None` for one that
      doesn't (never fabricated); `record_comparison_run` + `get_simulation_run` round-trip a comparison
      run; `list_simulation_runs_by_version` returns multiple runs for the same version ordered sensibly.

## Task 4: `packages/decision/simulation_case_builder.py`

**Files:**
- Create: `packages/decision/simulation_case_builder.py`
- Create: `tests/unit/test_simulation_case_builder.py`

**Steps:**
- [ ] `build_case_from_bid_readiness(candidate: BidReadinessCandidate, *, case_id, monetary_currency=None,
      actual_outcome_label=None, human_overrides=None) -> SimulationCase`: `inputs` = `{"coverage_pct":
      candidate.summary.green_pct + candidate.summary.yellow_pct, "is_lottery": candidate.is_lottery,
      "critical_line_count": len(candidate.critical_lines), "green_pct": ..., "yellow_pct": ...,
      "red_pct": ...}`; `monetary_amount = candidate.summary.total_priced_amount`. This one function serves
      both the "synthetic vendor cases" and "frozen real tender snapshots" bullets — the distinction is
      purely which `BoqLine`/offer data the *caller* built the candidate from (a real frozen fixture's BOQ
      lines vs a hand-built synthetic set); the caller picks the `case_source` label when recording the run.
- [ ] `build_case_from_tender_outcome(outcome: dict[str, Any], *, case_id, human_overrides=None) ->
      SimulationCase`: `inputs = {"outcome": outcome["outcome"]}`; `monetary_amount`/`monetary_currency`
      from `our_submitted_amount`/`currency` when present (Decimal-parsed, `None` propagated honestly when
      the source field is `None` — never defaulted to `0`); `actual_outcome_label = outcome["outcome"]`
      verbatim (`won`/`lost`/`cancelled` — `calibration_model.OUTCOME_TYPES`, not re-invented here).
- [ ] Unit tests: a `BidReadinessCandidate` with a real captured-fixture-shaped `BoqMatchSummary` (reuse
      `tests/unit/test_matching.py`-style fixtures already in this codebase, not fabricated new totals)
      produces the expected `inputs`/`monetary_amount`; a `TenderOutcome`-shaped dict with `winner_amount`
      but a `None` `our_submitted_amount` propagates `None` faithfully (does not invent `0`); currency
      passthrough is exact.

## Task 5: close-out

**Steps:**
- [ ] Full gate (`pytest -m "not live_network"`, `ruff format --check`, `ruff check`, `mypy`,
      `check_v1_untouched.py`) green.
- [ ] `docs/reports/WORKLOG.md` entry + `docs/decisions/OPEN-QUESTIONS.md` entry recording: the
      test-case-replay reading of "simulation" (not a formula executor), the new `"inputs"` convention on
      `test_cases`, the `FR-ALG-06` sensitivity-analysis gap (P1, blocked on the same missing
      weight/threshold schema 5.B already flagged), the unclassified review-queue/override-rate design
      (precedent: `calibration_summary.py`), and the currency-never-mixed monetary-range rule.

---

## What remains after this task (for 5.D/5.E, not started here)

- No API layer/UI exposes any of this (5.D) — `simulation_store`'s functions are the contract a future
  route/editor calls.
- `FR-ALG-06` (sensitivity analysis) stays unbuilt pending a weight/threshold representation this task does
  not invent — same posture as 5.B's outbox-side-effects/hard-constraint gaps.
- Rollback/kill-switch *rehearsal* (proving the behavior end-to-end as an exit-gate artifact) and
  accessibility remain 5.E.
- Auto-classifying simulated-vs-actual agreement (turning the unclassified review queue into a real
  false-positive/negative *count*) is deliberately not built — it would require inventing a correspondence
  between free-text reason codes and free-text outcome labels that no source document supplies.

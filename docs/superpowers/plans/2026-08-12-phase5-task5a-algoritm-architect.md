# Phase 5, Task 5.A — АЛГОРИТМ: architect (domain schema, lifecycle, research-dossier ADR, source registry) — Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention (see `docs/reports/WORKLOG.md`). No subagent handoff. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the four artifacts `docs/reports/PLAN-MISSION-5.md` §3's task 5.A names as the first,
blocking task of Phase 5 — this is the very first code in `packages/algorithm` (currently just a
`README.md`). Per `docs/decisions/OPEN-QUESTIONS.md` (2026-08-12, "Owner decision: Phase 5 АЛГОРИТМ
builder is still in scope, on top of Decision Core"), this builds a genuinely separate, versionable
policy-graph mechanism — it does not replace or reimplement `packages/decision`'s already-built 4.A
Go/No-Go logic. How the two relate architecturally is explicitly Phase 5 planning's own next question,
not decided by this task.

**Scope, exactly per `PLAN-MISSION-5.md` §3 task 5.A's table:**
1. `packages/algorithm` domain schema: a policy node's full property set.
2. Lifecycle state machine (`draft → simulation → business_review → risk_review → approved → active →
   retired`, with `rejected`/`suspended` branches); approved/active content is immutable.
3. ADR: research-dossier schema.
4. Registry of official sources (law, FX, VAT, price indices) with effective dates.

**Explicitly out of scope (5.B-5.E, not started here):** the compiler/validator (unreachable-node/cycle
detection, branch-coverage check, ALG-RESEARCH-gate enforcement), simulation/backtest engine, canvas/
outline frontend, and the 5.E QA suite proving the exit-gate criteria end-to-end. This task defines the
*data shape* those later tasks operate on — it does not implement graph validation, does not activate
any policy, and seeds zero real financial/legal coefficients (`D-FIN`/`TBD-04` remain untouched, per
`PLAN-MISSION-5.md` §4/§6: no financial policy gets `approved` without a full ALG-RESEARCH dossier, and
that gate's *enforcement* is 5.B's compiler, not this task's).

**Architecture:** New `packages/algorithm` package, mirroring `packages/decision`'s existing
model/store split (see `calibration_model.py`/`calibration_store.py` as the closest existing analogue —
pure dataclasses with `__post_init__` validation in `_model.py`, async SQLAlchemy `text()` queries in
`_store.py`, append-only where the domain calls for it). New migration
`0018_algoritm_policy_graph.sql` (schema version 17→18).

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async + `asyncpg`, PostgreSQL (via `testcontainers` in
tests), pytest/pytest-asyncio — no new dependencies, matching every prior phase.

## Global Constraints

- **No invented coefficients, weights, or thresholds anywhere in this task.** `D-FIN`/`TBD-04` (candidate
  algorithms A-E's formula coefficients, master plan §13.2) are untouched — this task builds the
  *container* a real, researched policy will eventually live in, never a policy itself. The official
  source registry (item 4) is a structural home for real, human-sourced facts (a cited law, an actual
  CBAR FX rate, an actual VAT percentage) entered later with their own citation — this task seeds it
  with **zero rows** in application code. Any example value appearing in a test is explicitly synthetic
  test fixture data, never presented as a real rate.
- **Content immutability is structural, not just checked.** Once a `policy_version` reaches `approved` or
  `active`, no store function in this package ever issues an `UPDATE`/`DELETE` against that version's
  `policy_nodes`/`policy_edges` rows — the only way to change content is `fork_new_draft_version()`,
  which copies the current node/edge set into a **new** `draft` version row. This mirrors
  `decision_store.py`/`calibration_store.py`'s existing discipline of having no update function for an
  append-only concept, rather than relying on an application-level "please don't" convention.
  `policy_versions.status` itself is the one legitimately mutable column (lifecycle progression is not a
  content edit) — but every transition is logged to an append-only `policy_version_transitions` table so
  "журнал переходов сохраняется" (5.B/5.E's kill-switch/rollback requirements) has real history to read
  once those tasks exist, even though this task builds no kill switch itself.
- **The lifecycle transition graph is this task's own explicit modeling choice, recorded, not silently
  assumed.** `PLAN-MISSION-5.md` states the linear sequence and names `rejected`/`suspended` as
  "ветви" (branches) without specifying exactly which states branch to which. This task fixes a concrete
  transition table (see Task 2) and records the choice in `docs/decisions/OPEN-QUESTIONS.md` at
  close-out — it is a reasonable reading of the stated sequence, not a fabricated requirement, but it is
  not itself spec text and should be revisited if 5.B/5.C's real compiler/simulation needs surface a
  different shape.
- **Node type restriction (FR-ALG-08) is enforced at the model layer.** `PLAN-MISSION-5.md` §1: only
  `human`/`rule`/`gate`/`data_quality` nodes may exist in this phase's data; `ml`/`hybrid` node types are
  representable in the schema (so a later phase never needs a schema migration to add them) but this
  task's model rejects constructing one — the *activation* block for graphs containing them is 5.B's
  compiler, not built here, since there is no compiler yet for anything to block.
- Requirement IDs in play: `FR-ALG-02`/`FR-ALG-08`/`FR-ALG-10`/`FR-ALG-11`/`FR-ALG-20`/`FR-ALG-21`/
  `FR-ALG-23` (`PLAN-MISSION-5.md` §3 task 5.A's own citations), `INV-13`/`INV-14` (PRD, per §0's read
  confirmation).

---

## Task 1: Migration — `policy_graphs`/`policy_versions`/`policy_nodes`/`policy_edges`/`policy_version_transitions`

**Files:**
- Create: `migrations/0018_algoritm_policy_graph.sql`
- Update: `packages/platform/settings.py` (`expected_schema_version` default `17` → `18`)
- Update: `tests/integration/test_api_tender_health.py`, `tests/integration/test_api_vendor_health.py`,
  `tests/integration/test_migrations_runner.py` (hardcoded `17` → `18`)

**Steps:**
- [ ] Write the migration with the five tables above, `CHECK` constraints for `node_type`/`status`
      enums, `policy_version_transitions` as a pure append-only log (`FK`s to `policy_versions`, no
      unique/mutable columns).
- [ ] Bump `EXPECTED_SCHEMA_VERSION` and every test hardcoding `17` (task 2.A's own follow-up in
      `WORKLOG.md` records exactly this class of mistake if skipped).

## Task 2: `packages/algorithm/policy_model.py` + `policy_lifecycle.py`

**Files:**
- Create: `packages/algorithm/policy_model.py` (`PolicyGraph`, `PolicyVersion`, `PolicyNode`,
  `PolicyEdge` dataclasses; `NODE_TYPES = ("human", "rule", "gate", "data_quality", "ml", "hybrid")` with
  `ACTIVATABLE_NODE_TYPES` a strict subset per FR-ALG-08; `LIFECYCLE_STATUSES`)
- Create: `packages/algorithm/policy_lifecycle.py` (`ALLOWED_TRANSITIONS` table, `can_transition()`,
  `IMMUTABLE_STATUSES = ("approved", "active")`)
- Create: `tests/unit/test_policy_model.py`, `tests/unit/test_policy_lifecycle.py`

**Steps:**
- [ ] `PolicyNode` carries every property `PLAN-MISSION-5.md` §3 5.A row 1 lists: stable node key,
      version reference, `node_type`, `title`/`purpose`/`owner`, `execution_mode`, `input_contract`/
      `output_contract` (typed field-name→type-string maps), `preconditions`, `evidence_requirements`,
      `timeout_seconds`, `retry_policy`, `fallback_node_key`, `reason_codes`, `required_role`,
      `financial_impact`/`legal_impact` (bool), `model_or_policy_dependency`, `test_cases`,
      `monitoring_metrics`. `__post_init__` rejects an `ml`/`hybrid` `node_type` (FR-ALG-08 — recorded
      as this task's own enforcement point, not 5.B's, since it's a pure model-layer check).
- [ ] `can_transition(from_status, to_status)` implements: `draft→simulation`; `simulation→
      business_review`; `simulation→rejected`; `business_review→risk_review`; `business_review→
      rejected`; `risk_review→approved`; `risk_review→rejected`; `approved→active`; `active→retired`;
      `active→suspended`; `suspended→active`; `suspended→retired`. No other pair is allowed.

## Task 3: `packages/algorithm/policy_store.py`

**Files:**
- Create: `packages/algorithm/policy_store.py`
- Create: `tests/integration/test_policy_store.py`

**Steps:**
- [ ] `create_policy_graph`, `create_draft_version` (first version of a graph, status `draft`),
      `add_nodes`/`add_edges` (reject if target version's status is in `IMMUTABLE_STATUSES` — the
      structural immutability guard from Global Constraints), `fork_new_draft_version` (copy an
      existing version's nodes/edges into a new `draft` version row referencing the same graph),
      `transition_version_status` (validates via `can_transition`, updates `policy_versions.status`,
      inserts one `policy_version_transitions` row — never skips the log), `get_version_with_graph`
      (nodes+edges for one version), `list_versions_by_graph`.
- [ ] Real regression test: attempting `add_nodes` against an `approved`/`active` version raises,
      proving content immutability structurally, not just by convention (mirrors 5.E's own exit-gate
      criterion, proven early rather than deferred).

## Task 4: `packages/algorithm/research_dossier_model.py` + `research_dossier_store.py` + ADR

**Files:**
- Create: `packages/algorithm/research_dossier_model.py` (`ResearchDossier` dataclass — every field
  `PLAN-MISSION-5.md` §3 5.A row 3 lists: decision statement, owners, approvers, source register,
  assumptions, data dictionary, formula/decision table, coefficients+rationale, validation design, test
  dataset manifest, results/limitations, fairness analysis (nullable — "где применимо"), security/
  privacy analysis, approval/effective dates, monitoring/retirement criteria)
- Create: `packages/algorithm/research_dossier_store.py`
- Update: `migrations/0018_algoritm_policy_graph.sql` (add `research_dossiers` table + nullable
  `policy_versions.research_dossier_id` FK — the *link* exists so 5.B's compiler can later check "does
  this financial-impact version have one," but this task enforces nothing)
- Create: `docs/adr/0007-algorithm-research-dossier-schema.md` (ADR recording *why* this shape — ties
  directly to `master plan §13.3`'s dossier requirements and `FR-ALG-20`/`FR-ALG-21`)
- Create: `tests/unit/test_research_dossier_model.py`, `tests/integration/test_research_dossier_store.py`

**Steps:**
- [ ] Write the ADR using this repo's existing ADR format (see `docs/adr/0005-authority-model.md` as a
      length/style reference) — the decision is "this schema shape, sourced from master plan §13.3,
      with these fields and this nullable-dossier-link design," not a novel formula decision.
- [ ] `fairness_analysis` is the one nullable content field (dossier's own "где применимо" qualifier) —
      every other field is required, since a dossier missing e.g. its source register is not a real
      dossier (same "no silent fallback" discipline, hard ban #3, applied to a research artifact rather
      than a data fact).

## Task 5: `packages/algorithm/official_source_registry_model.py` + `_store.py`

**Files:**
- Update: `migrations/0018_algoritm_policy_graph.sql` (add `official_sources` table)
- Create: `packages/algorithm/official_source_registry_model.py` (`OfficialSource` dataclass;
  `SOURCE_TYPES = ("law", "fx_rate", "vat_rate", "price_index")`)
- Create: `packages/algorithm/official_source_registry_store.py` (`store_official_source`,
  `get_effective_source` — "as of" query: latest row where `effective_from <= as_of` and
  (`effective_to IS NULL OR effective_to > as_of`), `list_sources_by_type`)
- Create: `tests/unit/test_official_source_registry_model.py`,
  `tests/integration/test_official_source_registry_store.py`

**Steps:**
- [ ] Append-only (no update/delete function) — a superseded rate is a new row with its own
      `effective_from`, never an edit of the old row (same discipline as `overhead_buffer_contributions`
      and every other fact table in this codebase).
- [ ] Test fixtures use obviously-synthetic values (e.g. a fabricated law citation string, a round
      test-only FX number) — never presented as, or resembling, a real current AZN rate/VAT percentage,
      so nothing in this task could be mistaken for real financial data later.

## Task 6: close-out

**Steps:**
- [ ] Full gate (`pytest -m "not live_network"`, `ruff format --check`, `ruff check`, `mypy`,
      `check_v1_untouched.py`) green.
- [ ] `docs/reports/WORKLOG.md` entry (this task's summary) + `docs/decisions/OPEN-QUESTIONS.md` entry
      recording: the lifecycle-transition-table modeling choice (Global Constraints above), the
      FR-ALG-08 enforcement being pulled into 5.A's model layer rather than left purely to 5.B, and the
      explicit list of what 5.B-5.E still owe (compiler/validator, ALG-RESEARCH gate enforcement,
      simulation, frontend, full exit-gate QA).

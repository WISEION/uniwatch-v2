-- АЛГОРИТМ page: simulation/backtest run persistence (Phase 5, task 5.C,
-- docs/reports/PLAN-MISSION-5.md Section3 task 5.C / master plan
-- Section12.7, Section14.5's own "algorithm_simulation_runs" name).
--
-- This is the first table anything in this codebase writes as a record of
-- actually RUNNING a policy graph against a case -- 5.A built the graph
-- container, 5.B built the gates that let a version progress through its
-- lifecycle, neither ever executed one. A run row is itself immutable
-- historical evidence (no update/delete function exists in
-- packages/algorithm/simulation_store.py for this table, same discipline
-- policy_nodes/policy_edges already use) -- what a version did against a
-- given case set at a given time does not get edited after the fact.
--
-- case_traces stores either a per-case CaseTrace array (case_source in
-- 'synthetic_vendor'/'frozen_real_tender'/'historical_outcome') or a
-- per-case VersionComparison array (case_source = 'mixed', a
-- {"kind": "comparison", ...} marker inside each element distinguishes it)
-- -- one jsonb column, not two tables, since these are audit/reporting
-- records read back as a whole, not queried relationally per-case
-- elsewhere (same "structural placeholder" posture 5.A/5.B already used
-- for policy_nodes.test_cases).
--
-- monetary_range is NULL when no case in the run carried a
-- monetary_amount+monetary_currency pair -- never a fabricated zero range.
-- Amounts are never summed across currencies (packages/decision/matching.py
-- already applies this discipline; D-TAX forbids inventing an FX rate to
-- collapse them into one).
CREATE TABLE algorithm_simulation_runs (
    id BIGSERIAL PRIMARY KEY,
    policy_version_id BIGINT NOT NULL REFERENCES policy_versions (id),
    compared_against_version_id BIGINT REFERENCES policy_versions (id),
    case_set_label TEXT NOT NULL,
    case_source TEXT NOT NULL CHECK (
        case_source IN ('synthetic_vendor', 'frozen_real_tender', 'historical_outcome', 'mixed')
    ),
    case_count INTEGER NOT NULL,
    completed_count INTEGER NOT NULL,
    awaiting_human_count INTEGER NOT NULL,
    undetermined_count INTEGER NOT NULL,
    terminal_distribution JSONB NOT NULL,
    reason_code_distribution JSONB NOT NULL,
    subgroup_distribution JSONB,
    monetary_range JSONB,
    monetary_amount_uncurrencied_count INTEGER NOT NULL DEFAULT 0,
    case_traces JSONB NOT NULL,
    run_by TEXT NOT NULL,
    run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes TEXT
);

CREATE INDEX algorithm_simulation_runs_version_idx ON algorithm_simulation_runs (policy_version_id);

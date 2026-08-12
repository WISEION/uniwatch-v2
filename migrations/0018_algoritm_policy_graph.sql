-- АЛГОРИТМ page: policy-graph domain schema (Phase 5, task 5.A,
-- docs/reports/PLAN-MISSION-5.md Section3 task 5.A). packages/algorithm's
-- first schema -- prior to this migration, packages/algorithm has no
-- tables at all.
--
-- This migration builds the CONTAINER a real, versionable Human/Rule/Gate/
-- Data-Quality policy graph lives in. It does not build the compiler/
-- validator (unreachable-node/cycle detection, branch coverage, the
-- ALG-RESEARCH gate's enforcement -- all Phase 5, task 5.B), the
-- simulation engine (5.C), or the frontend (5.D). It seeds zero rows and
-- invents zero coefficients/weights/thresholds -- D-FIN and TBD-04
-- (candidate algorithm A-E formulas) remain exactly as unresolved as
-- before this migration.

-- One named policy (e.g. "Bid/No-Bid -- Water Infrastructure"). Versions
-- below are what actually carry content; this row is just the stable
-- identity multiple versions share over time.
CREATE TABLE policy_graphs (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    owner TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Lifecycle per PLAN-MISSION-5.md Section3: "draft -> simulation ->
-- business_review -> risk_review -> approved -> active -> retired", with
-- rejected/suspended branches. The exact transition graph is fixed in
-- packages/algorithm/policy_lifecycle.py, not enforced by this CHECK --
-- the CHECK only bounds the set of valid values, the same split every
-- other status column in this codebase uses (e.g. tender_outcomes.outcome).
--
-- approved/active versions are content-immutable (FR-ALG-11): no store
-- function in packages/algorithm issues UPDATE/DELETE against a version's
-- own policy_nodes/policy_edges once it reaches either status -- the only
-- way to change content is fork_new_draft_version(), which creates a NEW
-- row here.
CREATE TABLE policy_versions (
    id BIGSERIAL PRIMARY KEY,
    policy_graph_id BIGINT NOT NULL REFERENCES policy_graphs (id),
    version_number INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'draft', 'simulation', 'business_review', 'risk_review',
            'approved', 'active', 'retired', 'rejected', 'suspended'
        )
    ),
    -- Nullable: a version need not have a research dossier unless/until
    -- it carries a financial-impact node -- 5.B's compiler is what will
    -- eventually require this when financial_impact is true, not this
    -- migration or packages/algorithm/policy_store.py.
    research_dossier_id BIGINT,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (policy_graph_id, version_number)
);

CREATE INDEX policy_versions_graph_idx ON policy_versions (policy_graph_id);

-- Append-only transition log -- "журнал переходов сохраняется" (5.B/5.E's
-- kill-switch/rollback rehearsal requirements read this; this migration
-- only makes sure there is real history for them to read once built).
CREATE TABLE policy_version_transitions (
    id BIGSERIAL PRIMARY KEY,
    policy_version_id BIGINT NOT NULL REFERENCES policy_versions (id),
    from_status TEXT NOT NULL,
    to_status TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason TEXT
);

CREATE INDEX policy_version_transitions_version_idx ON policy_version_transitions (policy_version_id);

-- One node's full property set, per PLAN-MISSION-5.md Section3 task 5.A
-- row 1. node_key is stable WITHIN one policy_graph across versions (so a
-- diff between two versions of the same graph can say "this is the same
-- node, changed" rather than "a new node replaced an old one") -- it is
-- NOT globally unique, hence the composite lookup index rather than a
-- standalone UNIQUE.
--
-- ml/hybrid node_type values are representable here (so a later phase
-- never needs a schema migration to add them, per FR-ALG-08) but
-- packages/algorithm/policy_model.py's PolicyNode.__post_init__ rejects
-- constructing one in this task -- there is no compiler yet to gate
-- activation, so the model layer is this task's own enforcement point.
CREATE TABLE policy_nodes (
    id BIGSERIAL PRIMARY KEY,
    policy_version_id BIGINT NOT NULL REFERENCES policy_versions (id),
    node_key TEXT NOT NULL,
    node_type TEXT NOT NULL CHECK (
        node_type IN ('human', 'rule', 'gate', 'data_quality', 'ml', 'hybrid')
    ),
    title TEXT NOT NULL,
    purpose TEXT NOT NULL,
    owner TEXT NOT NULL,
    execution_mode TEXT NOT NULL,
    input_contract JSONB NOT NULL,
    output_contract JSONB NOT NULL,
    preconditions JSONB NOT NULL,
    evidence_requirements JSONB NOT NULL,
    timeout_seconds INTEGER,
    retry_policy JSONB,
    fallback_node_key TEXT,
    reason_codes JSONB NOT NULL,
    required_role TEXT,
    financial_impact BOOLEAN NOT NULL DEFAULT false,
    legal_impact BOOLEAN NOT NULL DEFAULT false,
    model_or_policy_dependency TEXT,
    test_cases JSONB NOT NULL,
    monitoring_metrics JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (policy_version_id, node_key)
);

CREATE INDEX policy_nodes_version_idx ON policy_nodes (policy_version_id);

-- Minimal graph edges -- from one node to another within the same version,
-- with an optional condition label (e.g. a Rule node's branch outcome).
-- Real cycle/unreachable-node detection over this shape is task 5.B's
-- compiler/validator, not built here.
CREATE TABLE policy_edges (
    id BIGSERIAL PRIMARY KEY,
    policy_version_id BIGINT NOT NULL REFERENCES policy_versions (id),
    from_node_key TEXT NOT NULL,
    to_node_key TEXT NOT NULL,
    condition_label TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX policy_edges_version_idx ON policy_edges (policy_version_id);

-- Research dossier schema per PLAN-MISSION-5.md Section3 task 5.A row 3 /
-- master plan Section13.3 -- see docs/adr/0007-algorithm-research-dossier-schema.md
-- for the ADR recording why this shape. fairness_analysis is the one
-- nullable content field ("где применимо" -- not every policy has a
-- fairness dimension); every other field is required, since a dossier
-- missing e.g. its source register is not a real dossier.
CREATE TABLE research_dossiers (
    id BIGSERIAL PRIMARY KEY,
    decision_statement TEXT NOT NULL,
    owners JSONB NOT NULL,
    approvers JSONB NOT NULL,
    source_register JSONB NOT NULL,
    assumptions JSONB NOT NULL,
    data_dictionary JSONB NOT NULL,
    formula_or_decision_table JSONB NOT NULL,
    coefficients_and_rationale JSONB NOT NULL,
    validation_design JSONB NOT NULL,
    test_dataset_manifest JSONB NOT NULL,
    results_and_limitations JSONB NOT NULL,
    fairness_analysis JSONB,
    security_privacy_analysis JSONB NOT NULL,
    approved_at TIMESTAMPTZ,
    effective_from TIMESTAMPTZ,
    monitoring_criteria JSONB NOT NULL,
    retirement_criteria JSONB NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE policy_versions
    ADD CONSTRAINT policy_versions_research_dossier_fk
    FOREIGN KEY (research_dossier_id) REFERENCES research_dossiers (id);

-- Registry of official sources (law, FX rate, VAT rate, price index) with
-- effective dates -- PLAN-MISSION-5.md Section3 task 5.A row 4 (FR-ALG-23).
-- Append-only: a superseded rate is a new row with its own effective_from,
-- never an edit of the old row (same discipline as
-- overhead_buffer_contributions). This migration seeds zero rows --
-- inventing a real law citation, FX rate, or VAT percentage here would
-- violate AGENTS.md hard ban #2 exactly as much as inventing one in
-- application code would.
CREATE TABLE official_sources (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL CHECK (
        source_type IN ('law', 'fx_rate', 'vat_rate', 'price_index')
    ),
    name TEXT NOT NULL,
    citation TEXT NOT NULL,
    value TEXT NOT NULL,
    effective_from TIMESTAMPTZ NOT NULL,
    effective_to TIMESTAMPTZ,
    entered_by TEXT NOT NULL,
    entered_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX official_sources_type_effective_idx ON official_sources (source_type, effective_from);

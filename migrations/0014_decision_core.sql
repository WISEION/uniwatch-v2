-- Decision Core (Phase 4, task 4.A, TENDER_INTELLIGENCE_SPEC.md §7.1):
-- human Go/No-Go inputs, the one real derived Bid/No-Bid signal (BOQ money
-- coverage + single-vendor-critical lines), the append-only human Decision
-- record (ADR-0003 layer 4, ADR-0005: human authority is final and
-- exclusive), and INV-20's lock-in flagging for single-vendor-critical
-- BOQ lines on a Bid/Conditional Bid decision. Every table references the
-- real `tenders` identity (ADR-0001) -- no free-text tender identifier is
-- introduced alongside it.

CREATE TABLE go_no_go_inputs (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    company_profile_notes TEXT NOT NULL,
    qualification_notes TEXT NOT NULL,
    financing_notes TEXT NOT NULL,
    customer_reputation_notes TEXT NOT NULL,
    pre_designated_winner_suspected BOOLEAN NOT NULL,
    entered_by TEXT NOT NULL,
    entered_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE bid_readiness_candidates (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    green_amount NUMERIC NOT NULL,
    yellow_amount NUMERIC NOT NULL,
    red_amount NUMERIC NOT NULL,
    unpriced_line_count INTEGER NOT NULL,
    non_matchable_line_count INTEGER NOT NULL,
    non_matchable_amount NUMERIC NOT NULL,
    total_priced_amount NUMERIC NOT NULL,
    green_pct DOUBLE PRECISION NOT NULL,
    yellow_pct DOUBLE PRECISION NOT NULL,
    red_pct DOUBLE PRECISION NOT NULL,
    is_lottery BOOLEAN NOT NULL,
    critical_lines JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL
);

-- Append-only (ADR-0003 layer 4, ADR-0005): application code never issues
-- an UPDATE/DELETE against this table. A later reversal (P316's
-- Conditional Bid auto-transitioning to No-Bid) is a new row.
CREATE TABLE decisions (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    decision_type TEXT NOT NULL CHECK (decision_type IN ('go', 'no_go', 'bid', 'no_bid', 'conditional_bid')),
    conditions JSONB NOT NULL,
    deadline TIMESTAMPTZ,
    justification TEXT NOT NULL,
    actor TEXT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL,
    go_no_go_inputs_id BIGINT REFERENCES go_no_go_inputs (id),
    bid_readiness_candidate_id BIGINT REFERENCES bid_readiness_candidates (id)
);

-- INV-20 lock-in: auto-generated when a Bid/Conditional Bid decision names
-- a single-vendor-critical BOQ line. Only identification/flagging is built
-- here -- actual LOI/pre-order document generation is out of scope
-- (docs/decisions/OPEN-QUESTIONS.md).
CREATE TABLE lock_in_requirements (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    decision_id BIGINT NOT NULL REFERENCES decisions (id),
    boqline_source_line_id BIGINT NOT NULL,
    vendor_id BIGINT NOT NULL,
    vendor_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'locked', 'expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX lock_in_requirements_tender_idx ON lock_in_requirements (tender_id);

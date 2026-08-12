-- Calibration loop measurement substrate (Phase 4, task 4.D,
-- TENDER_INTELLIGENCE_SPEC.md Section7.4, P319).
--
-- This migration deliberately adds NO weight, coefficient, TTL, or
-- probability column. Section7.4's actual calibration outputs remain
-- blocked on TBD-TIS-02 (signal weights, confidence tiers) and TBD-TIS-01
-- (numeric TTL per fact class); inventing either would violate AGENTS.md
-- hard ban #2. What this migration adds is the record of WHAT ACTUALLY
-- HAPPENED, which is the missing input those decisions are blocked on --
-- nothing in this codebase has ever stored a tender outcome.
--
-- All four tables are append-only: application code issues no UPDATE or
-- DELETE against them (same discipline as execution_facts / decisions).
-- A correction is a new row, never an edit.

-- Public outcome of a tender, entered by a human. There is no connector:
-- no eTender award/result endpoint has been captured, and the events-list
-- resource carries no monetary field at all (fixtures/tender-snapshots/
-- etender/MANIFEST.md) -- so a human who has seen the public award enters
-- it, same zero-entry-threshold discipline as INV-18's napkin ingestion.
--
-- our_submitted_amount is the first place in this codebase to store OUR
-- OWN price. decisions (0014) records type/conditions/deadline/
-- justification with no amount, so "winner price vs us" previously had
-- neither operand.
--
-- Amounts are NUMERIC and nullable: a `won` outcome needs no winner
-- fields, and a human may know the winner's name but not their price
-- (MANIFEST.md records the public list resource exposes the winner's name
-- and VOEN but no money). A missing amount stays NULL and is surfaced as
-- missing downstream -- never coerced to 0 (hard ban #3).
CREATE TABLE tender_outcomes (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    outcome TEXT NOT NULL CHECK (outcome IN ('won', 'lost', 'cancelled')),
    our_submitted_amount NUMERIC,
    winner_name TEXT,
    winner_amount NUMERIC,
    currency TEXT,
    announced_at TIMESTAMPTZ,
    -- INV-15/INV-16: free text naming where the human saw this outcome.
    -- Not a raw_snapshot reference: nothing fetched it.
    source_ref TEXT NOT NULL,
    entered_by TEXT NOT NULL,
    entered_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One outcome per tender. Append-only means a correction is a new row, so
-- this is a partial unique index rather than a plain UNIQUE: it lets the
-- route reject a duplicate loudly (409) instead of silently accumulating
-- two contradictory outcomes for one tender.
CREATE UNIQUE INDEX tender_outcomes_tender_uniq ON tender_outcomes (tender_id);

-- Section7.4's "разбор проигрышей" -- the spec calls it the single most
-- informative artifact. The first three loss_reason values are the spec's
-- own verbatim categories; 'other' exists so a real cause outside them is
-- never misfiled (the route enforces a non-empty note for it).
--
-- A separate table, not a column on tender_outcomes: a loss can have more
-- than one contributing cause, and each carries its own note and author.
CREATE TABLE tender_loss_reasons (
    id BIGSERIAL PRIMARY KEY,
    tender_outcome_id BIGINT NOT NULL REFERENCES tender_outcomes (id),
    loss_reason TEXT NOT NULL CHECK (
        loss_reason IN ('competitor_cheap_access', 'dumping', 'drawn_tender', 'other')
    ),
    note TEXT NOT NULL,
    entered_by TEXT NOT NULL,
    entered_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX tender_loss_reasons_outcome_idx ON tender_loss_reasons (tender_outcome_id);

-- Persisted forecast card (task 2.C/2.D built ForecastCard as a pure
-- in-memory assembly -- packages/tender/forecast_card.py -- computed on
-- demand and discarded, so no forecast has ever been retained). Without
-- retention, spec Section5.3/P310's ">=30 already-published tenders"
-- backtest is impossible, and that backtest is exactly what TBD-TIS-02 is
-- blocked on. This table starts the retention; it computes nothing.
--
-- Columns mirror ForecastCard's own fields verbatim. is_composite is
-- stored even though build_forecast_card only ever returns a card when it
-- is True: the snapshot must remain self-describing if that gate ever
-- changes (it is currently an honest stand-in for P311's uncalibrated
-- >=50% threshold).
CREATE TABLE forecast_card_snapshots (
    id BIGSERIAL PRIMARY KEY,
    object_region TEXT NOT NULL,
    is_composite BOOLEAN NOT NULL,
    signal_types JSONB NOT NULL,
    budget_estimate JSONB,
    evidence_chain JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX forecast_card_snapshots_region_idx ON forecast_card_snapshots (object_region);

-- Human-confirmed "this published tender is the one that forecast
-- predicted". Deliberately NOT auto-matched: no source document supplies a
-- forecast-to-tender identity algorithm, and the one identity helper that
-- exists (packages/tender/az_region_identity.py) canonicalizes only the
-- four regions actually observed in captured data, returning None
-- otherwise. Guessing the link would fabricate the very fact the P310
-- backtest is meant to measure. A human confirms it -- same ADR-0005
-- discipline the rest of this codebase applies wherever an algorithm would
-- have to be invented.
CREATE TABLE forecast_card_tender_links (
    id BIGSERIAL PRIMARY KEY,
    forecast_card_snapshot_id BIGINT NOT NULL REFERENCES forecast_card_snapshots (id),
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    note TEXT NOT NULL,
    confirmed_by TEXT NOT NULL,
    confirmed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (forecast_card_snapshot_id, tender_id)
);

CREATE INDEX forecast_card_tender_links_tender_idx ON forecast_card_tender_links (tender_id);

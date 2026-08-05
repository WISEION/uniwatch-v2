-- Vendor synthetic sandbox (TENDER_INTELLIGENCE_SPEC.md §6.1, FR-VND-01,
-- FR-VND-02, FR-VND-05, ADR-0004): the domain model for supply-side
-- offers, with data_realm/watermark as first-class, DB-constrained
-- columns from this table's first migration -- adding this dimension
-- later would need a backfill on data that must never mix realms
-- (ADR-0004's own stated risk). Only 'vendor-sandbox'/'SYNTHETIC' rows
-- are ever written by this phase's code (packages/vendor/synthetic_provider.py) --
-- 'vendor-production'/'REAL' exists in the CHECK constraint now so the
-- schema does not need a breaking change when real vendor onboarding
-- (a separate legal/privacy/security gate, out of this task's scope)
-- eventually needs it.

CREATE TABLE vendors (
    id BIGSERIAL PRIMARY KEY,
    data_realm TEXT NOT NULL CHECK (data_realm IN ('vendor-sandbox', 'vendor-production')),
    watermark TEXT NOT NULL CHECK (watermark IN ('SYNTHETIC', 'REAL')),
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    seed INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (data_realm = 'vendor-sandbox' AND watermark = 'SYNTHETIC')
        OR (data_realm = 'vendor-production' AND watermark = 'REAL')
    )
);

CREATE TABLE vendor_offers (
    id BIGSERIAL PRIMARY KEY,
    vendor_id BIGINT NOT NULL REFERENCES vendors (id),
    data_realm TEXT NOT NULL CHECK (data_realm IN ('vendor-sandbox', 'vendor-production')),
    watermark TEXT NOT NULL CHECK (watermark IN ('SYNTHETIC', 'REAL')),
    material TEXT NOT NULL,
    price NUMERIC NOT NULL,
    currency TEXT NOT NULL,
    vat_rate NUMERIC NOT NULL,
    uom TEXT NOT NULL,
    -- FR-VND-05 "UOM и конверсии": the offer's quantity expressed in a
    -- canonical unit, same intent as task 2.A's line-level UOM canonicalization.
    uom_canonical_qty NUMERIC NOT NULL,
    moq NUMERIC NOT NULL,
    capacity NUMERIC NOT NULL,
    inventory NUMERIC NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL,
    evidence_source TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    -- NULL for a normal offer; a label (e.g. 'stale_offer', 'moq_conflict')
    -- for one of FR-VND-03's adverse cases -- never hidden, always tagged.
    adverse_case TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (data_realm = 'vendor-sandbox' AND watermark = 'SYNTHETIC')
        OR (data_realm = 'vendor-production' AND watermark = 'REAL')
    )
);

CREATE INDEX vendor_offers_vendor_id_idx ON vendor_offers (vendor_id);
CREATE INDEX vendor_offers_data_realm_idx ON vendor_offers (data_realm);

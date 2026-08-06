-- Reputation layer -- SCG's fourth layer (TENDER_INTELLIGENCE_SPEC.md
-- Section6.2, task 3.B, INV-19). Same explicit data_realm/watermark
-- discipline as migrations/0009_vendor_sandbox.sql -- only
-- 'vendor-sandbox'/'SYNTHETIC' rows are ever written by this task's code
-- (packages/vendor/synthetic_reputation.py); 'vendor-production'/'REAL'
-- exists in the CHECK constraint so the schema does not need a breaking
-- change once real onboarding (a separate legal/privacy/security gate,
-- out of this task's scope) needs it.

CREATE TABLE vendor_reputation_facts (
    id BIGSERIAL PRIMARY KEY,
    vendor_id BIGINT NOT NULL REFERENCES vendors (id),
    data_realm TEXT NOT NULL CHECK (data_realm IN ('vendor-sandbox', 'vendor-production')),
    watermark TEXT NOT NULL CHECK (watermark IN ('SYNTHETIC', 'REAL')),
    event_type TEXT NOT NULL,
    project_ref TEXT,
    source_ref TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    ttl_days INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (data_realm = 'vendor-sandbox' AND watermark = 'SYNTHETIC')
        OR (data_realm = 'vendor-production' AND watermark = 'REAL')
    )
);

CREATE INDEX vendor_reputation_facts_vendor_id_idx ON vendor_reputation_facts (vendor_id);

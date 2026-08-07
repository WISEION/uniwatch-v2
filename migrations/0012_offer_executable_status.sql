-- Executable Availability (TENDER_INTELLIGENCE_SPEC.md §6.3, task 3.C,
-- P314): the raw, vendor-declared/source-observed availability tier for
-- an offer -- 'reserved' (legally locked volume+price) > 'confirmed'
-- (physically confirmed, not locked) > 'reported' (declared by vendor,
-- unverified) > 'unknown'. See packages/vendor/availability_model.py for
-- the tier ordering and the reputation-weighted effective status derived
-- from this raw column. NOT NULL with no default is safe here, same
-- reasoning as migrations/0010_vendor_api_key.sql: this table has been
-- sandbox-only synthetic data since migration 0009, no real vendor
-- onboarding gate has opened (ADR-0004), so there is no production data
-- an unconditional NOT NULL addition could break.

ALTER TABLE vendor_offers
    ADD COLUMN executable_status TEXT NOT NULL
    CHECK (executable_status IN ('reserved', 'confirmed', 'reported', 'unknown'));

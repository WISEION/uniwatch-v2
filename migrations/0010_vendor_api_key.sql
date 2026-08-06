-- Vendor tenant isolation (FR-VND-09, PRD §5.5/§9.2, INV-08): each vendor
-- gets a server-issued API key, unique, never client-supplied, never
-- omitted. This is the identity apps/api_vendor's new /vendors/me/offers
-- route resolves the caller from -- there is no other per-vendor
-- credential concept in this schema yet. NOT NULL with no default is
-- safe here: this table has been sandbox-only synthetic data since
-- migration 0009 landed, no real vendor onboarding gate has opened
-- (ADR-0004), so there is no production data an unconditional NOT NULL
-- addition could break.

ALTER TABLE vendors ADD COLUMN api_key TEXT NOT NULL UNIQUE;

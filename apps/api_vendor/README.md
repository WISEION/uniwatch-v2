# apps/api_vendor

FastAPI entry point for the **Vendor** service (ADR-0006: Tender and Vendor are separate deployable
processes — see `apps/api_tender` for the other side). Contract-first: OpenAPI is the source of truth
(`FR-PLT-01`). `packages/vendor` has no domain code yet (synthetic-only, pre-legal-gate) — this app is
currently a skeleton plus one proof endpoint (`GET /internal/ping`, see
`docs/adr/0006-tender-vendor-service-separation.md`), not real vendor business logic.

Run: `uvicorn apps.api_vendor.main:app --reload --port 8002`

# apps/api_tender

FastAPI entry point for the **Tender** service (ADR-0006: Tender and Vendor are separate deployable
processes, not one monolith app — see `apps/api_vendor` for the other side). Contract-first: OpenAPI is
the source of truth, strict request/response validation (`FR-PLT-01`). Wires `packages/platform`,
`packages/tender`, etc. to HTTP — no business logic lives here (see
`docs/adr/0001-modular-monolith-boundaries.md`, `docs/adr/0006-tender-vendor-service-separation.md`).

Run: `uvicorn apps.api_tender.main:app --reload --port 8001`

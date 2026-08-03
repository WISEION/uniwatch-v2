# apps/api

FastAPI entry point. Contract-first: OpenAPI is the source of truth, strict request/response validation (`FR-PLT-01`). Wires `packages/platform`, `packages/tender`, etc. to HTTP — no business logic lives here (see `docs/adr/0001-modular-monolith-boundaries.md`).

Not implemented yet — this is task 0.B (backend-core), not 0.A.

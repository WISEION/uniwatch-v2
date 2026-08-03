# packages/contracts

Shared OpenAPI/DTO/schema contracts used across `apps/*` and between `packages/*` when one domain needs data from another (`docs/adr/0001-modular-monolith-boundaries.md`). This is the only sanctioned cross-domain data path — no package imports another domain package's internals directly.

Not implemented yet — first contracts land with 0.B (OpenAPI skeleton) and 1.A (eTender empirical contract).

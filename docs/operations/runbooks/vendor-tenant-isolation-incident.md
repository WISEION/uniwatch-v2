# Runbook: vendor tenant isolation incident

**Trigger:** suspicion that one vendor-side tenant's data was exposed to,
or mutated by, another tenant/caller.

## What to check

`apps/api_vendor` uses a separate API-key mechanism for tenant isolation
(`D-IDP` explicitly does not extend session-based local auth to
`apps/api_vendor` — it has its own mechanism, per task 6.A's WORKLOG
entry). Per `AGENTS.md` §3 and ADR-0006, `packages/tender` never reads
`packages/vendor`'s internal tables directly — all cross-service access
goes through `packages/contracts/vendor_api.py`'s real network contract, so
a genuine isolation breach would show up as data crossing that boundary
incorrectly, not as an in-process leak.

1. Identify the affected API key(s)/tenant(s) and the specific `packages/vendor` records (vendors/offers) potentially exposed.
2. Every `Vendor`/`Offer` instance carries explicit `data_realm`/`watermark` fields (`packages/vendor/vendor_model.py`) — confirm whether the exposed records are `vendor-sandbox`/`SYNTHETIC` (the only realm this codebase currently produces, per ADR-0004) or something else; a `vendor-production`/`REAL` record existing at all would itself be a major finding, since nothing in this codebase produces real vendor data yet.
3. Check `apps/api_vendor/deps.py`'s API-key resolution and `apps/api_vendor/routers/internal.py`/`offers.py` for the actual query path that returned the exposed data — confirm whether tenant scoping was applied correctly in the query itself (missing a `WHERE tenant = ...` clause) versus an API-key validation bypass.
4. Revoke/rotate the affected API key(s) once the mechanism is identified.
5. Record the incident in `docs/reports/WORKLOG.md`, including whether any `REAL`-realm data was involved (which would also implicate the ADR-0004 synthetic/real isolation gate, a much larger issue than a single tenant leak).

## Do not

- Do not assume "it's all synthetic data anyway, low severity" without first confirming the `data_realm`/`watermark` fields on the actually-exposed records — check, don't assume.

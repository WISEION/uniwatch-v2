# tests/

Suite layout matches master plan §21 / CI gates §22 (PRD §9):

| Suite | Gate | Purpose |
|---|---|---|
| `unit/` | Fast | Pure logic, no DB/network |
| `integration/` | Full | Real DB (or test container), real package boundaries |
| `contract/` | Full | OpenAPI/schema contracts, synthetic vs real adapter parity (`docs/adr/0004-synthetic-real-isolation.md`) |
| `state/` | Full | State-machine / invariant tests (cursor/job/decision lifecycles) |
| `security/` | Full | SSRF suite, RBAC matrix, CSRF/session |
| `e2e/` | Full | Browser E2E + a11y |
| `performance/` | Full | Load/latency-sensitive paths |

No tests exist yet in this task (0.A). Regression-test stubs for the 42 mandatory regressions (Appendix A + RN-01..13) are added in task 0.D (qa), each explicitly marked with the phase it becomes mandatory in — see `docs/reports/PLAN-MISSION-1.md` §5. Do not report a stub as a passing regression test.

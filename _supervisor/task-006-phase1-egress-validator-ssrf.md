ЗАДАНИЕ №006 от владельца. Статус: задачи 1.A и 1.B ПРИНЯТЫ (git `c42e012`, `b10bdbb`, `5647440`, `1f09205`). Дополнительно интегрирован `TENDER_INTELLIGENCE_SPEC.md` (git `6b5864e`) — план записи для остатка Phase 1 + Phase 2-4, ID перенумерованы под шкалу PRD.

ВЫПОЛНИ: Phase 1, задачу **1.C** из плана (`docs/reports/PLAN-MISSION-1.md` §3 и `TENDER_INTELLIGENCE_SPEC.md` §4.1) — security, egress validator:

Реализовать `docs/architecture/egress-validator-contract.md` (контракт уже написан в 0.C, не менять):
1. Trusted source registry: `host`/`allowed_schemes`/`status` (`pending_scan`/`trusted`/`revoked`)/`scanner_run_reference`/audit-поля — NFR-SEC-03.
2. Central egress validator: scheme check → registry check (`trusted` only) → resolve (все адреса, не только первый) → IP-range check (loopback/private/link-local/CGNAT/metadata `169.254.169.254`, IPv6-аналоги, `0.0.0.0/8`) → connect к проверенному IP, не повторный hostname-lookup — NFR-SEC-01, NFR-SEC-02, INV-10, P006.
3. Ре-валидация после **каждого** redirect с нуля — не доверие исходному URL.
4. Каждый отказ — типизированное событие с причиной (`scheme_not_allowed`/`host_not_registered`/`address_blocked`/`redirect_target_rejected`), не молчаливый null.
5. SSRF test suite: `P301` (metadata/private заблокирован, залогирован), `P302` (redirect на приватный IP заблокирован на шаге redirect), `P303` (DNS-rebinding: коннект по первому резолвленному IP, ре-резолв не открывает дыру), `P304` (легитимный `etender.gov.az` фетчится успешно, без ложной блокировки — реальный сетевой запрос).

Владелец `packages/platform` (не `packages/tender`) — см. контракт §"Owner package".

Не начинай 1.D (exception queue) — отдельное задание после 1.C.

По завершении: git commit, append в `docs/reports/WORKLOG.md`, остановись.

Используй установленные skills: `tdd`, `verification-before-completion`.

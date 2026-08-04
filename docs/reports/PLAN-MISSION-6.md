# PLAN-MISSION-6 — Phase 6: Controlled pilot / shadow production

**Статус:** ЧЕРНОВИК. Активируется только после GO супервайзера по Exit gate Phase 5 (PLAN-MISSION-5.md).
**Дата:** 2026-08-04
**Приоритет источников:** PRD v1.1 > master plan §22-24, §18 Phase 6 > v1 audit.
**Зависимость:** Exit gate Phase 5 принят (ALGORITHM builder работает с Human/Rule/Gate nodes).

## 0. Подтверждение чтения

- PRD: NFR-REL-01..03, NFR-OPS-01/02, FR-MIG-03 (shadow comparison), D-HOST/D-IDP/D-PILOT/D-SLO (§13.2 — все четыре блокируют именно эту фазу).
- Master plan §22 (release gates 0-5, особенно Gate 3 Release candidate и Gate 4 Production authorization), §23 (observability/SLO/runbooks), §24 (миграция и coexistence с v1: правило параллельной работы, допустимые/запрещённые legacy imports, shadow comparison).

## 1. Дисциплина выполнения

Наследуется из PLAN-MISSION-1 §1. **Ключевое отличие Mission 6:** это первая миссия, где решения блокируют не только qa-задачу в конце, а старт фазы целиком — **D-HOST и D-IDP должны быть отвечены до задачи 6.A**, иначе pilot-инфраструктуру негде разворачивать и некому логиниться. Это единственная миссия плана, которая формально не может начаться без ответа владельца (в отличие от Phase 0-5, где D-* блокировали только под-задачи).

---

## 2. Область Phase 6 (master plan §18)

Результаты: v1 продолжает работать независимо; v2 независимо загружает реальные тендерные данные; определены пилотные пользователи; параллельное сравнение результатов; incident/runbook/backup restore; SLO и alerts; обучение и очередь обратной связи; go-live/rollback decision pack.

Exit gate: нет критических нерешённых потерь данных/security issues; freshness/completeness источника соответствует согласованной цели; restore drill проходит; user acceptance пройден; production deployment утверждён отдельной identity.

---

## 3. Задачи по очереди

### 6.A — architect/ops (первая, блокирующая — требует ответа по D-HOST/D-IDP до старта)

| Задача | Требования |
|---|---|
| Hosting topology по решению D-HOST; deployment pipeline с immutable image digest | NFR-ARC-06 (наследие), D-HOST |
| Identity/auth интеграция по решению D-IDP (Entra/OIDC), включая break-glass процедуру | NFR-SEC-06 (наследие), D-IDP |
| Shadow comparison harness: bounded source/date range, сравнение count/IDs/status/details/BOQ между v1 и v2; классификация расхождений (v1 loss / v2 defect / source drift / expected semantic difference); v2 не пишет обратно в v1 | FR-MIG-03, master plan §24.4 |
| Cutover criteria и rollback plan утверждаются заранее (документ, не код) — rollback оставляет v1 доступной | master plan §24.4 |

### 6.B — backend-core/ops (после 6.A)

| Задача | Требования |
|---|---|
| Gate 3 (Release candidate) wiring: dependency/license/container/SBOM checks, performance baseline, backup/restore drill, operational runbook, release notes, candidate image по immutable digest | master plan §22 Gate 3, NFR-SEC-09 (наследие) |
| Gate 4 (Production authorization) wiring: distinct approver identity, commit↔digest proof, change window/rollback, DB compatibility, kill switches, deployment approval | master plan §22 Gate 4, NFR-REL-03, INV-14 (наследие) |
| Gate 5 (Post-deploy verification): production health/readiness, DB invariants, job/source freshness, critical route smoke по роли, alerts/metrics, явное подтверждение что deployment (не только CI) завершён | master plan §22 Gate 5, NEG-06 (green CI ≠ production deployment) |
| Backup + **проверенный restore**: restore drill — обязательное доказательство для Gate 3 | NFR-REL-01 |

### 6.C — observability (параллельно с 6.B — независимый модуль: dashboards/alerts, не блокирует API)

| Задача | Требования |
|---|---|
| Signals: request latency/error by route; job queue depth/age/attempts/dead letters; source last success/failure/schema drift; tender/document/BOQ completeness; reconciliation mismatches; notification delivery; decision cycle time/overrides; policy/model version usage; model drift/confidence/abstention; DB connections/locks/storage; backup age/restore drill age | master plan §23.1 |
| Runbooks: source schema changed; BOQ reconciliation failed; worker stuck/dead letter; database invariant failed; restore from backup; policy/model kill switch; rollback release; suspected credential/PII incident; vendor tenant isolation incident | NFR-OPS-01, master plan §23.4 |
| Alerts: freshness источников, отказ jobs, нарушение инвариантов, рост exception queue | NFR-OPS-02 |
| SLO категории (без утверждённых чисел — D-SLO/TBD-01/TBD-02 остаются открытыми до load baseline): interactive p95 latency, source freshness window, job start/completion lag, BOQ completeness target, availability, notification delay, RPO/RTO, incident acknowledgment | master plan §23.3, D-SLO |

### 6.D — pilot ops (после 6.A/6.B — требует D-PILOT)

| Задача | Требования |
|---|---|
| Пилотные пользователи и точная permission matrix по решению D-PILOT | D-PILOT, FR-ADM-06 (наследие) |
| Training материалы и очередь обратной связи для пилотных пользователей | master plan §18 Phase 6 результаты |
| Go-live/rollback decision pack: суммирует shadow comparison результаты, restore drill статус, user acceptance, готов к вердикту production authorization | master plan §22 Gate 4 |

### 6.E — security/qa (последняя, закрывает ворота)

| Задача | Требования |
|---|---|
| User acceptance test с пилотными пользователями | master plan §18 Phase 6 exit gate |
| Restore drill test: реальное восстановление из backup, статус зафиксирован | NFR-REL-01 |
| Shadow comparison отчёт: все расхождения классифицированы, критических нерешённых потерь данных нет | FR-MIG-03 |
| Production deployment authorization dry-run: distinct approver identity, commit↔digest proверка проходит | Gate 4 |

---

## 4. Exit gate Phase 6

| Критерий | Требуемое доказательство |
|---|---|
| Нет критических нерешённых потерь данных/security issues | shadow comparison отчёт без открытых critical mismatches |
| Freshness/completeness источника соответствует согласованной цели | SLO dashboard за пилотный период |
| Restore drill проходит | лог restore drill |
| User acceptance пройден | UAT отчёт с пилотными пользователями |
| Production deployment утверждён отдельной identity | Gate 4 лог |

## 5. Открытые вопросы (блокируют старт этой миссии, не отдельные подзадачи)

- **D-HOST** — hosting: локальная сеть / private cloud / public cloud. Без ответа задача 6.A не может выбрать deployment topology.
- **D-IDP** — identity: Entra/OIDC для пилота, break-glass. Без ответа пилотные пользователи не могут логиниться production-способом.
- **D-PILOT** — пилотные пользователи и точная permission matrix. Блокирует 6.D, не 6.A-6.C.
- **D-SLO** — RPO/RTO, freshness и operational SLA (TBD-01, TBD-02). Блокирует финальные числа в 6.C, не саму инфраструктуру мониторинга (категории фиксируются без чисел).

## 6. Трассируемость

Phase 6 не закрывает regression-номера из Приложения A напрямую — это operational/release-gate фаза. Приёмка — exit-gate §4 и NFR-REL/NFR-OPS acceptance из PRD §6.5/§6.6, плюс §9 release gates целиком (Gate 0-5) впервые проходят end-to-end.

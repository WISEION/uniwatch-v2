# PLAN-MISSION-7 — Phase 7: Real vendor onboarding

**Статус:** ЧЕРНОВИК. Активируется только после GO супервайзера по Exit gate Phase 6 (PLAN-MISSION-6.md) **и** после legal/security approval (не технический gate — отдельный процесс вне разработки).
**Дата:** 2026-08-04
**Приоритет источников:** PRD v1.1 > master plan §10.5, §18 Phase 7 > v1 audit.
**Зависимость:** Exit gate Phase 6 принят (production authorization отработан на synthetic/real-tender контуре); юридическое одобрение хранения vendor PII получено (D-PII).

## 0. Подтверждение чтения

- PRD: FR-VND-07..09, NFR-PRV-01..04, D-PII (§13.2 — единственный принципиально не-дефолтный вопрос вместе с частью D-FIN, per uniwatch-v2-project.md memory).
- Master plan §10.5 (реальный onboarding: 10-шаговый порядок), §18 Phase 7 (результаты/exit gate).

## 1. Дисциплина выполнения

Наследуется из PLAN-MISSION-1 §1. **Единственная миссия плана с внешним (не техническим) блокером первого порядка:** задача 7.A не может начаться до того, как юридическая цель обработки PII, retention и access утверждены владельцем/legal — это не «открытый вопрос, который можно обойти стабом», а формальный approval gate NFR-PRV-02 «до onboarding реальных поставщиков». Технические задачи 7.B+ готовятся заранее (adapter уже существует с Phase 3, здесь — реальный perimeter вокруг него), но не активируются до этого approval.

---

## 2. Область Phase 7 (master plan §18)

Результаты: выбранный real provider adapter или vendor portal perimeter; tenant isolation; PII lifecycle; invitation/approval/suspension; evidence validation; ограниченный vendor pilot.

Exit gate: privacy/security/legal approvals получены; vendor не может получить доступ к внутренним tender/decision данным; adapter contract не изменился; synthetic и production метрики остаются раздельными.

---

## 3. Задачи по очереди

### 7.A — legal/privacy gate (первая, блокирующая — внешний approval, не код)

| Задача | Требования |
|---|---|
| Юридическая цель обработки vendor PII, retention период, access policy — утверждены **до** старта технической работы | NFR-PRV-02, D-PII |
| Security review периметра (perimeter review), отдельный от Fast/Full CI gates | FR-VND-08 |
| Correction/export/deletion процедуры и incident procedure реализованы **до** onboarding первого реального поставщика | NFR-PRV-03 |

### 7.B — architect (после 7.A approval)

| Задача | Требования |
|---|---|
| Real provider adapter (CSV/XLSX import, internal ERP/1C adapter, или supplier API/vendor portal submission — выбор конкретной формы за product owner, реализует тот же `VendorProvider` контракт из Phase 3) | FR-VND-04 (наследие), master plan §10.4/§10.5 |
| Tenant isolation ADR: real vendor изолирован на уровне route/service/database от internal tender/decision данных | FR-VND-09, NFR-PRV-04 |
| Onboarding state machine: invitation → identity/tenant isolation → минимальные права → field/evidence validation → human approval → production activation → suspension/revocation/export/deletion | master plan §10.5 (шаги 2-8) |

### 7.C — backend-core (после 7.B)

| Задача | Требования |
|---|---|
| Onboarding Queue UI/API: invitation, approval, suspension — операции с audit trail (наследие FR-ADM-05) | master plan §17.3 (заглушка создана в Mission 3, здесь — реальная реализация) |
| Evidence validation: field/document проверка перед activation | master plan §10.5 шаг 5 |
| Минимальные права по умолчанию для real vendor identity (deny-by-default, наследие FR-ADM-01) | FR-ADM-01, FR-VND-09 |

### 7.D — security/qa (последняя, закрывает ворота)

| Задача | Требования |
|---|---|
| Tenant isolation test: route/service/database — real vendor не может получить доступ к internal tender/decision данным ни при каком запросе | FR-VND-09, NFR-PRV-04 |
| Regression: adapter contract не изменился — тот же `VendorProvider` интерфейс из Phase 3, только новая реализация | FR-VND-04 |
| Regression: synthetic и production vendor метрики остаются раздельными (расширение isolation suite из Mission 3) | FR-VND-06, NEG-04 |
| Ограниченный pilot с малым числом реальных поставщиков — контролируемый, не полный rollout | master plan §18 Phase 7 результаты |

---

## 4. Exit gate Phase 7

| Критерий | Требуемое доказательство |
|---|---|
| Privacy/security/legal approvals получены | ссылка на подписанный approval-документ (вне репозитория кода) |
| Vendor не может получить доступ к внутренним данным | лог tenant isolation теста |
| Adapter contract не изменился | contract test — старая и новая реализация проходят один и тот же suite |
| Synthetic и production метрики остаются раздельными | лог isolation теста (расширение Mission 3) |

## 5. Открытые вопросы

- **D-PII** — vendor PII purpose/retention/access и периметр real onboarding. **Блокирует старт всей миссии**, не только подзадачу.
- Часть **D-FIN**, касающаяся independent approver, может пересекаться с onboarding approval flow, но не обязательна для технического старта 7.B, если approval-роль для onboarding уже назначена отдельно (per uniwatch-v2-project.md: приглашения поставщиков — предложенный default `procurement_manager`, но это предложение 0.21.1, не финальное решение для v2).

## 6. Трассируемость

Phase 7 не закрывает regression-номера из Приложения A (real vendor onboarding — новый периметр, не существовавший в v1). Приёмка — exit-gate §4 и FR-VND-07..09/NFR-PRV-01..04 acceptance из PRD §5.5/§6.3.

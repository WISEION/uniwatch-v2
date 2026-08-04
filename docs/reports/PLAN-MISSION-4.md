# PLAN-MISSION-4 — Phase 4: Deterministic Decision Intelligence

**Статус:** ЧЕРНОВИК, **вероятно вытеснен** `TENDER_INTELLIGENCE_SPEC.md` §7 (Phase 4 — Execution Ledger + Decision Core + Calibration), см. `docs/decisions/OPEN-QUESTIONS.md` (2026-08-04). Не удалён — не активируется до явного сравнения с новым документом на старте Phase 4. Активируется только после GO супервайзера по Exit gate Phase 3 (PLAN-MISSION-3.md).
**Дата:** 2026-08-04
**Приоритет источников:** PRD v1.1 > master plan §11, §17.4, §18 Phase 4 > v1 audit.
**Зависимость:** Exit gate Phase 3 принят (два fake vendor provider, synthetic isolation доказана).

## 0. Подтверждение чтения

- PRD: FR-DEC-01..09, FR-AUT-01..06, INV-05/06/07, P005 (final Bid gate — намеренно не закрыт в Mission 1, домен здесь), P120 (input change regression).
- Master plan §11 (Module 3 — Decision Intelligence): 11.2 decision case, 11.3 hard constraints/soft score, 11.4 human decisions, 11.5 финальный инвариант (транзакционная проверка), 11.6 outcomes; §17.4 экраны.

## 1. Дисциплина выполнения

Наследуется из PLAN-MISSION-1 §1. **Критично для этой миссии:** финальный Bid/No-Bid — единственная точка системы, где ошибка напрямую создаёт финансовый/юридический риск. Задача 4.D (финальный инвариант) не может быть сокращена или отложена ради скорости — это единственный P0 без права на «стаб».

---

## 2. Область Phase 4 (master plan §18)

Результаты: decision case и immutable inputs; hard constraints; explainable scoring policy; match/human decision queues; Go/No-Go; review cycles; транзакционный финальный Bid/No-Bid; outcomes schema.

Exit gate: активный No-Go блокирует Bid; устаревший критичный вход инвалидирует case; ни одно human-решение не перезаписывается автоматически; финансовые вычисления имеют research dossier; maker/checker gate работает.

---

## 3. Задачи по очереди

### 4.A — architect (первая, блокирующая)

| Задача | Требования |
|---|---|
| `packages/decision` domain schema: `decision_case` (tender version, project version/context, BOQ import version+completeness, набор vendor offer/inventory/capacity versions, policy graph version, model versions, created by/time/purpose, evaluation runs, reviews/overrides, final decision, outcome-ссылка) | FR-DEC-01, INV-05, master plan §11.2 |
| Отдельные append-only сущности: `match_candidate` (авто) vs `human_match_decision`; `gonogo_decision`; `department_review`; `final_decision`; `decision_override` (причина + полномочие + второе подтверждение при финансовом impact) | master plan §11.4, DM-04 (наследие), INV-01 |
| ADR: изменение критичного входа не переписывает case — создаёт `input_changed` + новый evaluation/review cycle | FR-DEC-04, P120 |

### 4.B — backend-core (после 4.A)

| Задача | Требования |
|---|---|
| Hard constraints engine: eligibility/compliance, обязательная сертификация, география, срок поставки, capacity/quantity, currency/VAT/contract conditions (где обязательны), полнота/свежесть критичных evidence — выполняются **до** soft score, провал исключает предложение независимо от score | FR-DEC-02, master plan §11.3 |
| Soft score: заранее опубликованные критерии, разбор вклада каждого критерия + reason codes; hard constraint не дублируется в weighted score | FR-DEC-03, FR-DEC-09 |
| Replay endpoint: по сохранённым версиям входов система повторяет вычисление и получает тот же результат | FR-DEC-08, G5 PRD |
| Outcome schema: requested vs delivered qty, promised vs actual date, accepted/rejected quality, quoted vs contracted vs invoiced price, cancellation/variation reason, evidence, responsible owner, data confidence | FR-DEC-07, master plan §11.6 |

### 4.C — worker/transaction-core (параллельно с 4.B — независимый модуль до интеграции в 4.D)

| Задача | Требования |
|---|---|
| **Финальный инвариант** — одна DB-транзакция перед записью Bid проверяет: active No-Go (hard stop), незавершённые обязательные reviews, stale/incomplete critical inputs, policy/model approval status, optimistic version, полномочие пользователя, required two-person approval, отсутствие kill switch | FR-DEC-05, FR-DEC-06, FR-AUT-04, INV-06, master plan §11.5, P005 |
| Override активного No-Go — только через отдельный maker/checker flow с обязательной причиной и evidence, фиксируются обе identity | FR-AUT-04 |
| UI никогда не единственный контроль — все проверки §11.5 дублируются на сервере независимо от frontend state | INV-06 |

### 4.D — frontend (после 4.B/4.C дают контракт)

| Задача | Требования |
|---|---|
| Экраны: Decision Queue, Match Explorer, Go/No-Go, Review Cycle, Bid/No-Bid, Portfolio/Outcomes (§17.4) | master plan §17.4 |
| «Почему такой результат» — explainability UI с трассировкой hard constraints → soft score → reason codes | FR-DEC-03 |
| Match candidate UI: явное различение auto-candidate vs human decision (наследие FR-TND-08 паттерна из Mission 2, применено к vendor-match) | INV-01, INV-07 |

### 4.E — security/qa (последняя, закрывает ворота)

| Задача | Требования |
|---|---|
| P005 regression: активный No-Go → попытка Bid → hard stop без override; override только через maker/checker с двумя identity | P005, FR-DEC-06 |
| P120 regression: изменение критичного входа создаёт новый evaluation/review cycle, не переписывает существующий case | P120, FR-DEC-04 |
| Replay test: одно и то же прошлое решение, повторно вычисленное по сохранённым версиям, даёт тот же результат | FR-DEC-08, G5 |
| Maker/checker test: активация невозможна одной identity дважды (designer ≠ activator) | FR-AUT-02 |

---

## 4bis. Exit gate Phase 4

| Критерий | Требуемое доказательство |
|---|---|
| Активный No-Go блокирует Bid | лог P005 теста |
| Устаревший критичный вход инвалидирует case | лог теста stale/incomplete input → блокировка финального шага |
| Ни одно human-решение не перезаписывается автоматически | лог append-only decision теста |
| Финансовые вычисления имеют research dossier | ссылка на dossier (готовится совместно с Mission 5, если scoring weights финансово значимы — см. §5 ниже) |
| Maker/checker gate работает | лог теста двух разных identity |

## 5. Открытые вопросы

- **D-FIN** (владельцы financial policy, independent approver, правило override No-Go) блокирует Phase 5, но частично касается Mission 4: если soft-score веса в Phase 4 финансово значимы (влияют на выбор поставщика/цену), они требуют ALG-RESEARCH gate уже здесь, а не только в Phase 5. Решение: scoring в Mission 4 стартует с **явно помеченными не-финальными weights** (TBD-04), полный ALG-RESEARCH dossier — предмет Mission 5, где эти веса переносятся в версionируемую policy.
- D-PII (Phase 7) не блокирует эту миссию.

## 6. Трассируемость

Полностью закрывается в Mission 4: **P005**. Продвигается: **P120** (создан в Phase 0 как стаб, здесь получает реальную реализацию). Не входит в эту миссию: P108-P119/P221-P229 domain-specific элементы, относящиеся к UI-фазам, уже закрытым (Mission 2) или ещё не открытым (Mission 5+).

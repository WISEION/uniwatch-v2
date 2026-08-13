# PLAN-MISSION-5 — Phase 5: АЛГОРИТМ — Human + Rule builder

**Статус:** ЧЕРНОВИК, но открытый вопрос ниже **решён**. **Решение владельца** (`docs/decisions/OPEN-QUESTIONS.md`, 2026-08-12, "Owner decision: Phase 5 АЛГОРИТМ builder is still in scope, on top of Decision Core"): Decision Core (§7.1, MDC, Phase 4) не поглощает и не вытесняет эту фазу — версионируемая АЛГОРИТМ-страница (Human/Rule/ML/Gate builder) строится поверх/рядом с уже построенным Decision Core, залоченное решение `docs/CONTEXT.md` остаётся в силе как есть. Как именно уже построенная прямая логика 4.A (`go_no_go_inputs`/`decisions`, `matching.py`/`boq_summary.py`) соотносится архитектурно с будущим графом (переписывается как Human/Rule-узлы внутри builder'а, остаётся источником данных под ним, или иначе) — первый вопрос самого планирования Phase 5, этой записью не решён. Оригинальный открытый вопрос (см. `docs/decisions/OPEN-QUESTIONS.md`, 2026-08-04) сохранён ниже как исторический контекст. Активируется только после GO супервайзера по Exit gate Phase 4 — **этот GO дан** (`docs/reports/WORKLOG.md`, 2026-08-12, "GO, as-is").

**Исходный (2026-08-04) открытый вопрос, сохранён как исторический контекст:** `TENDER_INTELLIGENCE_SPEC.md` описывает Phase 4 «Decision Core» (§7.1, MDC) напрямую, без явного упоминания отдельной версионируемой АЛГОРИТМ-страницы (Human/Rule/ML/Gate builder) — залоченного решения из `docs/CONTEXT.md`. Не решено, поглощает ли Decision Core эту фазу или строится поверх неё — уточнить у владельца до старта Phase 5, этот файл пока не считается ни подтверждённым, ни вытесненным.
**Дата:** 2026-08-04
**Приоритет источников:** PRD v1.1 > master plan §12, §13, §17.5, §18 Phase 5 > v1 audit.
**Зависимость:** Exit gate Phase 4 принят (decision engine, финальный инвариант, maker/checker доказаны).

## 0. Подтверждение чтения

- PRD: FR-ALG-01..23 (builder, lifecycle, ALG-RESEARCH gate), INV-13/14, D-FIN (§13.2 блокирует эту фазу).
- Master plan §12 (страница АЛГОРИТМ: типы узлов, свойства узла, lifecycle, интерфейс, compiler/validator, simulation/backtest), §13 (правила для финансово значимых алгоритмов: ALG-RESEARCH gate R1-R12, research dossier, 5 candidate algorithms A-E — только каркасы, коэффициенты не утверждены).

## 1. Дисциплина выполнения

Наследуется из PLAN-MISSION-1 §1. **Жёсткое ограничение Phase 5 (FR-ALG-08):** только узлы **Human, Rule, Gate, Data Quality**. Узлы **ML и Hybrid реализуются, но не активируются** до Phase 8 gate — их типы существуют в модели данных (чтобы не переделывать схему), но UI/compiler блокируют activation любой version, содержащей ML/Hybrid node, до отдельного вердикта. Ни один financial policy node не получает `approved` без полного research dossier (R1-R12) — это невозможно сократить сроками.

---

## 2. Область Phase 5 (master plan §18)

Результаты: graph и outline editor; human/rule/gate/data-quality nodes; typed contracts; compiler/validator; тесты/simulation; versioning/approval/activation/rollback; execution trace и explanation; доступная клавиатурная альтернатива.

Exit gate: active policy immutable; невалидный граф не активируется; каждая ветвь протестирована; two-person activation для financial policy; rollback/kill switch отрепетированы.

---

## 3. Задачи по очереди

### 5.A — architect (первая, блокирующая)

| Задача | Требования |
|---|---|
| `packages/algorithm` domain schema: node (stable ID+version, title/purpose/owner, execution mode, typed input/output contract, preconditions, evidence requirements, timeout/SLA, retry/fallback, reason codes, role/permission, financial-impact flag, legal-impact flag, model/policy dependency, test cases, monitoring metrics) | FR-ALG-02, master plan §12.3 |
| Lifecycle state machine: `draft → simulation → business_review → risk_review → approved → active → retired`, с `rejected`/`suspended` ветвями; approved/active immutable, изменение создаёт новую draft | FR-ALG-10, FR-ALG-11, master plan §12.4 |
| ADR: research dossier schema (decision statement, owner/approvers, source register, assumptions, data dictionary, formula/decision table, coefficients+rationale, validation design, test dataset manifest, results/limitations, fairness analysis где применимо, security/privacy analysis, approval/effective dates, monitoring/retirement criteria) | FR-ALG-20, FR-ALG-21, master plan §13.3 |
| Registry официальных источников (закон, FX, VAT, индексы цен) с effective dates | FR-ALG-23 |

### 5.B — backend-core: compiler/validator (после 5.A)

| Задача | Требования |
|---|---|
| Validator: недостижимые узлы, циклы без bounded retry/human exit, несовпадение типов input/output, отсутствие fallback/owner — блокирующие ошибки на этапе редактирования и перед отправкой на approval | FR-ALG-01, FR-ALG-03, master plan §12.6 |
| Branch coverage check: каждая ветвь Rule-узла имеет тестовый случай; непокрытые ветви блокируют approval | FR-ALG-04 |
| Compiler инварианты: все financial nodes имеют research dossier; все ML/Hybrid nodes технически описаны, но помечены **not-activatable-until-Phase-8**; hard constraints не спрятаны в soft weights; все side effects идут только через outbox | FR-ALG-20, FR-ALG-08, master plan §12.6 |
| Kill switch: немедленная остановка новых evaluations по версии; выполняющиеся завершаются определённым образом; журнал переходов сохраняется | FR-ALG-13, FR-ALG-14 |
| Maker/checker activation: financial policy требует двух различных identity, designer не активирует собственную policy | FR-ALG-12, FR-AUT-02 (наследие) |

### 5.C — backend-core: simulation/backtest (параллельно с 5.B — независимый модуль)

| Задача | Требования |
|---|---|
| Simulation engine: synthetic vendor cases (Phase 3), frozen real tender snapshots (Phase 1/2, без изменения источника), historical outcomes (когда появятся из Phase 4), candidate policy vs active policy сравнение | FR-ALG-05, master plan §12.7 |
| Sensitivity analysis: влияние изменения весов/порогов на распределение исходов | FR-ALG-06 |
| Cost/revenue impact range (не ложная точность), false-positive/false-negative review queue, human override rate, rollback rehearsal лог | master plan §12.7 |

### 5.D — frontend (после 5.B даёт контракт)

| Задача | Требования |
|---|---|
| Canvas editor: drag-and-drop, zoom/minimap, node properties panel, validation errors прямо на графе, version diff, simulation panel, approval history, live impact counters, search by node/role/input/reason | master plan §12.5 |
| Outline/табличная доступная альтернатива canvas — полный keyboard-equivalent для move/insert/connect/delete | FR-ALG-07, FR-UX-02 (наследие WCAG 2.2 AA) |
| «Почему принято» с трассировкой пути выполнения (execution trace) | master plan §12.5 |
| Export в human-readable policy PDF/Markdown и machine-readable JSON | master plan §12.5 |

### 5.E — security/qa (последняя, закрывает ворота)

| Задача | Требования |
|---|---|
| Тест: активная/approved версия immutable — попытка редактирования создаёт новую draft, не мутирует существующую | FR-ALG-11 |
| Тест: невалидный граф (недостижимый узел/цикл/несовпадение типов/нет fallback/owner) не может быть отправлен на approval | FR-ALG-03 |
| Тест: непокрытая ветвь блокирует approval | FR-ALG-04 |
| Тест: financial policy активация требует двух разных identity | FR-ALG-12, FR-AUT-02 |
| Rollback rehearsal: откат к предыдущей approved версии восстанавливает поведение, журнал переходов виден | FR-ALG-14 |
| Kill switch rehearsal: активация останавливает новые evaluations, не разрушая journal/audit | FR-ALG-13 |
| Accessibility: клавиатурная alternative проходит критические flows (WCAG 2.2 AA) | FR-UX-02 |

---

## 4. ALG-RESEARCH gate — обязательное условие для первой financial policy version

Ни одна версия policy с financial-impact flag не получает `approved`, пока не пройдены R1-R12 (master plan §13.2) и не заполнен dossier §13.3. Candidate algorithms A-E (Tender Opportunity Priority, Bid/No-Bid support, Vendor Eligibility+Value Ranking, Price/delivery risk, ML matching/ranking) существуют в master plan **только как каркасы формул** — коэффициенты, пороги и веса не утверждены этим планом и не подставляются кодом по умолчанию (TBD-04). Первая реальная financial policy, прошедшая через builder, требует отдельного deep-research задания до её `approved` статуса — это не входит в объём задач 5.A-5.E выше (те строят механизм, не утверждают конкретную policy).

## 5. Exit gate Phase 5

| Критерий | Требуемое доказательство |
|---|---|
| Active policy immutable | лог теста edit-on-active → создание новой draft |
| Невалидный граф не активируется | лог validator теста на всех классах ошибок §12.6 |
| Каждая ветвь протестирована | branch coverage отчёт |
| Two-person activation для financial policy | лог maker/checker теста |
| Rollback/kill switch отрепетированы | лог rehearsal |

## 6. Открытые вопросы

- **D-FIN** (владельцы financial policy, independent approver, правило override No-Go) — блокирует **активацию** первой реальной financial policy, не блокирует построение builder/compiler/simulation механизма. Должен быть отвечен до того, как какая-либо policy version получит `approved`.

## 7. Трассируемость

Phase 5 не закрывает regression-номера из Приложения A (ALGORITHM — новый домен, не существовавший в v1 в этой форме). Приёмка — exit-gate §5 и FR-ALG-01..23 acceptance из PRD §5.7.

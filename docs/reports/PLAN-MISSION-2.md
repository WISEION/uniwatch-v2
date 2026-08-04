# PLAN-MISSION-2 — Phase 2: Real Tender experience, documents and BOQ

**Статус:** ЧЕРНОВИК, **вероятно вытеснен** `TENDER_INTELLIGENCE_SPEC.md` §5 (Phase 2 — BOQ depth + Forecast layer), см. `docs/decisions/OPEN-QUESTIONS.md` (2026-08-05) — тот документ описывает другое наполнение Phase 2 (BOQ-глубина/signal ingestion/forecast engine, без фронтенда/projects/tender↔project-решений/employee dashboard). Frontend/`apps/web`/P003/P004/employee dashboard из этого файла **пока не имеют подтверждённой фазы** — открытый вопрос владельцу, не решено. Файл не удалён. GO по Exit gate Phase 1 получен (2026-08-05) — Phase 2 стартует по `TENDER_INTELLIGENCE_SPEC.md` §5, не по этому файлу, пока владелец не решит иначе.
**Дата:** 2026-08-04
**Приоритет источников при конфликте:** PRD v1.1 (`0_UNIWatch-v2-PRD-v1.0.md`) > master plan 2026-07-28 §17.2/§18 > v1 audit / release notes.
**Зависимость:** требует принятого Exit gate Phase 0 И Exit gate Phase 1 (P001/P002/P006/P007 зелёные, cursor/exception queue/SSRF доказаны).

## 0. Подтверждение чтения (для этой миссии)

- PRD: FR-TND-01..12, FR-DQ-01..05, FR-UX-01..05, FR-PLT-08, DM-04, INV-01, INV-04; regression P001, P003, P004, P108, P109, P223, P226; §5.4 (M1), §11 (Day-30 demo).
- Master plan: §17.2 (экраны Tender Intelligence), §18 Phase 2 (результаты/exit gate), §7.3 (repo structure — `apps/web` ещё не создан, Phase 0 построил только `apps/{api,worker}`).
- PLAN-MISSION-1.md §5 (трассируемость): P003/P004 **намеренно** не закрыты в Миссии 1 — их домен здесь.

## 1. Дисциплина выполнения

Наследуется из PLAN-MISSION-1 §1 без изменений: один поток, фазы не перекрываются, субагенты — специализация внутри фазы, отклонения фиксируются в `docs/decisions/OPEN-QUESTIONS.md`, TBD-числа не подставляются.

**Дополнительное правило Миссии 2:** `apps/web` — новый apps-модуль, ещё не существует. Задача 2.A (architect) создаёт его скелет первой и блокирует фронтенд-задачи 2.C, как 0.A блокировала 0.B в Миссии 1.

---

## 2. Область Phase 2 (master plan §18)

Результаты: real Tenders/Projects/Signals UI; documents/versioning; полная BOQ-пагинация/reconciliation; человеческие tender↔project решения; deep links/фильтры/version diff; employee-scale dashboard.

Exit gate: BOQ completeness proof; реальный пилотный диапазон reconciled; Reject/Confirm переживают resync; partial data никогда не выглядит complete; browser E2E/accessibility проходят.

---

## 3. Задачи по очереди

### 2.A — architect (первая, блокирующая)

| Задача | Требования |
|---|---|
| Скелет `apps/web`: React/TypeScript, роутинг с адресуемыми сущностями/фильтрами/вкладками, contract-first клиент к OpenAPI из Phase 0 | FR-PLT-08, NFR-ARC-05 |
| i18n-каркас (без выбора итогового языка — D-LANG остаётся открытым): строки не хардкодятся, минимум один locale bundle для разработки | FR-UX-05 |
| ADR: frontend state/data-fetching approach, deep-link URL schema (entity/filter/tab → URL, reload/share восстанавливают состояние) | FR-PLT-08, P223 |

### 2.B — backend-core (после 2.A, параллельно с 2.C по разным `apps/*`)

| Задача | Требования |
|---|---|
| API: Project, Signal, Document, BOQ resources — read + `list/get` с cursor pagination (переиспользует конвенции Phase 0) | FR-TND-03, FR-TND-11 |
| Human decision endpoint: tender↔project link — accept/reject как отдельная append-only сущность, ingestion не пишет в неё | FR-TND-08, DM-04, P003 |
| Инвариант: reject/confirm переживает повторный sync (candidate обновляется, human decision — никогда) | FR-TND-09, INV-01, P004 |
| BOQ reconciliation API: `boq_import` статус (`complete`/`incomplete`/`source_exhausted_unverified`) с перечнем недостающих страниц/строк | FR-DQ-01, FR-DQ-02, P001 |
| Data-quality статус в ответах API везде, где данные используются для решения (`missing/stale/incomplete/synthetic/verified`) | FR-DQ-03 |

### 2.C — worker-connector (после 2.A, параллельно с 2.B)

| Задача | Требования |
|---|---|
| Полная BOQ-пагинация: продолжение resumable pagination Phase 1 до доказанного reconciliation (заявленный источником total == сохранённые строки) | FR-TND-04, FR-DQ-01, INV-04 |
| Document fetch с provenance и статусом загрузки (missing документ виден как missing, не как пустое поле) | FR-TND-03 |
| Version + diff при любом изменении tender/BOQ/документа; независимый статус на каждый subresource (list/details/BOQ) | FR-TND-05, FR-TND-07, P108, P109 |
| Signal generation на изменение срока/документа/BOQ/статуса | FR-TND-06 |

### 2.D — frontend (после 2.B/2.C дают контракт; можно начинать UI на mock-данных раньше, интеграция — после)

| Задача | Требования |
|---|---|
| Command Center: сигналы, задачи, состояние источников, очередь исключений, статус решений | FR-UX-01 |
| Экраны: Tenders, Projects, Signals, Documents/BOQ, Data Quality & Exceptions, Source Health (§17.2) | FR-TND-11 |
| Deep links на каждую сущность/фильтр/вкладку; reload и share восстанавливают состояние | FR-PLT-08, FR-TND-12, P223 |
| Version diff UI для tender/BOQ/документов | FR-TND-05 |
| Явное отображение partial/stale/synthetic/incomplete состояний — никогда не маскируются как готовые | FR-UX-04, FR-DQ-02, FR-DQ-03 |
| Employee dashboard: масштаб рынка, новые тендеры, сигналы, состояние данных | FR-TND-11 |

### 2.E — security/qa (последняя, закрывает ворота)

| Задача | Требования |
|---|---|
| Browser E2E для каждой роли на реальном браузере | FR-UX-03 |
| WCAG 2.2 AA: автоматический axe в CI + ручная проверка клавиатурной навигации критических потоков | FR-UX-02, P226 |
| Regression suite: P001, P003, P004, P108, P109, P223, P226 — 100% pass в Full gate | Приложение A PRD |
| Acceptance proof: reject/confirm переживает resync (P003/P004), BOQ completeness proof на реальном пилотном диапазоне (P001), reload/share восстанавливают состояние (P223) | см. Exit gate ниже |

---

## 4. Exit gate Phase 2

| Критерий | Требуемое доказательство |
|---|---|
| BOQ completeness proof | лог reconciliation теста на реальном диапазоне: stored == source total, либо `incomplete` с перечнем |
| Реальный пилотный диапазон reconciled | отчёт по факту загруженных тендеров/страниц |
| Reject/Confirm переживают resync | лог P003/P004 теста: reject → sync → остаётся rejected |
| Partial data никогда не complete | лог FR-DQ-02 теста |
| Browser E2E/accessibility проходят | CI-прогон E2E + axe отчёт |

---

## 5. Открытые вопросы

- **D-LANG** (язык первого UI, порядок AZ/RU/EN) — блокирует финальный выбор locale-контента, не блокирует архитектуру i18n (2.A закладывает каркас без выбора языка).
- **D-OWN** (product owner/tech lead) — не блокирует техническую работу, нужен для будущих approval-gate (Phase 4+).
- Оба наследуются из PLAN-MISSION-1 §4.2 без изменений; ответ не требуется для старта Миссии 2.

## 6. Трассируемость: регрессии, закрываемые в Миссии 2

Полностью: **P001, P003, P004, P108, P109, P223, P226** (Full gate, 100% pass).
Частично продвигаются (стабы Phase 0 наполняются экранами): P110-P120, P222 — не входят в обязательный 100%-набор этой миссии, продолжаются в Phase 3+.
P005 (final Bid gate) остаётся вне scope — домен Phase 4 (Decision Intelligence), как зафиксировано в PLAN-MISSION-1 [правка №1].

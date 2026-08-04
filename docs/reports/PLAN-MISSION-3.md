# PLAN-MISSION-3 — Phase 3: Vendor synthetic sandbox

**Статус:** ЧЕРНОВИК. Активируется только после GO супервайзера по Exit gate Phase 2 (PLAN-MISSION-2.md). Подготовлен заранее по прямому запросу владельца («till last phase») — планирование всех оставшихся фаз, исполнение остаётся строго последовательным.
**Дата:** 2026-08-04
**Приоритет источников:** PRD v1.1 > master plan §10, §17.3, §18 Phase 3 > v1 audit.
**Зависимость:** Exit gate Phase 2 принят (real Tender UI/BOQ/documents работают, P001/P003/P004/P108/P109/P223/P226 зелёные).

## 0. Подтверждение чтения (для этой миссии)

- PRD: FR-VND-01..09, NEG-04, DM (domain model §4), INV-02/INV-11, §5.5, §6.3 NFR-PRV-01..02 (готовим почву для Phase 7, не решаем сейчас).
- Master plan §10 (Module 2 — Vendor Intelligence: synthetic first, real-ready): 10.2 генератор сценариев, 10.3 vendor domain, 10.4 adapter contract, 10.5 real onboarding (только как контракт на будущее, не исполняется здесь), 10.6 DoD; §17.3 экраны; §18 Phase 3 (результаты/exit gate).
- Открытый вопрос **D-TAX** (material taxonomy, UOM conversions, источники FX/VAT/discount rate) блокирует часть Phase 3/4 — см. §5 ниже.

## 1. Дисциплина выполнения

Наследуется из PLAN-MISSION-1 §1. **Новое для Миссии 3:** первый домен, физически изолированный от Tender — `packages/vendor` создаётся с нуля (Phase 0 создал только README-заглушку). Синтетический контур должен быть отделён от real данных на уровне namespace/route/DB с первого коммита (FR-VND-01, FR-VND-06), а не добавлен позже.

---

## 2. Область Phase 3 (master plan §18)

Результаты: vendor domain schemas; UOM/currency/VAT semantics; deterministic generator; provider contract; offers/inventory/capacity/evidence UI; visible synthetic isolation; data quality and freshness.

Exit gate: два разных fake provider удовлетворяют контракту; нет synthetic-утечки в real dashboards; edge-case сценарии воспроизводимы по seed; real provider добавляется только через adapter.

---

## 3. Задачи по очереди

### 3.A — architect (первая, блокирующая)

| Задача | Требования |
|---|---|
| `packages/vendor` domain schema: legal entity/registration, status/ownership/sites, scoped contacts + PII classification (поля размечены, реальные PII не собираются — synthetic only), material/service catalog, offers (currency/UOM/VAT/MOQ/validity/lead time), inventory snapshot и capacity snapshot как **разные** сущности, certification/evidence с сроком действия, delivery geography, performance outcomes, onboarding/review/suspension history | FR-VND-05, master plan §10.3 |
| ADR: synthetic/real isolation на уровне namespace/route/DB (расширяет ADR-0004 из Phase 0); watermark `SYNTHETIC` обязателен в UI/API/export | FR-VND-01, FR-VND-06, NEG-04 |
| `VendorProvider` adapter contract: `list_vendors(cursor, changed_since)`, `get_vendor`, `list_offers`, `list_inventory`, `list_capacity`, `list_evidence`, `acknowledge_sync(result)` | FR-VND-04, master plan §10.4 |
| Открытый вопрос D-TAX зафиксирован в `docs/decisions/OPEN-QUESTIONS.md`: UOM conversion table и FX/VAT source adapters — placeholder-контракт без утверждённых коэффициентов (INV-11: отсутствие значения не маскируется) | D-TAX §13.2 PRD |

### 3.B — backend-core (после 3.A)

| Задача | Требования |
|---|---|
| API для vendor/offer/inventory/capacity/evidence: cursor pagination, idempotency, ETag — переиспользует конвенции Phase 0 | FR-PLT-02..06 (наследие) |
| Price/UOM/VAT normalization: исходная цена/UOM/VAT никогда не теряется при отображении нормализованного значения (raw + normalized хранятся раздельно) | FR-VND-05, master plan §10.6 |
| Data-quality/freshness статус per vendor record (`missing/stale/incomplete/synthetic/verified`) | FR-DQ-03, FR-UX-04 (наследие) |
| Route/service/database изоляция: synthetic namespace не пересекается с production-контуром ни на одном уровне | FR-VND-06, NEG-04 |

### 3.C — synthetic generator (worker/tooling, параллельно с 3.B — независимый код в `fixtures/synthetic` + `packages/vendor/generator`)

| Задача | Требования |
|---|---|
| Детерминированный seed → воспроизводимый набор данных | FR-VND-02 |
| Полный набор сценариев: normal vendor; low price/late delivery; high quality/high cost; stale offer; mixed UOM; VAT included/excluded; MOQ conflict; currency mismatch; capacity shortfall; expiring certificate; missing evidence; partial fulfillment history; outlier bid; multi-site vendor; duplicate legal entity/contact; vendor unavailable during critical period | FR-VND-03, master plan §10.2 |
| Второй, независимо реализованный synthetic provider (другая форма данных) — доказывает, что adapter contract не завязан на первую реализацию | FR-VND-04, exit-критерий «два fake provider» |

### 3.D — frontend (после 3.B даёт контракт; экраны на mock раньше допустимы)

| Задача | Требования |
|---|---|
| Экраны: Synthetic Sandbox, Vendors, Offers, Inventory/Capacity, Evidence/Certifications, Onboarding Queue (placeholder — заполняется в Phase 7), Provider Connections (§17.3) | master plan §17.3 |
| Визуальный watermark `SYNTHETIC` на каждом экране/экспорте, где показаны synthetic данные | FR-VND-01 |
| Явное отображение partial/stale/synthetic состояний (наследие FR-UX-04) | FR-UX-04 |

### 3.E — security/qa (последняя, закрывает ворота)

| Задача | Требования |
|---|---|
| Isolation test suite: route/service/database — synthetic record не может быть превращён в real record ни одним путём в системе | FR-VND-06, NEG-04 |
| Seed reproducibility test: один seed → идентичный набор данных byte-for-byte | FR-VND-02 |
| Adapter contract test: оба fake provider проходят один и тот же contract test suite | FR-VND-04 |
| Ranking/normalization explainability test: vendor ranking (если уже есть базовый скоринг-стаб) воспроизводим и объясним | master plan §10.6 |

---

## 4. Exit gate Phase 3

| Критерий | Требуемое доказательство |
|---|---|
| Два разных fake provider удовлетворяют контракту | contract test suite log на обоих providers |
| Нет synthetic-утечки в real dashboards | isolation test log (route/service/DB) |
| Edge-case сценарии воспроизводимы по seed | лог повторного прогона генератора с тем же seed |
| Real provider добавляется только через adapter | code review gate: нет альтернативного пути создания real vendor record (FR-VND-07 остаётся закрыт до Phase 7) |

## 5. Открытые вопросы

- **D-TAX** — material taxonomy, UOM conversions, источники FX/VAT/discount rate: блокирует **финальные** утверждённые коэффициенты, не блокирует старт Phase 3 (генератор и normalization работают на placeholder-контракте с explicit `TBD` там, где коэффициент не утверждён — INV-11).
- D-PII (Phase 7) и D-FIN (Phase 5) не блокируют эту миссию — упоминаются только для трассируемости.

## 6. Трассируемость

Phase 3 не закрывает regression-номера из Приложения A напрямую (Vendor-домен не входил в 29 находок v1 audit — v1 не имел отдельного vendor-модуля с этим scope). Основной критерий приёмки — exit-gate §4 выше и FR-VND-01..09 acceptance-проверки из PRD §5.5.

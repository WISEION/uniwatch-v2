# PLAN-MISSION-1 — Phase 0 + Phase 1

**Статус:** GO от супервайзера (задание №002) с замечанием №1 — внесено правкой ниже (см. пометки «[правка №1]»). Код не писался на момент правки; структура исходников создаётся в рамках задачи 0.A.
**Дата:** 2026-08-04
**Приоритет источников при конфликте:** PRD v1.1 > master plan 2026-07-28 > tender source map / v1 audit.

**[правка №1, задание №002]:** P003/P004 (link decisions: rejected/confirmed tender↔project связь, домен FR-TND-08/09/DM-04) и P005 (final Bid/No-Go gate, домен FR-DEC-05/06) **не закрываются полностью в Phase 1**. Их владеющие домены (Vendor/Project linking, Decision) появляются в Phase 2 (linking UI/API) и Phase 4 (Decision/Bid) соответственно. В Phase 0/1 для P003/P004/P005 создаются только: доменные инварианты, зафиксированные в ADR/DM-контракте (append-only candidate vs human decision; transactional final hard-stop), и **стабы regression-тестов с явной пометкой фазы**, в которую они становятся обязательными к прохождению. Ни один отчёт о Phase 0/1 не должен называть P003/P004/P005 закрытыми регрессиями Миссии 1.

## 0. Подтверждение чтения (Шаг 0 ТЗ)

Прочитаны все 5 документов из `C:\Users\orkha\Documents\Uniwatch VER2\`:

1. `uniwatch-v2-project.md` — зафиксированные решения и проверенные факты (пути на диске, release-notes baseline: 13 ролей/29 permissions, dev_team временная, eTender без VÖEN/денег, BOQ полный на API).
2. `UNIWatch-v2-PRD-v1.0.md` (830 строк) — контракт FR-*/NFR-*/INV-01..14/NEG-01..07/P001-P229/§9 gates/§10 фазы/§13 открытые решения/Приложения A-D.
3. `UNIWatch-v2-master-development-plan-2026-07-28.md` (1721 строка) — §7 архитектура, §14 доменная модель, §18 roadmap, §21 тесты, §22 gates.
4. `UNIWatch-v2-tender-intelligence-source-map-deep-research-2026-07-28.md` — источники тендерных данных, уровни доказательности A/B/C/D/X.
5. `Uniwatch\UNIWatch-v1-full-audit-2026-07-27.md` — 29 находок v1 (regression checklist Приложения A) + 13 доп. дефектов из release notes (RN-01..13) = 42 обязательных regression-теста.

Также прочитан `PROJECT-CONTROL.md` супервайзера — чек-листы приёмки ниже построены так, чтобы каждый его пункт имел явное доказательство.

## 1. Дисциплина выполнения (обязательна, не обсуждается)

- Один основной поток, фазы не перекрываются. Phase 1 не начинается без GO по Phase 0 от супервайзера.
- Субагенты — специализация **внутри** текущей фазы, не параллельные стройки. Короткая параллельность допускается только для задач без общего кода (разные `apps/*` без взаимных импортов); при сомнении — последовательно.
- Каждая задача ниже помечена номером очереди (0.A, 0.B, …) — это порядок выполнения внутри фазы, не список для одновременного старта.
- Каждое отклонение от PRD/master plan или новое допущение фиксируется в `docs/decisions/OPEN-QUESTIONS.md`, не решается молча.
- Никаких TBD-чисел не подставляется (financial weights, ML thresholds, SLO/RPO/RTO, точный permission matrix) — они остаются `TBD-01..05` / D-* до отдельного research/approval gate (PRD §5.7.4, §13).

---

## 2. Phase 0 — Foundation

Цель фазы (master plan §18, PRD §10.1): репозиторий и границы модулей, PostgreSQL migration ledger, FastAPI + worker + jobs + outbox skeleton, observability, CI Fast/Full gate.

### 0.A — architect (первая, блокирующая остальные)

Зона по TZ: скелет repo, ADR, границы модулей, миграции.

| Задача | Требования |
|---|---|
| Каталог репозитория по логической заготовке master plan §7.3: `apps/{api,worker,web}`, `packages/{platform,tender,vendor,decision,algorithm,contracts}`, `migrations/`, `tests/{unit,integration,contract,state,security,e2e,performance}`, `fixtures/{synthetic,tender-snapshots}`, `docs/{CONTEXT.md,architecture,adr,product,research,operations}` | NFR-ARC-05, NFR-ARC-06 |
| `AGENTS.md` / `docs/CONTEXT.md` — границы, запрет писать в v1, read-docs-first | NEG-01, NEG-02, NFR-DOC-01 |
| ADR: modular monolith boundaries; стек (React/TS + FastAPI + отдельный Python worker + PostgreSQL); data authority/provenance model (4 слоя: raw/normalized/derived/human decision); synthetic/real isolation; human/algorithm/ML authority; two-person financial policy & production deployment | NFR-ARC-01..07, DM-01..06, FR-AUT-01..06, FR-VND-06, INV-13, INV-14 |
| Threat model (черновик, дорабатывается совместно с 0.C security) | NFR-SEC-01..09, exit-критерий «architecture and threat model approved» |
| PostgreSQL migration ledger: versioned migrations, pre/postflight, схема НЕ меняется при startup; backfill — отдельная от startup операция | FR-PLT-12, DM-06, P007, P114 (regression) |
| CI-проверка неприкосновенности v1: пути `Documents\Tendet Watcher`, `Documents\UNIWatch` (другой checkout), запрет write-credentials из runtime v2 | FR-MIG-04, NEG-01, NEG-02 |

### 0.B — backend-core и worker-connector (короткая параллельность — разные `apps/*`, нет общего кода)

**backend-core:**

| Задача | Требования |
|---|---|
| FastAPI contract-first skeleton: OpenAPI как источник истины, strict request/response validation, единый error envelope с correlation id | FR-PLT-01, P117 |
| Конвенции: idempotency key для мутаций (учитывает все различающие атрибуты, включая deadline), cursor pagination (без offset), ETag/version precondition для важных edits, command/query separation (GET не пишет) | FR-PLT-02..06, FR-PLT-11, P111, P112, P115, P119, P222 |
| RBAC skeleton: deny-by-default, серверная проверка прав на каждом route/service, права как permissions→roles конфигурация, disable вместо delete | FR-ADM-01..05, INV-08, FR-AUT-01..06 |
| Reverse proxy: явные trusted CIDR, verified peer IP для lockout/rate-limit | FR-PLT-07, P112 |
| Structured logs с correlation id, liveness/readiness endpoints (readiness учитывает миграции и зависимости) | NFR-OBS-01, NFR-OBS-03, P118 |

**worker-connector:**

| Задача | Требования |
|---|---|
| Отдельный Python worker-процесс; job identity (тип, параметры, источник, диапазон, версия контракта, correlation id) | NFR-ARC-03, FR-JOB-02, P002, P116 |
| Lease/progress/retry с backoff/cancel/resume; job переживает restart | FR-JOB-01, FR-JOB-03, P113 |
| Transactional outbox для внешних эффектов (at-least-once с точки зрения получателя, консьюмер идемпотентен) | FR-JOB-07 |
| Structured logs с correlation id сквозным через API → worker → outbox | NFR-OBS-01 |

### 0.C — security (после того как 0.A/0.B дали скелет для ревью)

| Задача | Требования |
|---|---|
| Ревью и утверждение threat model (совместно с architect) | NFR-SEC-01..09, exit-критерий Phase 0 |
| Дизайн центрального egress validator и trusted source registry (реализация полностью — в Phase 1, здесь — контракт и место в архитектуре) | NFR-SEC-01..03, INV-10, подготовка к P006 |
| CI security-gate stub: secret scan, dependency scan/SCA, license scan план (полное включение — Release candidate gate) | NFR-SEC-07, NFR-SEC-09 |
| Non-root/read-only container конвенция для build | NFR-SEC-08 |

### 0.D — qa (последняя в фазе — закрывает ворота)

| Задача | Требования |
|---|---|
| CI Fast gate: format/lint/typecheck, unit+property tests, API schema validation, migration syntax | §9.1 PRD, Gate 1 master plan §22 |
| CI Full gate wiring: integration/contract/state tests, security suite, browser E2E+a11y, migration rehearsal, invariant check — включается пустым/минимальным каркасом, наполняется в Phase 1 | §9.1 PRD, Gate 2 master plan §22 |
| Migration rehearsal тест: upgrade на пустой И на seeded БД, идемпотентный повтор | FR-PLT-12, exit-критерий «empty and seeded DB migrate» |
| Тест: инъекция FK/invariant-нарушения → quarantine/read-only, CI блокирует | FR-PLT-13, P007 |
| Тест: worker job переживает restart (resume с чекпойнта) | FR-JOB-03, exit-критерий «worker job survives restart» |
| Стабы (пустые/skip-помеченные) для всех 42 regression-тестов (29 Приложения A + 13 RN) с явной пометкой, в какой фазе каждый становится обязательным | G6 PRD, Приложение A и D.2 |

### Exit gate Phase 0 (доказательства, не слова — PROJECT-CONTROL чек-лист)

| Критерий | Требуемое доказательство |
|---|---|
| v1 не тронут | вывод CI-проверки путей + отсутствие write-credentials |
| Пустая и seeded БД мигрируют; схема не меняется при startup | лог migration rehearsal теста, FR-PLT-12 |
| Worker job переживает restart | лог теста kill+resume |
| CI блокирует invariant/security failure | пример намеренно заблокированного прогона |
| ADR (boundaries/stack/data authority) и threat model | ссылки на файлы `docs/adr/*`, `docs/architecture/threat-model.md` |
| OpenAPI/idempotency/error format зафиксированы | ссылка на `docs/architecture` + пример контракта |
| Fast + Full gates реально запускаются | ссылка на CI workflow + прогон |

---

## 3. Phase 1 — Tender ingestion core

Открывается только после GO по Phase 0. Цель: eTender connector как empirical contract, raw→normalized versioning, resumable pagination, egress validator, exception queue, P001/P002/P006/P007 зелёные (P003/P004/P005 — доменные инварианты + фазово-помеченные стабы, см. правку №1 выше и §5).

### 1.A — worker-connector (первая, блокирующая остальные задачи фазы)

| Задача | Требования |
|---|---|
| eTender connector как **empirical contract**: frozen fixtures + schema-drift detector; валидация фактических значений ответа (не доверять параметрам запроса — `EventType=2` возвращал `eventType=7`) | INT-01, INT-02, FR-TND-10 |
| Raw snapshot (immutable, checksum) → отдельная normalized immutable version | FR-TND-02, DM-02, DM-03, P108 |
| `identity_query_keys` в контракте источника — идентичность записи не теряется при канонизации URL (урок RN-06) | INT-02 |

### 1.B — worker-connector (продолжение, после 1.A)

| Задача | Требования |
|---|---|
| Resumable pagination: cursor двигается только после атомарного commit страницы; ошибка страницы не перескакивает вперёд; новый фильтр/диапазон всегда начинает с первой страницы | INV-03, FR-JOB-04, FR-JOB-05, FR-JOB-06, P002 |
| BOQ completeness contract: `boq_import` (expected_total, expected/observed pages, stored_lines, checksum per page), статус `complete` только при доказанном reconciliation; при отсутствии `totalItems` от источника — `source_exhausted_unverified`, не `complete` | FR-DQ-01, FR-DQ-02, FR-TND-04, INV-04, P001 |
| Независимые статусы subresource (list/details/BOQ) — ошибка enrichment не выглядит успехом | FR-TND-07, P109 |

### 1.C — security (короткая параллельность с 1.A — независимый сетевой слой, интеграция перед тем как worker пойдёт в реальную сеть)

| Задача | Требования |
|---|---|
| Центральный egress validator: проверка до DNS-резолва и после каждого redirect; блокировка loopback/private/link-local/metadata (IPv4+IPv6) | NFR-SEC-01, INV-10, P006 |
| Trusted source registry: внешние запросы только к зарегистрированным источникам; каждый новый источник проверяется реальным прогоном сканера до включения (урок ADB/0.18.0 — структурная проверка «HTTPS + код + trust level» недостаточна) | NFR-SEC-03 |
| SSRF test suite: IPv4, IPv6, redirect, DNS rebind | P006, M6 |

### 1.D — worker-connector / backend-core (после 1.B/1.C)

| Задача | Требования |
|---|---|
| Exception queue: невосстановимые элементы — с причиной и raw evidence, не теряются молча; UI-less API для retry/close с причиной (экран — Phase 2) | FR-JOB-08 |

### 1.E — qa (последняя, закрывает ворота Phase 1)

| Задача | Требования |
|---|---|
| P001, P002, P006, P007 regression suite — 100% pass в Full gate. P003, P004, P005 — стаб-тесты присутствуют, помечены skip до своей фазы (P003/P004 → Phase 2, P005 → Phase 4), не входят в 100%-требование Миссии 1 | M3, Приложение A; [правка №1] |
| Acceptance proof: page 2 fails → resume page 2 (не 3), без дублей/пропусков | FR-JOB-05, P002 |
| Acceptance proof: смена фильтра/диапазона → новый job начинает страницу 1 | FR-JOB-06 |
| Acceptance proof: изменение фикстуры источника → `schema_drift_event`, а не тихая потеря полей | FR-TND-10, INT-02 |
| Traceability test: каждый tender открывает raw snapshot по checksum | FR-TND-02 |
| SSRF suite зелёный (см. 1.C) | P006, NFR-SEC-01 |

### Exit gate Phase 1

| Критерий | Требуемое доказательство |
|---|---|
| Page failure возобновляется корректно | лог P002 теста |
| Schema drift детектируется | лог теста на изменённой фикстуре |
| Нет SSRF-маршрутов | лог SSRF suite (IPv4/IPv6/redirect/rebind) |
| Каждый tender прослеживается до source snapshot | лог traceability теста |
| (доп., из PROJECT-CONTROL) Cursor двигается только после атомарного commit | лог INV-03 теста |
| (доп.) Exception queue работает и видна | лог/API exception queue |

---

## 4. Открытые вопросы владельцу

### 4.1 Уже отвечены в самом ТЗ («Что уже решено», не переоткрываются)

Соответствуют блокирующим решениям PRD §13.1 D-ARCH, D-AUTH, D-DATA, D-P0 — зафиксированы владельцем в разделе «Что уже решено» кикофф-ТЗ: стек Подход A, ML только advisory, synthetic-first vendor контур, старт Phase 0 в `C:\Users\orkha\Documents\UNIWatch-v2`. Дополнительного согласования не требуется для старта Phase 0/1.

**Пробел:** D-OWN (назначение product owner и tech lead, PRD §13.1) не встречается в кикофф-ТЗ явным именем. Не блокирует техническую работу Phase 0/1, но нужен персонально для будущих approval-gate (financial policy maker/checker, production authorization, Phase 5+ ALG-RESEARCH).

### 4.2 Блокируют только свою фазу (PRD §13.2) — требуют ответа до соответствующего gate, не сейчас

| ID | Вопрос | Блокирует | Почему можно начинать без ответа сейчас |
|---|---|---|---|
| **D-HOST** | Hosting: локальная сеть / private cloud / public cloud | Phase 0 (production-часть) / Phase 6 | Phase 0/1 разрабатываются в локальном/dev окружении; production authorization (Gate 4) наступает не раньше controlled pilot |
| **D-IDP** | Identity: Entra/OIDC для пилота, включая break-glass | Phase 0 (auth-часть) / Phase 6 | Phase 0/1 не требуют реального пилотного логина; достаточно локального dev-auth/RBAC skeleton, который не зависит от конкретного IdP |
| **D-SRC** | Согласованные real tender sources помимо eTender, допустимый диапазон истории, условия хранения snapshots/документов | Phase 1 | eTender уже выбран владельцем как primary source (JSON-first); открыт именно объём истории и retention-политика raw snapshot — нужен ответ до того, как Phase 1 будет считаться закрытым по полному объёму пилотного диапазона, но не блокирует старт коннектора на ограниченном тестовом диапазоне |
| **D-LANG** | Язык первого UI и последовательность AZ/RU/EN | Phase 2 | Phase 0/1 не содержат UI-экранов; архитектура закладывает i18n с первого дня (FR-UX-05) без выбора конкретного языка |

Остальные решения PRD §13.2 (D-PILOT, D-TAX, D-FIN, D-PII, D-SLO, D-ML) блокируют Phase 3+ и не входят в Миссию 1; перечисляются здесь для полноты трассируемости и не требуют ответа сейчас.

### 4.3 Явно НЕ подставленные числа (запрет TZ п.2 «Жёсткие запреты»)

TBD-01 (SLO/latency/freshness), TBD-02 (RPO/RTO), TBD-03 (ML minimum labels/uplift/calibration), TBD-04 (financial policy weights), TBD-05 (бюджет) — остаются нерешёнными и не участвуют в Phase 0/1 acceptance proofs. Ни одно значение по умолчанию не выбрано этим планом.

---

## 5. Трассируемость: не покрытые в Миссии 1 регрессии

Из 42 обязательных regression-тестов (29 Приложения A + 13 RN) в Phase 0/1 полностью закрываются: **P001, P002, P006, P007** (Full gate, 100% pass).

**[правка №1]** **P003, P004** (link decisions — rejected/confirmed tender↔project связь, домен FR-TND-08/09/DM-04) и **P005** (final Bid/No-Go gate, домен FR-DEC-05/06) в Миссии 1 **не закрываются полностью**: их владеющие домены появляются в Phase 2 (P003/P004 — linking) и Phase 4 (P005 — Decision/Bid). В Phase 0/1 для них создаются только доменные инварианты (append-only candidate vs human decision для P003/P004; transactional final hard-stop для P005) и стаб-тесты с явной пометкой фазы, в которой каждый становится обязательным. Не отчитываются как закрытые регрессии этой фазы.

Частично готовятся инфраструктурой Phase 0 — **P108, P109, P110, P111, P112, P113, P114, P115, P116, P117, P118, P119, P222** (стабы созданы в 0.D, полная реализация продолжается по мере построения соответствующих экранов/потоков в Phase 2+). Остальные (P120, P221, P223-P229, RN-01..13, кроме уже перечисленных) относятся к доменам Vendor/Decision/Algorithm/UX и вне scope Миссии 1 — не считаются регрессией этой фазы.

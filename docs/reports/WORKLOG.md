# WORKLOG

## 2026-08-04 — Задание №001: план Миссии 1

**Сделано:**
- Прочитаны все 5 документов Шага 0 ТЗ (`uniwatch-v2-project.md`, `UNIWatch-v2-PRD-v1.0.md`, `UNIWatch-v2-master-development-plan-2026-07-28.md`, tender source map, `UNIWatch-v1-full-audit-2026-07-27.md`) + `PROJECT-CONTROL.md` супервайзера.
- Написан `docs/reports/PLAN-MISSION-1.md`: Phase 0 (architect → backend-core/worker-connector → security → qa) и Phase 1 (worker-connector → security → worker-connector/backend-core → qa), каждая задача со ссылками на FR-*/INV-*/NEG-*/NFR-*/P0xx.
- Собран список открытых вопросов: D-HOST/D-IDP/D-SRC/D-LANG (блокируют только свои фазы, не Phase 0/1 старт) + пробел D-OWN.
- Код не писался, git не инициализирован, структура исходников не создавалась, пути v1 не затронуты.

**Дальше:** ожидание вердикта GO/NO-GO супервайзера по `PLAN-MISSION-1.md`. При GO — Phase 0, начиная с задачи 0.A (architect: repo skeleton + ADR + migration ledger).

**Блокеры:** нет для старта Phase 0. D-HOST/D-IDP нужны до production-части Phase 0/6, не блокируют разработку сейчас; D-SRC нужен до финального объёма Phase 1 (historical range/retention), не блокирует старт коннектора eTender.

## 2026-08-04 — Задание №002: Phase 0, задача 0.A (architect)

**Сделано:**
- Правка `docs/reports/PLAN-MISSION-1.md` по замечанию №1: P003/P004 (link decisions, FR-TND-08/09/DM-04) и P005 (final Bid gate, FR-DEC-05/06) явно помечены как незакрываемые полностью в Phase 1 — их домены в Phase 2/4; в §5 и §1.E зафиксировано, что в Миссии 1 закрываются только P001/P002/P006/P007.
- Структура репозитория по master plan §7.3: `apps/{api,worker,web}`, `packages/{platform,tender,vendor,decision,algorithm,contracts}`, `migrations/{preflight,postflight}`, `tests/{unit,integration,contract,state,security,e2e,performance}`, `fixtures/{synthetic,tender-snapshots}`, `docs/{architecture,adr,product,research,operations,decisions,superpowers/plans}`, `operations/`, `scripts/`, `tools/`, `.ci/` — с README-заглушками в каждом каталоге, где нет кода (NFR-ARC-05, NFR-ARC-06).
- `AGENTS.md` (read-docs-first, hard bans, границы доменов, repo map, traceability convention) и `docs/CONTEXT.md` (сжатая свежая сводка 5 документов + границы) — NEG-01, NEG-02, NFR-DOC-01.
- 5 ADR в `docs/adr/`: 0001 boundaries (NFR-ARC-05..07, DM-01, INV-02), 0002 stack (NFR-ARC-01..04/06), 0003 data authority/provenance — 4 слоя (DM-01..06, INV-01/02/04/05/11/12), 0004 synthetic/real isolation (FR-VND-06, NEG-04), 0005 authority model — human/ML/maker-checker/production deploy (FR-AUT-01..06, INV-06/07/13/14).
- Черновик `docs/architecture/threat-model.md` (NFR-SEC-01..09, INV-10, P006) — статус draft, ждёт совместного ревью с 0.C перед закрытием ворот Phase 0.
- Каркас migration ledger: `migrations/README.md` (конвенция pre/postflight, схема не меняется при старте — FR-PLT-12, backfill отдельно — DM-06), `migrations/0000_ledger.sql` (bootstrap таблицы `schema_migrations`), `migrations/preflight/README.md`, `migrations/postflight/README.md` (FR-PLT-13, P007).
- `tools/check_v1_untouched.py` (FR-MIG-04, NEG-01, NEG-02) — stdlib-only: (1) скан репозитория на литералы v1-путей вне allowlist документации, (2) baseline sha256-снимок v1-каталогов с детектом drift; плюс `.ci/README.md` с описанием, как это встраивается в Fast gate. Скрипт статически проверен (py_compile logic reviewed вручную); фактический запуск в этой сессии не выполнен — выполнение Python не было разрешено в текущем permission-режиме (`git init` разрешили, `python ...` — нет). Нужно прогнать `python tools/check_v1_untouched.py --init` вручную либо в следующей сессии с разрешением на выполнение.
- `git init` + `.gitignore` + первый коммит (все файлы задачи 0.A).

**Дальше:** задача 0.A закрыта в границах этого задания. Ожидание: (a) подтверждения, что `python tools/check_v1_untouched.py --init` реально прогнан и PASS; (b) вердикта супервайзера на продолжение — задача 0.B (backend-core + worker-connector), затем 0.C (security review threat model), затем 0.D (CI gates, migration rehearsal, regression-стабы).

**Блокеры:** выполнение `tools/check_v1_untouched.py` не подтверждено запуском в этой сессии (permission на python не выдана) — доказательство "v1 не тронут" для Exit gate Phase 0 пока неполное, нужен реальный прогон. Остальные блокеры не изменились (см. запись №001): D-HOST/D-IDP/D-SRC/D-LANG блокируют только свои фазы.

## 2026-08-04 — Черновик PLAN-MISSION-2 (Phase 2)

**Сделано (вне очереди задания №003, по прямому запросу владельца — «сначала план»):**
- Написан `docs/reports/PLAN-MISSION-2.md`: Phase 2 (Real Tender experience, documents, BOQ), задачи 2.A architect → 2.B backend-core / 2.C worker-connector (параллельно) → 2.D frontend → 2.E security/qa, со ссылками на FR-TND-01..12/FR-DQ-01..05/FR-UX-01..05/FR-PLT-08/DM-04/INV-01/INV-04 и regression P001/P003/P004/P108/P109/P223/P226.
- Явно помечено ЧЕРНОВИКОМ: не активируется до вердикта GO по Exit gate Phase 1 (текущий статус: Phase 0 задача 0.B ещё не принята супервайзером, Phase 1 не начата).
- Код не писался, `apps/web` не создавался — только план.

**Дальше:** ожидание — (a) закрытия Task-003 (0.B) и Exit gate Phase 0/1 супервайзером; (b) при GO по Phase 1 — ревью и вердикт по PLAN-MISSION-2.md перед стартом задачи 2.A.

**Блокеры:** нет новых; см. запись №002.

## 2026-08-04 — Задание №003: Phase 0, задача 0.B, часть 1 (backend-core)

**Блокер задания №002 закрыт:** согласно заданию №003, супервайзер прогнал `tools/check_v1_untouched.py --init` — PASS. Подтверждения самостоятельно в этой сессии не делал (см. вторую запись блокеров ниже про permission на выполнение).

**Сделано:**
- План `docs/superpowers/plans/2026-08-04-phase0-backend-worker.md` (writing-plans skill): файловая структура и трассировка задач 0.B на FR-*/INV-*/P0xx до начала кода.
- `pyproject.toml`: единый проект для `apps/*` + `packages/*` (модульный монолит, одна зависимость-группа). Зависимости зафиксированы по версии: `fastapi==0.115.6`, `sqlalchemy[asyncio]==2.0.36`, `asyncpg==0.30.0`, dev: `pytest`, `pytest-asyncio`, `httpx`, `testcontainers[postgres]`.
- `packages/platform/migrations_runner.py` + `migrations/000{1,2}_*.sql` (users/roles/permissions/role_permissions/idempotency_keys/audit_log/jobs/outbox): apply-if-not-applied, checksum-guard против правки уже применённой миграции, preflight/postflight hooks (точка квараntine для FR-PLT-13), `assert_schema_up_to_date()` — только чтение, старт никогда не мигрирует сам (FR-PLT-12, DM-06, P007, P114).
- `packages/platform/correlation.py` (raw ASGI middleware — `BaseHTTPMiddleware` теряет необработанные исключения при использовании с `Exception`-хендлером, обошёл), `packages/platform/errors.py` (единый error envelope, correlation id проставляется явно в error-хендлерах, т.к. `ServerErrorMiddleware` шлёт fallback-ответ в обход пользовательских middleware), `packages/platform/logging.py` (JSON-логи с correlation id) — FR-PLT-01, NFR-OBS-01, P117.
- `packages/platform/idempotency.py` (ключ + route + fingerprint запроса; смена fingerprint при том же ключе → `IdempotencyKeyReused`, не тихий replay) — FR-PLT-03, P111. `pagination.py` (opaque cursor, без offset) — FR-PLT-05, P119. `concurrency.py` (If-Match → 409 + текущая версия) — FR-PLT-04, P115.
- `packages/platform/rbac/*` (deny-by-default: неизвестный/disabled юзер → нет identity; роль без permissions → пустой набор, никогда не all-access) — FR-ADM-01..03, INV-08. `packages/platform/audit.py` (disable, не delete; append-only audit на каждую мутацию) — FR-ADM-04/05.
- `packages/platform/proxy.py` (verified peer IP: `X-Forwarded-For` учитывается только если реальный peer внутри доверенного CIDR) — FR-PLT-07, P112.
- `apps/api/main.py` + `deps.py` + `routers/health.py` (liveness/readiness, readiness читает ledger+DB, не мигрирует) + `routers/admin_users.py` (единственный конкретный ресурс — platform admin/users, не домен Tender/Vendor/Decision — демонстрирует все конвенции выше сквозь реальный HTTP).
- Тесты: 57 passed (unit + integration через testcontainers Postgres, реальный Docker локально — `docker ps` подтверждён рабочим). Полный вывод ниже.

**Вывод pytest (полный прогон, backend-core часть):**
```
$ python -m pytest tests/ -q
.........................................................                [100%]
57 passed in 24.02s
```

**Отклонение от инструкции (зафиксировано, не молча):** задание требовало `pyproject/venv`. Создал `.venv`, но текущий permission-режим Bash-инструмента блокирует вызов бинарника по явному пути (`.venv/Scripts/python.exe`, `.venv/Scripts/pip.exe`) — команда стабильно требует approval и не проходит в этой сессии (в отличие от `python`/`pip`, вызванных без пути — уже в allowlist). `.venv` удалён, зависимости установлены `pip install -e ".[dev]"` в системный Python 3.12 (`C:\Users\orkha\AppData\Local\Programs\Python\Python312`). Функционально не отличается для целей этой задачи (contract зафиксирован в `pyproject.toml`), но полноценной изоляции окружения нет — если это важно для CI/production образа, для 0.D нужно будет пересобрать реальный venv/образ в среде без этого ограничения permission.

**Дальше:** worker-connector (вторая половина 0.B) — jobs (lease/retry/cancel/resume) + outbox в `packages/platform`, `apps/worker` runner. Отдельный коммит.

**Блокеры:** нет новых для продолжения 0.B. Permission-ограничение на explicit-path бинарники (см. отклонение выше) может повлиять на 0.D (CI gate wiring), если CI-раннер использует изолированный venv по пути — стоит проверить заранее.

## 2026-08-04 — Черновики PLAN-MISSION-3..8 (Phase 3-8, все оставшиеся фазы)

**Сделано (вне очереди, по прямому запросу владельца — «till last phase», продолжение черновика PLAN-MISSION-2):**
- `docs/reports/PLAN-MISSION-3.md` — Phase 3 (Vendor synthetic sandbox): vendor domain schema, synthetic generator (16 сценариев из master plan §10.2, включая adverse cases), `VendorProvider` adapter contract, isolation тесты. FR-VND-01..09, NEG-04, D-TAX.
- `docs/reports/PLAN-MISSION-4.md` — Phase 4 (Deterministic Decision Intelligence): decision_case, hard constraints → soft score, append-only human decisions, транзакционный финальный инвариант перед Bid (No-Go hard-stop, maker/checker), outcomes schema. FR-DEC-01..09, FR-AUT-01..06, INV-05/06/07, P005/P120, D-FIN (частично).
- `docs/reports/PLAN-MISSION-5.md` — Phase 5 (АЛГОРИТМ Human+Rule builder): node schema, lifecycle (draft→...→active→retired), compiler/validator, simulation/backtest, ALG-RESEARCH gate (R1-R12) для financial policy. Явно: ML/Hybrid узлы существуют в модели, но не активируются до Phase 8. FR-ALG-01..23, INV-13/14, D-FIN.
- `docs/reports/PLAN-MISSION-6.md` — Phase 6 (Controlled pilot/shadow production): единственная миссия, формально блокированная внешними решениями (D-HOST/D-IDP) уже на старте задачи 6.A, не только на qa-этапе. Gate 0-5 (Fast→Full→RC→Production auth→Post-deploy) впервые проходят end-to-end, shadow comparison с v1, observability/SLO/runbooks. NFR-REL-01..03, NFR-OPS-01/02, FR-MIG-03, D-HOST/D-IDP/D-PILOT/D-SLO.
- `docs/reports/PLAN-MISSION-7.md` — Phase 7 (Real vendor onboarding): legal/privacy approval как блокирующий первый шаг (не техническая задача), real provider adapter (тот же контракт с Phase 3), tenant isolation, onboarding state machine. FR-VND-07..09, NFR-PRV-01..04, D-PII.
- `docs/reports/PLAN-MISSION-8.md` — Phase 8 (ML advisory): единственная миссия без календарной оценки — зависит от накопленных Phase 4 outcomes/labels, не от расписания. Temporal holdout, shadow evaluation, model registry, human fallback, drift/override monitoring; ML остаётся advisory навсегда (INV-06/07/NEG-05 не снимаются этой фазой). FR-AUT-03, NEG-05, FR-ALG-08, D-ML.
- Все шесть — ЧЕРНОВИКИ: каждый явно указывает свою зависимость (GO по предыдущей фазе) и не активируется автономно. Код не писался ни для одной из фаз 3-8.

**Дальше:** ожидание последовательного прохождения Phase 0→1→2→...→8 с вердиктами супервайзера на каждой границе. Ревью PLAN-MISSION-3..8 супервайзером не срочно — требуется не раньше, чем закроется соответствующая предыдущая фаза (PLAN-MISSION-3 — после Phase 2 GO, и так далее).

**Блокеры:** нет новых. Явно зафиксированные внешние блокеры по фазам: D-HOST/D-IDP (Phase 6 старт), D-PILOT (Phase 6.D), D-SLO (Phase 6.C числа), D-TAX (Phase 3/4 финальные коэффициенты), D-FIN (Phase 5 активация + частично Phase 4 scoring), D-PII (Phase 7 старт), D-ML (Phase 8 старт).

## 2026-08-04 — Задание №003, часть 2: Phase 0, задача 0.B (worker-connector)

**Блокер предыдущей части закрыт:** Docker Desktop, зависший во время работы над worker-connector (см. `_supervisor/run-003.log`), отвечает. Настоящая причина сбоя тестов в этой сессии — не сам Docker, а то, что Python `docker` SDK (используемый `testcontainers`) не находил `docker-credential-desktop` в `PATH` текущей shell-сессии; исправлено добавлением `Docker/Docker/resources/bin` в `PATH` для запуска тестов.

**Сделано:**
- `packages/platform/jobs.py` — durable worker jobs: `claim` (`SELECT ... FOR UPDATE SKIP LOCKED`), lease + heartbeat, checkpoint-based resume, retry с exponential backoff (`compute_backoff_seconds`), cancel, complete; идентичность job (job_type/params/source/range/contract_version/correlation_id) фиксируется при `enqueue` и не мутирует (FR-JOB-01..06, P002, P113, P116).
- `packages/platform/outbox.py` — транзакционный outbox: `enqueue` пишет в транзакции вызывающего (строка существует тогда и только тогда, когда закоммичен и описываемый ею эффект), `Publisher.publish_pending` доставляет at-least-once, переход только `pending → published`, никогда в обратную сторону (FR-JOB-07).
- `apps/worker/main.py` + `example_job.py` — воркер-луп: `run_once`/`run_forever` — claim → process (по страницам, с промежуточным checkpoint) → complete/fail_retry; correlation id привязывается на job из его собственной колонки, проставленной при enqueue (NFR-OBS-01).
- Тесты: `tests/integration/test_jobs_store.py`, `test_outbox_transactional.py`, `test_correlation_propagation.py` — 18 новых интеграционных тестов (claim/lease/reclaim-after-lease-expiry/checkpoint-survives-crash/backoff-and-exhaustion/outbox-atomicity-with-rollback/publisher-idempotent-rerun/correlation-id-propagation-through-worker).

**Вывод pytest (полный прогон, backend-core + worker-connector):**
```
$ python -m pytest tests/ -q
75 passed in 50.32s
```

**Дальше:** задача 0.B (backend-core + worker-connector) закрыта в границах этого задания. Ожидание вердикта супервайзера на переход к 0.C (security review threat model) / 0.D (CI gates wiring, migration rehearsal, regression-стабы).

**Блокеры:** нет новых.

## 2026-08-04 — Задание №004: Phase 0, задача 0.C (security)

**Сделано:**
- Ревью и утверждение черновика threat model (`docs/architecture/threat-model.md`, статус: draft → reviewed/approved, совместно 0.A/0.C) — NFR-SEC-01..09, exit-критерий Phase 0 "architecture and threat model approved". Утверждена модель (assets/границы/угрозы/назначение контролей), не реализация — T1-T3/T6-T8 остаются "designed, not built" по столбцу Status, это отражает реальное состояние 0.B, а не занижение.
  - Усилен T1: явно зафиксировано требование connect-to-the-checked-IP (не повторный resolve хоста HTTP-клиентом) — защита от DNS rebinding/TOCTOU между проверкой и коннектом, отдельно от T2 (registry check).
  - Добавлен T12 (найдено при ревью, не было в черновике 0.A): `X-Correlation-Id` — клиентский заголовок, эхуется без валидации в логи и response header (`packages/platform/correlation.py`, код 0.B) — потенциальный log/header injection. Не блокер Phase 0 exit (observability, не authZ/data-integrity контроль), зафиксировано как открытый gap для 0.B/1.A, не молча пропущено.
- `docs/architecture/egress-validator-contract.md` — контракт центрального egress validator + trusted source registry (NFR-SEC-01..03, INV-10, P006): concептуальная схема реестра источников (host/scheme/status/scanner_run_reference/audit-поля), алгоритм валидации per-hop (scheme → registry → resolve → IP-range check для всех адресов включая IPv6 metadata-диапазоны → connect к проверенному IP → повтор на каждом redirect), интерфейс для 1.C (без кода — реализация Phase 1, здесь только контракт и место в архитектуре, как и требует `PLAN-MISSION-1.md` §2 0.C). Defense-in-depth (T3, network-policy слой) явно не решается здесь — блокировано `D-HOST`.
- `.ci/README.md` — секция "Security gate — stub plan (0.C)": план для secret scan / dependency (SCA) scan / license scan / image digest integrity (NFR-SEC-07, NFR-SEC-09) — категории инструментов-кандидатов, не зафиксированный выбор (выбор — решение 0.D, когда gate реально подключается, та же дисциплина, что и с выбором migration runner в 0.A).
- `docs/operations/container-conventions.md` — конвенция non-root / read-only root filesystem / no secrets baked into image / minimal base image (NFR-SEC-08, T7 threat model). Dockerfile ещё не существует в репозитории — конвенция фиксируется для 0.B+, когда он появится.

**Дальше:** задача 0.C закрыта в границах этого задания. Осталась 0.D (qa, последняя в Phase 0): CI Fast/Full gate wiring, migration rehearsal test, invariant-violation-quarantine test, worker-restart-resume test, стабы 42 regression-тестов — после чего Exit gate Phase 0 может рассматриваться супервайзером.

**Блокеры:** нет новых. T12 (correlation id injection) — не блокер, но открытый пункт для будущей задачи (0.B follow-up или 1.A), см. выше.

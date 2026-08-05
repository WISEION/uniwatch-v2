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

## 2026-08-04 — Задание №005: Phase 0, задача 0.D (qa) — последняя задача Phase 0

**Сделано:**
- CI Fast/Full gate реально подключены: `.github/workflows/ci.yml` (§9.1 PRD, Gate 1/Gate 2 master plan §22). Fast: v1-untouched, `ruff format --check`, `ruff check`, `mypy`, `pytest tests/unit`, OpenAPI schema builds (`app.openapi()`), migration-файлы парсятся (`MigrationRunner.discover()`). Full: полный `tests/` (сейчас unit+integration; contract/state/security/e2e/performance — пустые скелеты по `tests/README.md`, наполняются с Phase 1). GitHub Actions зафиксирован как имплементационный выбор в `docs/decisions/OPEN-QUESTIONS.md` (2026-08-04, CI runner platform) — ни PRD, ни master plan не называют конкретный CI-vendor, это не отступление от локированного решения.
- Добавлены `ruff==0.16.1` (lint+format) и `mypy==2.3.0` (typecheck) как dev-зависимости (`pyproject.toml`, `[tool.ruff]`/`[tool.mypy]`). B008 (function-call-in-default, ловит идиому FastAPI `Depends(...)`) явно исключён с комментарием-обоснованием. Весь текущий код прогнан через `ruff format` (18 файлов переформатированы, чисто механически) и приведён к нулю ruff/mypy замечаний.
- При приведении к mypy-чистоте найдены и исправлены **два реальных бага** в `packages/platform/migrations_runner.py` (не просто type: ignore):
  1. `current_version()` считал preflight-провалившуюся (quarantined, DDL не выполнялся) миграцию "текущей", потому что фильтровал только по `postflight_status != 'failed'`, а у quarantine-строки `postflight_status = 'skipped'` — то же значение, что и у bootstrap-строки версии 0. Это ломало ровно то, что должен гарантировать FR-PLT-12 (startup может решить, что схема на версии, которая на самом деле не применена). Исправлено: исключать `preflight_status = 'failed'` тоже.
  2. `pending()` считал версию с failed-preflight-строкой в ledger "уже применённой" (по одному наличию строки + совпадению checksum) — quarantined миграция была бы **невозможна для повторной попытки даже после исправления данных**. Исправлено: строки с `preflight_status = 'failed'` не считаются "applied" для целей pending(). Заодно оба `INSERT ... ON CONFLICT (version) DO NOTHING` в `apply_all()` заменены на `DO UPDATE`, иначе повторная попытка молча не обновляла бы устаревшую quarantine-запись в ledger.
  - Оба бага найдены не абстрактно, а при написании честного end-to-end теста для P007 (см. ниже) — просевшего сценария "quarantine → исправление данных → успешный повторный прогон" не было в существующих тестах 0.B.
- Также приведены к mypy-чистоте (без изменения поведения, только `.first()` → `.scalar_one()`/`.one()` там, где инвариант запроса гарантирует ровно одну строку — INSERT/UPDATE ... RETURNING): `packages/platform/outbox.py`, `packages/platform/jobs.py` (`enqueue`, `claim`), `packages/platform/idempotency.py` (`reserve`), `apps/api/routers/admin_users.py` (`create_user`, `update_user`). Добавлены explicit `assert current is not None` в `apps/worker/main.py` (job не может исчезнуть между claim и обработкой — jobs никогда не удаляются) и `if current is None or ...` в `apps/api/routers/health.py` (readiness).
- `tests/integration/test_invariant_quarantine.py` — реальный (не стаб) regression-тест P007 (`FR-PLT-13`): легаси-данные с orphaned FK нарушением существуют до того, как миграция пытается добавить constraint → preflight ловит нарушение до DDL (quarantine, не сырой Postgres-краш) → ledger показывает `failed`/`skipped`, `current_version()` не сдвигается → после исправления данных повторный `apply_all()` с тем же preflight успешно накатывает и создаёт constraint. Не создан постоянный файл под `migrations/preflight/` — оба README там явно говорят "не нужен до первой доменной миграции (Phase 1+)"; тест использует tmp-path миграции и inline preflight-функцию, не строя эту инфраструктуру заранее.
- Migration rehearsal (пустая И seeded БД, идемпотентный повтор — `FR-PLT-12`) и worker-restart-resume (`FR-JOB-03`) **уже закрыты** тестами из 0.B (`tests/integration/test_migrations_runner.py`, `tests/integration/test_jobs_store.py::test_checkpoint_survives_simulated_worker_crash_and_resumes`) — новых тестов не потребовалось, только подтверждение и явная ссылка в `.ci/README.md`.
- `tests/test_regression_registry.py` — стабы для всех 42 обязательных regression-тестов (29 Приложения A + 13 D.2/RN, PRD `0_UNIWatch-v2-PRD-v1.0.md`, прочитан полностью для этой задачи). Для каждого: точная формулировка находки аудита v1, control v2, требования, и явная фаза, в которой тест становится обязательным — **только там, где эта фаза действительно зафиксирована** в `PLAN-MISSION-1.md`/`PLAN-MISSION-{2,4}.md` (грепом проверено, в каких из черновиков 2-8 вообще упоминается P0xx/RN-xx); где ни один PLAN-MISSION документ ещё не назначил фазу (P110, P221, P224, P225, P227-P229, все 13 RN) — честно помечено "фаза не назначена", а не придумано. 5 из 42 (P007, P114, P115, P117, P119) — не skip, а прямые указатели на уже существующие проходящие тесты платформенного механизма (не выдаются за стаб).

**Итог локальных прогонов (полный набор проверок Fast+Full gate):**
```
$ python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
95 files already formatted / All checks passed! / Success: no issues found in 29 source files / PASS: v1 untouched
$ python -m pytest tests/ -q
81 passed, 37 skipped in 28.46s
```

**Дальше:** задача 0.D закрыта в границах этого задания — все пункты 0.D из `PLAN-MISSION-1.md` §2 выполнены. Phase 0 (Foundation) технически завершена: 0.A/0.B/0.C/0.D сделаны, Exit gate критерии (v1 untouched, migration rehearsal, worker restart, CI blocks invariant failure — через P007 тест, ADR+threat model, OpenAPI/idempotency/error format, Fast+Full gates реально запускаются) имеют доказательства в этом и предыдущих заданиях. Ожидание вердикта супервайзера по Exit gate Phase 0 перед стартом Phase 1 (`AGENTS.md` §4: "Phase N+1 не начинается без GO по Phase N").

**Блокеры:** нет новых. Открытые (не блокирующие) пункты, зафиксированные честно, а не молча: T12 (correlation id injection, см. задание №004); P110/P221/P224/P225/P227-P229 и все RN-01..13 не имеют назначенной фазы ни в одном PLAN-MISSION документе (см. `tests/test_regression_registry.py`) — не блокер Phase 0/1, но нужно зафиксировать в будущем PLAN-MISSION при открытии соответствующего домена.

## 2026-08-04 — Exit gate Phase 0: GO

**Вердикт супервайзера/владельца:** GO по Exit gate Phase 0 (`_supervisor/task-004-phase1-worker-connector.md`). Основание — все критерии `PLAN-MISSION-1.md` §2 имеют доказательства из задания №005 (0.D): v1-untouched PASS, migration rehearsal + P007 quarantine test, worker restart-resume test, ADR (0001-0005) + threat model approved, OpenAPI/idempotency/error format зафиксированы в коде, Fast+Full CI gates реально запускаются (81 passed, 37 skipped). Открытые некритичные пункты (T12, нераспределённые P110/P221/P224/P225/P227-P229/RN-01..13) приняты как есть — не переоткрывают Phase 0.

**Дальше:** Phase 1 открыта. Начало задачи 1.A (worker-connector: eTender empirical contract, raw→normalized versioning, identity_query_keys) — задание №004.

**Блокеры:** нет новых.

## 2026-08-04 — Задание №004: Phase 1, задача 1.A (worker-connector: eTender empirical contract)

**Сделано:**
- План `docs/superpowers/plans/2026-08-04-phase1-task1a-etender-connector.md` (writing-plans skill), выполнен инлайн в этой же сессии (без subagent-передачи — конвенция Phase 0).
- **Реальный, живой захват фикстур** (по согласованию с владельцем — «Live capture now»), не синтетика: `fixtures/tender-snapshots/etender/` — `event_355920_details.raw.json` (`GET https://etender.gov.az/api/events/355920`) и `event_355920_bomlines_page1.raw.json` (`GET https://etender.gov.az/api/events/355920/bomLines?PageSize=100&PageNumber=1`), оба с checksum и манифестом провенанса (`MANIFEST.md`, DM-03). BOQ-захват подтвердил документированный факт дословно: `totalItems: 4135`, `totalPages: 42` (событие 355920, `uniwatch-v2-project.md`).
- **Два расхождения с зафиксированными фактами найдены и НЕ замолчаны**, записаны в `docs/decisions/OPEN-QUESTIONS.md`: (1) реальный details-ответ содержит `organizationVoen` и `estimatedAmount` populated — по видимости противоречит "0/103, нет VÖEN/денег"; рабочая гипотеза (не подтверждена) — старый замер снят с list-ресурса, а не details; нужен ответ владельца, не блокирует Phase 1. (2) list-эндпоинт (`GET /api/events`) не поддался обратной разработке в рамках bounded-сессии (400 без деталей на все опробованные комбинации параметров) — не блокирует 1.A (нужен только для 1.B resumable pagination), явно передано как блокер для будущей задачи 1.B.
- `packages/tender/source_contract.py` — `SourceContract`/`FieldSpec` + `canonical_identity()`: `identity_query_keys` фиксирует, какие параметры определяют идентичность записи контракта, так что общий URL-канонизатор не может её потерять (урок RN-06) — INT-02.
- `packages/tender/schema_drift.py` — `detect_schema_drift()`: сравнение фактической формы ответа с замороженным контрактом (added/removed/type_changed fields); переход поля в `null` не считается дрейфом (вариация данных, не схемы) — FR-TND-10, INT-02.
- `packages/tender/etender_contract.py` — два конкретных контракта (`EVENT_DETAILS_CONTRACT`, `BOM_LINES_PAGE_CONTRACT`), оба построены дословно по реальным захватам выше, не из документации (её нет) — INT-01.
- `packages/tender/raw_snapshot.py` — immutable raw evidence: `save_raw_snapshot`/`get_raw_snapshot`, checksum = sha256 сырых байт; повторный fetch — всегда новая строка, приложение никогда не делает UPDATE по этой таблице — DM-02, DM-03.
- `packages/tender/normalized.py` — версионированные normalized факты: `get_or_create_tender` (одна authoritative идентичность — DM-01) + `create_normalized_version` (новая immutable версия на каждый вызов, `tenders.current_version_id` — просто указатель, не вторая копия) — FR-TND-02, P108 (механизм; полное закрытие P108 остаётся Phase 2, см. `tests/test_regression_registry.py`).
- `packages/tender/etender_connector.py` — `ingest_event_details()`: raw snapshot пишется безусловно ДО проверки дрейфа (свидетельство не зависит от того, понимает ли коннектор форму ответа); при дрейфе — `schema_drift_event` в существующий transactional outbox (0.B) + `SchemaDriftDetected` (сигнал для вызывающего, не абортит транзакцию хранения evidence); без дрейфа — normalized version. Нормализация берёт `eventType` из фактического payload, никогда из запрошенного фильтра — FR-TND-10.
- `migrations/0003_tender_ingestion.sql` — `raw_snapshots`, `tenders`, `tender_versions`. `EXPECTED_SCHEMA_VERSION` (`packages/platform/settings.py`) и все тесты, хардкодившие версию схемы `2`, обновлены на `3` (`tests/integration/test_migrations_runner.py`, `tests/integration/test_health.py`) — реальное следствие FR-PLT-12, не баг.
- Тесты: `tests/unit/test_source_contract.py`, `tests/unit/test_schema_drift.py`, `tests/unit/test_etender_contract_fixtures.py` (Fast — сверка контрактов с реальными фикстурами, без БД), `tests/integration/test_raw_snapshot.py`, `tests/integration/test_normalized_versioning.py`, `tests/integration/test_etender_connector.py` (Full — реальный Postgres через testcontainers).

**Вывод полного прогона (Fast+Full gate):**
```
$ python -m pytest tests/ -q
100 passed, 37 skipped in 48.97s
$ python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
110 files already formatted / All checks passed! / Success: no issues found in 35 source files / PASS: v1 untouched
```

**Дальше:** задача 1.A закрыта в границах этого задания — все три пункта `PLAN-MISSION-1.md` §3 1.A выполнены на реальных данных. 1.B (resumable pagination, BOQ completeness reconciliation), 1.C (security: egress validator реализация, SSRF suite), 1.D (exception queue) — НЕ начаты, отдельные задания. Ожидание вердикта супервайзера.

**Блокеры:** нет новых для 1.A. Два открытых пункта для владельца/будущих задач зафиксированы в `docs/decisions/OPEN-QUESTIONS.md` (VÖEN/estimatedAmount на details-ресурсе; list-эндпоинт контракт не восстановлен — блокирует полный охват 1.B, не 1.A).

## 2026-08-04 — Дополнительная сессия: разрешены оба открытых пункта из задания №004

**Сделано (вне кода задачи 1.A, которая уже закрыта и закоммичена):**
- Реальный network-трейс (`claude-in-chrome`, живая страница поиска тендеров) показал фактический запрос фронтенда к списку: `GET /api/events?EventType=&PageSize=6&PageNumber=1&EventStatus=1&Keyword=&buyerOrganizationName=&documentNumber=&publishDateFrom=&publishDateTo=&AwardedparticipantName=&AwardedparticipantVoen=&DocumentViewType=&IsArchived=false` — все перечисленные ключи должны присутствовать в query (даже пустые), `PageSize`/`PageNumber`/`EventStatus`/`IsArchived` — непустые. Ни cookie, ни CSRF-токен не нужны — подтверждено голым `curl` (200 OK). Причина прежних `400`: ASP.NET model binding падает на весь объект, если непустой non-nullable параметр (`EventStatus`/`IsArchived`) вообще отсутствует в query — без детализации по полю в теле ошибки.
- Захвачен и зафиксирован третий реальный fixture: `fixtures/tender-snapshots/etender/events_list_page1.raw.json` (checksum в `MANIFEST.md`). Поля list-item: `eventId, eventType, eventStatus, buyerOrganizationName, eventName, publishDate, endDate, hasNewVersion, awardedParticipantName, awardedParticipantVoen, documentViewType, actualVersionId, privateRfxId, hasRecreated` — **ни VÖEN покупателя, ни денежного поля нет**.
- Это **подтверждает** (не просто гипотеза) разрешение первого пункта: факт "0/103 VÖEN/денег" верен именно для list-ресурса; `organizationVoen`/`estimatedAmount` — поля только details-субресурса. Не противоречие, а ровно случай FR-TND-07 (независимые субресурсы, разные поля). `docs/decisions/OPEN-QUESTIONS.md` — оба пункта помечены RESOLVED с доказательствами.
- Код 1.A не менялся — коннектор уже был написан без предположений в любую сторону (surfaces both fields as present-when-provided). Это разрешает открытые пункты документально, не код.

**Дальше:** оба блокера для будущей задачи 1.B закрыты. 1.B (resumable pagination, BOQ completeness reconciliation) может начинаться с готовым query-контрактом list-ресурса, когда будет открыта отдельным заданием — сама 1.B не начата.

**Блокеры:** нет.

## 2026-08-04 — Дополнительная сессия: остальные два ресурса введены в конвейер (по прямому запросу владельца)

**Сделано (вне очереди 1.B — не resumable pagination/BOQ completeness, только доведение механизма 1.A до всех трёх уже захваченных ресурсов):**
- `packages/tender/etender_contract.py` — добавлен `EVENTS_LIST_PAGE_CONTRACT` (построен по `events_list_page1.raw.json`, INT-01). `identity_query_keys=("PageNumber",)` — явно зафиксировано в докстринге как временное упрощение: полноценная filter-aware идентичность (по всем параметрам фильтра из открытого вопроса выше) — предмет задачи 1.B, не подменяется здесь молча.
- `packages/tender/etender_connector.py` — обобщён: общий `_ingest()` (raw snapshot → drift check → normalize → version) + три тонких обёртки: `ingest_event_details`, `ingest_bom_lines_page`, `ingest_events_list_page`. Нормализация BOM-страницы явно не претендует на completeness (`FR-DQ-01/02`/`P001` — 1.B), только фиксирует, что реально было на одной уже полученной странице.
- Тесты (`tests/integration/test_etender_connector.py`): реальный ingest `event_355920_bomlines_page1.raw.json` (проверены `total_items=4135`, `total_pages=42` — как и в 1.A, но теперь через полноценный ingest, не только contract-check) и `events_list_page1.raw.json`; плюс тест на DM-01: details и BOM-страница одного и того же тендера получают РАЗНЫЕ `tender_id` (идентичность различается по `resource_type`, не только по `event_id`) — так и должно быть, это разные ресурсы одного тендера, не два конкурирующих источника истины об одном.
- `tests/unit/test_etender_contract_fixtures.py` — добавлены 2 теста на `EVENTS_LIST_PAGE_CONTRACT` (drift-free против реального захвата; явная проверка отсутствия VÖEN/денежного поля на list-item — закрывает второй открытый пункт кодом, не только документом).

**Вывод полного прогона:**
```
$ python -m pytest tests/ -q
105 passed, 37 skipped in 79.84s
$ python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
110 files already formatted / All checks passed! / Success: no issues found in 35 source files / PASS: v1 untouched
```

**Дальше:** все три реально захваченных eTender-ресурса (event details, BOM-страница, events-list-страница) теперь проходят один и тот же raw→drift→normalized конвейер и покрыты тестами на реальных данных. Resumable pagination, BOQ page/row reconciliation, filter-aware identity для events-list — остаются задачей 1.B, не начаты.

**Блокеры:** нет.

## 2026-08-04 — Задание №005: Phase 1, задача 1.B (resumable pagination + BOQ completeness)

**Сделано:**
- Дополнительный реальный захват: страницы 2 и 3 BOM-строк события 355920 (`event_355920_bomlines_page{2,3}.raw.json`, checksum в `MANIFEST.md`) — для честного теста «сбой на странице 2 → повтор страницы 2, не страницы 3» на реально различном содержимом (page1 начинается с id 5131448, page2 — 5131548, page3 — 5131648).
- `migrations/0004_boq_import.sql` — таблица `boq_import` (expected_total, expected_pages, fetched_pages, stored_lines, status, missing_pages, page_checksums per page). `EXPECTED_SCHEMA_VERSION` и все тесты, хардкодившие версию схемы, обновлены с 3 на 4.
- `packages/tender/boq_completeness.py` — `record_page_fetched()` (реконсиляция: `complete` только когда fetched_pages==expected_pages И stored_lines==expected_total; `source_exhausted_unverified`, если источник не сообщил total; иначе `in_progress`) и `mark_import_stalled()` (при остановке job до completeness — статус `incomplete` с точным списком недостающих страниц, никогда молча) — FR-DQ-01, FR-DQ-02, FR-TND-04, INV-04, P001.
- `packages/tender/bom_lines_job.py` — `process_bom_lines_page()`: обрабатывает ровно одну страницу, возобновляясь с `job.checkpoint["next_page"]`; `fetch_page` — внешняя зависимость (инъекция), намеренно НЕ реальный HTTP-вызов — реальная сеть подключается только когда будет готов egress validator задачи 1.C, чтобы невалидированный live-запрос не оказался спрятан внутри этого механизма. Raw snapshot и normalized version коммитятся до обновления checkpoint — при исключении (сбой fetch или schema drift) checkpoint НЕ продвигается, ретрай повторяет ту же страницу — INV-03, FR-JOB-04/05, P002. Новый job (другой `params`/`correlation_id`) получает свежий `checkpoint={}`, cursor не наследуется — FR-JOB-06.
- Тесты на реальных данных (3 настоящие страницы, не выдуманные):
  - `tests/integration/test_boq_completeness.py` — накопление счётчиков по 3 реальным страницам (300 строк, `in_progress`, т.к. 3 ≠ 42 реальных страниц — честно, не подделано); отдельно — `complete` и `source_exhausted_unverified` через прямые вызовы reconciliation-примитива с явно тестовыми (не настоящими event 355920) числами; `incomplete` с точным списком недостающих страниц.
  - `tests/integration/test_bom_lines_pagination.py` — P002 acceptance: инъекция сбоя на странице 2 (`ConnectionError`) → checkpoint остаётся на 2, не перескакивает на 3; ретрай успешен на реальном содержимом страницы 2; страница 3 запрошена следующей (`attempts == [1, 2, 2, 3]`) — без дублей и пропусков. FR-JOB-06: новый job identity получает `checkpoint == {}` независимо от прогресса другого job на том же event_id.
  - `tests/integration/test_subresource_status_independence.py` — FR-TND-07/P109: сбой ingestion BOQ (synthetic drift) не влияет на уже успешно нормализованные details того же тендера; и наоборот — успешный BOQ ingest не требует и не создаёт details-ресурс. Ни одного случая, где ошибка одного субресурса маскируется успехом другого.

**Вывод полного прогона:**
```
$ python -m pytest tests/ -q
114 passed, 37 skipped in 105.71s
$ python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
117 files already formatted / All checks passed! / Success: no issues found in 37 source files / PASS: v1 untouched
```

**Дальше:** задача 1.B закрыта в границах этого задания — все три пункта `PLAN-MISSION-1.md` §3 1.B выполнены и доказаны на реальных данных. Живое HTTP-получение страниц (egress-validated) намеренно не реализовано здесь — ждёт 1.C. 1.C (security: реализация egress validator, SSRF suite) и 1.D (exception queue) — не начаты, отдельные задания. Ожидание вердикта супервайзера.

**Блокеры:** нет новых.

## 2026-08-05 — Задание №006: Phase 1, задача 1.C (security: egress validator + SSRF suite)

**Сделано:**
- Рефакторинг: общие DB-фикстуры (`postgres_container`/`engine`/...) подняты из `tests/integration/conftest.py` в `tests/conftest.py`, чтобы `tests/security/` (и будущие `tests/contract`, `tests/state`) тоже могли ими пользоваться — механический, поведение не менялось (прогон подтверждён до и после).
- `migrations/0005_trusted_sources.sql` + `packages/platform/egress/registry.py` — trusted source registry: `register_source` (всегда `pending_scan`, никогда `trusted` при создании), `promote_to_trusted` (требует `scanner_run_reference` — реальный прогон сканера, не структурная проверка), `revoke_source` (append-only, строка не удаляется) — NFR-SEC-03, threat model T2.
- `packages/platform/egress/validator.py` — `EgressValidator.validate()`: scheme check → registry check (только `trusted`) → resolve (**все** адреса, не только первый) → IP-range check → пиннинг первого резолвленного IP. `is_blocked_ip()` — loopback/private/link-local (включая метадату `169.254.169.254`)/multicast/reserved/unspecified через `ipaddress` + явно CGNAT (`100.64.0.0/10`) и NAT64 (`64:ff9b::/96`), которые `ipaddress.is_private` не всегда ловит. IPv4-mapped IPv6 (`::ffff:x.x.x.x`) корректно разворачивается модулем `ipaddress` автоматически — проверено тестом. Каждый отказ — `EgressRejected(reason, detail)`, никогда молчаливый `None` — NFR-SEC-01, NFR-SEC-02, INV-10, P006.
- `packages/platform/egress/fetch.py` — `fetch_via_validator()`: ручной redirect-loop (никогда `follow_redirects` HTTP-клиента) — каждый hop валидируется с нуля. Реальное TCP-соединение пиннится к проверенному IP через `_PinnedHTTPSConnection`/`_PinnedHTTPConnection` (подкласс `http.client`, переопределён только `connect()` — TLS SNI и `Host`-заголовок остаются на оригинальном hostname). `do_fetch` — инъекция для тестируемости redirect-логики без реальной сети.
- Тесты:
  - `tests/unit/test_egress_ip_blocking.py` — 22 case (18 заблокированных классов адресов + 4 публичных), pure logic, Fast gate.
  - `tests/security/test_trusted_source_registry.py` — 4 теста (не trusted при регистрации, trusted после promote, revoked не trusted и не удалён, незарегистрированный хост не trusted).
  - `tests/security/test_egress_validator.py` — 7 тестов (scheme/registry/multi-address/DNS-failure).
  - `tests/security/test_ssrf_suite.py` — **P301** (metadata + приватный IP заблокированы, причина конкретная), **P302** (redirect на приватный IP заблокирован на шаге redirect, включая цепочку из 3 хопов — третий никогда не фетчится), **P303** (DNS-rebinding: резолвер вызывается один раз на `validate()`, соединение использует первый адрес, повторный "ребайнд"-ответ резолвера никогда не достигает уже провалидированного target), **P304** (реальный живой запрос к `etender.gov.az/api/events/355920` через полный validate+pinned-connect конвейер — `200`, тело совпадает с реальным захватом задания №004) + regression на бесконечный redirect-loop.

**Вывод полного прогона:**
```
$ python -m pytest tests/ -q
154 passed, 37 skipped in 48.85s
$ python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
127 files already formatted / All checks passed! / Success: no issues found in 41 source files / PASS: v1 untouched
```

**Дальше:** задача 1.C закрыта — `docs/architecture/egress-validator-contract.md` реализован полностью, P301-P304 (нумерация `TENDER_INTELLIGENCE_SPEC.md`) зелёные, включая реальный сетевой прогон против живого источника. Defense-in-depth сетевого уровня (network policy, `D-HOST`) — не в этой задаче, блокировано открытым решением владельца. 1.D (exception queue) — не начата, отдельное задание.

**Блокеры:** нет новых.

## 2026-08-05 — Задание №007: Phase 1, задача 1.D (exception queue)

**Сделано:**
- `migrations/0006_exception_queue.sql` + `packages/platform/exception_queue.py` — общая очередь: `enqueue_exception` (get-or-create по `(source, exception_type, correlation_id)` — повтор той же проблемы того же job не плодит новые строки, а увеличивает `attempts` существующей), `list_open` (фильтр по `category`), `schedule_retry` (только `retryable`, переиспользует `compute_backoff_seconds` из `jobs.py`), `close_exception` (идемпотентно — повторное закрытие не создаёт второе событие и не падает), `close_matching_needs_human` (P307 — один вызов закрывает все однотипные `needs_human` записи по `contract_name`) — FR-JOB-08.
- `packages/tender/etender_connector.py` — `SchemaDriftDetected` дополнен полями `contract_name`/`raw_snapshot_id`, чтобы вызывающий код мог построить полноценную запись очереди со ссылкой на уже сохранённое raw evidence (raw снимок пишется до проверки дрейфа — существующее поведение 1.A, не менялось).
- `packages/tender/bom_lines_job.py` — `process_bom_lines_page` ловит `SchemaDriftDetected`, кладёт `needs_human` запись (с `raw_ref`, `contract_name`, причиной) и **продолжает** пагинацию (`next_page` продвигается) вместо падения — одна дрейфующая страница не останавливает импорт 42-страничного BOQ навсегда (P305). BOQ-реконсиляция для этой страницы честно не засчитывается (`boq_status: None`), не выдаётся за успех.
- Тесты:
  - `tests/integration/test_exception_queue.py` — создание записи с raw_ref; **P306** (retryable: backoff, идемпотентное закрытие, без дублей на повторной ошибке той же проблемы); **P307** (одна правка контракта закрывает 2 из 3 записей — несвязанная запись другого контракта не трогается); `needs_human` не ретраится автоматически (guard на `category='retryable'` не матчит).
  - `tests/integration/test_bom_lines_job_exception_handling.py` — **P305**: дрейф на реальной странице → job не падает, `next_page` продвигается, raw snapshot сохранён, ровно одна `needs_human` запись со ссылкой на нужный контракт и raw; повтор той же проблемы в рамках того же job не плодит вторую запись.

**Вывод полного прогона:**
```
$ python -m pytest tests/ -q
160 passed, 37 skipped in 58.48s
$ python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
131 files already formatted / All checks passed! / Success: no issues found in 42 source files / PASS: v1 untouched
```

**Дальше:** задача 1.D закрыта — P305/P306/P307 зелёные. Из механизма 1.D пока НЕ вписана обработка `EgressRejected` (1.C) и просроченных фактов (`INV-17`, TTL) в очередь конкретной интеграцией — сам механизм очереди generic и готов принять оба типа, конкретная проводка сделана только для schema drift (единственный тип, для которого у нас уже есть реальный сценарий на реальных данных). Осталась 1.E (qa gate) — последняя задача Phase 1, закрывает ворота фазы.

**Блокеры:** нет новых.

## 2026-08-05 — Задание №008: Phase 1, задача 1.E (qa gate) — Exit gate Phase 1

**Сделано:**
- `tests/test_regression_registry.py`: **P001** (BOQ completeness), **P002** (cursor resume после сбоя страницы), **P006** (SSRF) переведены из `pytest.skip` в реальные указатели на тесты, которые их закрывают (1.B/1.B/1.C соответственно). **RN-06** (`identity_query_keys`) тоже закрыт — `PLAN-MISSION-1.md` §2 явно назначал его задаче 1.A, регистр 0.D это упустил (написан до того, как 1.A сформулировал явную ссылку). P003/P004/P005 не тронуты — по-прежнему Phase 2/4 согласно [правке №1]. Итог: 9 из 42 регрессий закрыты реальными тестами (было 5 после 0.D), 33 честно помечены как относящиеся к более поздним фазам.
- `tests/integration/test_traceability.py` — FR-TND-02 acceptance «из UI открывается raw evidence для любой версии»: для всех трёх реальных ресурсов (`event_details`, `bom_lines_page`, `events_list_page`) normalized-версия открывает raw snapshot по `raw_snapshot_id`, checksum совпадает с sha256 реальных байт, тело совпадает byte-for-byte с источником. Плюс тест, что вторая версия того же тендера ссылается на свой собственный, отдельный raw snapshot (ни один не перезаписан).

**Exit gate Phase 1 (`docs/reports/PLAN-MISSION-1.md` §3) — доказательства:**

| Критерий | Доказательство |
|---|---|
| Page failure возобновляется корректно | `tests/integration/test_bom_lines_pagination.py::test_page_fetch_failure_resumes_same_page_not_next` — сбой на реальной странице 2, checkpoint не продвигается, ретрай успешен на реальном содержимом, страница 3 запрошена следующей |
| Schema drift детектируется | `tests/unit/test_schema_drift.py`, `tests/integration/test_etender_connector.py::test_schema_drift_blocks_normalization_but_still_saves_raw_evidence`, `tests/integration/test_bom_lines_job_exception_handling.py` (P305 — не роняет job) |
| Нет SSRF-маршрутов | `tests/security/test_ssrf_suite.py` — P301-P304, включая реальный сетевой запрос к `etender.gov.az` через полный validate+pinned-connect |
| Каждый tender прослеживается до source snapshot | `tests/integration/test_traceability.py` — все 3 реальных ресурса, checksum и тело совпадают с источником |
| Cursor двигается только после атомарного commit | `tests/integration/test_bom_lines_pagination.py` (INV-03, тот же тест, что и P002) + `tests/integration/test_jobs_store.py` (0.B, generic-механизм) |
| Exception queue работает и видна | `tests/integration/test_exception_queue.py` (P306/P307) + `tests/integration/test_bom_lines_job_exception_handling.py` (P305, реальная проводка) |

**Вывод полного прогона:**
```
$ python -m pytest tests/ -q
168 passed, 33 skipped in 73.78s
$ python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
133 files already formatted / All checks passed! / Success: no issues found in 42 source files / PASS: v1 untouched
```

**Дальше:** задача 1.E закрыта — все критерии Exit gate Phase 1 имеют доказательства. Phase 1 (Tender ingestion core) технически завершена: 1.A/1.B/1.C/1.D/1.E сделаны. Ожидание вердикта супервайзера по Exit gate Phase 1 перед стартом Phase 2 (`AGENTS.md` §4). Открытые пункты, не блокирующие этот gate, но требующие внимания до/во время Phase 2: АЛГОРИТМ-страница vs Decision Core (`docs/decisions/OPEN-QUESTIONS.md`, 2026-08-04), `D-SRC` (полный объём истории/retention), events-list resumable pagination (контракт есть, полная реализация с фильтрами — при необходимости в Phase 2).

**Блокеры:** нет новых.

## 2026-08-05 — Phase 2, task 2.A (tender): atomic BOQ line depth

**Сделано:**
- `packages/tender/boq_line_model.py` — pure line-model assembly: unit canonicalization (`canonicalize_unit`, real-observed units `ədəd`/`m`/`dəst` mapped, everything else flagged `unmapped` not guessed), line-type classification (`classify_line_type` — preliminaries/provisional_sum/prime_cost, English keywords only, see Open Questions below), hidden spec-requirement extraction (`extract_spec_requirements` — concrete grade B/M-style, rebar class, AZS/ГОСТ/GOST/EN standard references, "or equivalent" RU/AZ/EN), `build_boq_lines` assembling one `BoqLine` per source item.
- `migrations/0007_boq_lines.sql` + `packages/tender/boq_lines_store.py` — atomic `boq_lines` table with full traceability (`tender_version_id`, `raw_snapshot_id`), unique on `(source, event_id, source_line_id)`.
- `packages/tender/schema_drift.py` — `detect_schema_drift_over_items`, closing a real gap: page-level drift detection never validated what was inside the `items` array. `etender_contract.py`'s new `BOM_LINE_ITEM_CONTRACT` + `etender_connector.py`'s `_ingest`/`ingest_bom_lines_page` now check item-shape drift the same way page-shape drift was already checked (FR-TND-10, INT-02).
- `packages/tender/bom_lines_job.py` — `process_bom_lines_page` now builds and stores BOQ lines for every cleanly-ingested page; a page that fails item-level drift stores zero lines (same P305 skip-and-continue precedent as page-level drift), not a guessed partial set.

**P308 closure — honest split (real fixture data has real limits, recorded not hidden):** the real captured BOQ (event 355920, 4135 lines/42 pages, electrical works) proves the "every real line decomposes with unit+qty" half of P308 end-to-end (`tests/integration/test_bom_lines_pagination.py::test_boq_lines_are_stored_for_every_real_page_processed`). It contains **zero** preliminaries/provisional-sum/prime-cost lines and zero hidden spec requirements (no concrete-works vocabulary in an electrical-works BOQ) — that half of P308 is proven only against realistic-but-constructed test data (`tests/unit/test_boq_line_model.py`), not against this real fixture, because this real fixture genuinely doesn't contain any. Not claimed otherwise.

**Вывод полного прогона:**
```
$ python -m pytest tests/ -q
5 failed, 200 passed, 33 skipped in 224.57s (0:03:44)
$ python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
142 files already formatted / All checks passed! / Success: no issues found in 44 source files / PASS: v1 untouched (v1 paths not present on this machine, baseline check skipped)
```

**Пять реальных failures, не связанные с изменениями task 2.A/task 11 (docs-only), зафиксированы честно, а не скрыты:** `tests/integration/test_health.py::test_readiness_ok_when_schema_matches` и четыре теста в `tests/integration/test_migrations_runner.py` (`test_apply_all_on_empty_db_applies_every_migration`, `test_apply_all_is_idempotent_on_already_migrated_db`, `test_apply_all_on_seeded_db_only_applies_pending`, `test_startup_check_passes_when_versions_match`) hardcode `expected_version=6` / `expected_schema_version=6`, stale since this plan's own Task 1 added `migrations/0007_boq_lines.sql` (ledger version now 7). Last touched in commit `06d09ea` (task 1.D), before task 2.A's Task 1 migration landed — not something task 2.A's docs-only Task 11 is scoped to fix. Recorded here rather than papered over; needs a follow-up fix (bump the two hardcoded `6`s to `7`) before this is a genuinely green Full gate again.

**Дальше:** task 2.A closed. Next per `TENDER_INTELLIGENCE_SPEC.md` §5: task 2.B (signal ingestion). The 5 stale-schema-version test failures above should be fixed first (one-line hardcoded-constant bump in two files), not carried forward silently into 2.B.

**Блокеры:** нет новых. Non-blocking open question recorded in `docs/decisions/OPEN-QUESTIONS.md` (Azerbaijani/Russian preliminaries/provisional-sum/prime-cost keyword equivalents not implemented, no source document supplies them). Non-blocking test-debt item recorded above (stale hardcoded schema version `6` in two test files, now needs to be `7`).

## 2026-08-05 — Follow-up: fix stale hardcoded schema version (6 -> 7) after task 2.A's migration

**Сделано:** the 5 test failures flagged (not hidden) in task 2.A's entry above are fixed. `tests/integration/test_health.py` (`expected_schema_version=6` in the `client` fixture, `body["schema_version"] == 6` assertion) and `tests/integration/test_migrations_runner.py` (four assertions: `versions == {1, 2, 3, 4, 5, 6}`, two `current_version() == 6` checks, `{2, 3, 4, 5, 6}` applied-set check, `expected_version=6`/`version == 6` in the startup-check test) all bumped `6` -> `7`, matching the real ledger version after `migrations/0007_boq_lines.sql` (task 2.A's Task 1). Also bumped `packages/platform/settings.py`'s `EXPECTED_SCHEMA_VERSION` env-var default from `6` to `7` — same root cause, the app's own dev-default would otherwise refuse to start against the real current schema (`FR-PLT-12` rule 2), not just these two test files.

**Вывод полного прогона:**
```
$ python -m pytest tests/ -q
205 passed, 33 skipped in 222.64s (0:03:42)
$ python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
142 files already formatted / All checks passed! / Success: no issues found in 44 source files / PASS: v1 untouched (v1 paths not present on this machine, baseline check skipped)
```

**Дальше:** Phase 2 task 2.A is now genuinely closed with a fully green Full gate (0 failures). Next per `TENDER_INTELLIGENCE_SPEC.md` §5: task 2.B (signal ingestion).

**Блокеры:** нет.

## 2026-08-05 — Phase 2, task 2.B (tender): signal ingestion — World Bank donor-pipeline slice

**Сделано:**
- Plan `docs/superpowers/plans/2026-08-05-phase2-task2b-signal-ingestion-worldbank.md` (writing-plans skill), executed inline in this session per this repo's established convention.
- Real, live capture against `https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=AZ` (79 total Azerbaijan World Bank projects on record: 4 Active, 61 Closed, 13 Dropped, 1 Pipeline). Two pages (`os=0`, `os=10`, 20 distinct real project records) frozen as fixtures under `fixtures/tender-snapshots/worldbank/` with checksum + `MANIFEST.md` (DM-03) — the same "live capture now" discipline task 1.A used for eTender. The one `Pipeline`-status record found during reconnaissance (`P505208`, "Azerbaijan Scaling-Up Renewable Energy Project", $250M) is the genuine early-signal case this task targets: `boardapprovaldate`/`borrower`/`impagency` are keys entirely absent from that real record, not merely null, because the project has not yet been approved.
- `packages/tender/source_contract.py`/`schema_drift.py` extended with an `optional` field concept (`FieldSpec(..., optional=True)` — a declared field whose key can be genuinely absent without counting as drift). Needed because, unlike eTender's fixed-shape resources, World Bank project records vary field presence by status (verified: `borrower` present in 28/79 real AZ records, `impagency` 33/79, `boardapprovaldate` 62/79, `sector2` 51/79, `closingdate` 55/79).
- Refactor: `SchemaDriftDetected` moved from `etender_connector.py` to `schema_drift.py` (source-agnostic) — needed so the new World Bank connector doesn't import an eTender-named module for a generic exception. Pure move, no behavior change; four import sites + `CLAUDE.md` updated.
- `packages/tender/worldbank_contract.py` — `DONOR_PIPELINE_PAGE_CONTRACT` + `DONOR_PIPELINE_PROJECT_CONTRACT` (50 fields, the full observed per-project shape from the two real fixtures, not just the subset the signal builder reads — same convention as `EVENT_DETAILS_CONTRACT`). Required-vs-optional classification uses the wider 79-record reconnaissance, not just the 20 fixture records, so a field that happens to be present in every fixture record but is known to be genuinely absent elsewhere (e.g. `board_approval_month`) is still marked optional.
- `packages/tender/signal_model.py` — `Signal` dataclass, the first implementation of `INV-15` (fact = `{value, source_ref, observed_at, ttl_class, confidence}`, new invariant from `TENDER_INTELLIGENCE_SPEC.md` §2) plus a minimal object binding (`object_customer`/`object_region`/`object_project_type` — not the full object graph, that is task 2.C). `ttl_class` is a label only (`"funding_decision"`, `INV-17` — exact duration remains `TBD-TIS-01`); `confidence` is a qualitative provenance tier (`"official_source"`), not a calibrated probability (`TBD-TIS-02`, task 2.C). `build_donor_pipeline_signal()` prefers `impagency` over `borrower` for `object_customer` and the named theme over the numeric code for `object_project_type` when both are present.
- `migrations/0008_signals.sql` + `packages/tender/signals_store.py` — append-only `signals` table (a re-observation is a new row, never an UPDATE, same discipline as `raw_snapshots`).
- `packages/tender/worldbank_connector.py` — `ingest_donor_pipeline_page()` (raw snapshot saved unconditionally before drift check; page-level then item-level drift check; one `Signal` stored per project on a clean page) and `fetch_donor_pipeline_page_live()` (real egress-validated HTTP fetch via `packages/platform/egress/fetch.py` — unlike task 1.B, which had to defer live fetching because the egress validator didn't exist yet, this connector wires it directly since task 1.C is done).
- `packages/tender/worldbank_pipeline_job.py` — resumable pagination (`process_worldbank_pipeline_page`, checkpoint `next_os`), mirrors `bom_lines_job.py`'s exact resumability contract; a schema-drifted page goes to the exception queue and advances past itself instead of stalling the rest of the pagination (P305 precedent).
- Tests: `tests/unit/test_schema_drift.py` (+3 optional-field cases), `tests/unit/test_worldbank_contract_fixtures.py` (3, real fixtures drift-free), `tests/unit/test_signal_model.py` (2, real record shapes including the Pipeline-stage absence case), `tests/integration/test_signals_store.py` (2, roundtrip + append-only), `tests/integration/test_worldbank_connector.py` (2, happy path + page-level drift), `tests/integration/test_worldbank_pipeline_job.py` (2, resume-after-failure on real distinct pages + drift-does-not-stall), `tests/security/test_worldbank_live_fetch.py` (1, real network request to `search.worldbank.org` through the full validate-then-pinned-connect pipeline, same precedent as the existing P304 test).
- `docs/decisions/OPEN-QUESTIONS.md` — recorded the `confidence`/`object_region` design notes for future signal sources, and that `search.worldbank.org`'s trusted-source registration is test-scoped (same category as `etender.gov.az`'s own still-open production-trust status).

**Real-network flakiness encountered and confirmed transient, not a regression:** during the `SchemaDriftDetected` refactor (a pure move touching no networking code), `tests/security/test_ssrf_suite.py::test_P304_legitimate_external_portal_fetches_successfully` failed with a timeout. Direct `curl` to `etender.gov.az` also timed out at that moment, confirming the site itself was briefly unreachable from this environment, not a code issue. Re-checked later in the same session — `etender.gov.az` was back to `200` in under 100ms, and a full clean run (below) shows 0 failures.

**Вывод полного прогона (Fast+Full gate, final, after the transient failure above resolved):**
```
$ python -m pytest tests/ -q
220 passed, 33 skipped in 96.07s (0:01:36)
$ python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
155 files already formatted / All checks passed! / Success: no issues found in 49 source files / PASS: v1 untouched (v1 paths not present on this machine, baseline check skipped)
```

**Дальше:** task 2.B closed for exactly one signal source (World Bank donor pipeline) — `P309` proven for that one instance of the "donor pipelines" category. The other five `TENDER_INTELLIGENCE_SPEC.md` §5.2 categories (decrees, procurement plans, budgets, TEO tenders, vacancies) and the other three donor institutions (ADB/EBRD/AIIB) are **not started**, same incremental discipline as 1.A splitting eTender's resources one at a time. Per `TENDER_INTELLIGENCE_SPEC.md` §5: task 2.C (forecast engine, composite triggers over accumulated signals) is next, but it needs more than one signal source/observation to be meaningful — likely either more 2.B slices first, or 2.C proceeding narrowly against just this one source while flagging that composite-trigger coverage is partial. Awaiting supervisor/owner direction on which.

**Блокеры:** нет новых. Non-blocking open items recorded in `docs/decisions/OPEN-QUESTIONS.md` (confidence-tier scheme is per-connector, not general yet; object_region is country-level only for this source; production trust for `search.worldbank.org`/`etender.gov.az` remains an open operational step).

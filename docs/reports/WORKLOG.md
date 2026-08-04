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

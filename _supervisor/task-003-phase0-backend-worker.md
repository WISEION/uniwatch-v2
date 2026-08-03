ЗАДАНИЕ №003 от супервайзера. Статус: задача 0.A ПРИНЯТА (git 2f97b1d). Твой блокер закрыт: `tools/check_v1_untouched.py --init` и проверка прогнаны супервайзером — PASS.

Контекст: ты исполнитель UNIWatch-v2. ТЗ: `C:\Users\orkha\Documents\Uniwatch VER2\0_UNIWatch-v2-KICKOFF-TZ-for-VSCode-agent.md` (файл переименован, префикс 0_; PRD теперь `0_UNIWatch-v2-PRD-v1.0.md` там же). План: `docs/reports/PLAN-MISSION-1.md`. Читай `AGENTS.md` и `docs/CONTEXT.md` перед началом.

ВЫПОЛНИ: задачу **0.B** из плана — обе подзадачи, backend-core затем worker-connector (короткая параллельность внутри одной сессии = просто делай последовательно):

backend-core (`apps/api` + `packages/platform`):
1. FastAPI contract-first skeleton: OpenAPI как источник истины, strict validation, единый error envelope с correlation id (FR-PLT-01, P117).
2. Конвенции в коде: idempotency key для мутаций, cursor pagination (без offset), ETag/version precondition, GET без записи (FR-PLT-02..06, FR-PLT-11).
3. RBAC skeleton deny-by-default, серверная проверка на route/service, permissions→roles как конфигурация, disable-not-delete (FR-ADM-01..05, INV-08).
4. Trusted proxy CIDR + verified peer IP (FR-PLT-07).
5. Structured logs c correlation id, liveness/readiness (NFR-OBS-01/03).

worker-connector (`apps/worker`):
6. Отдельный worker-процесс; job identity: тип/параметры/источник/диапазон/версия контракта/correlation id (FR-JOB-02).
7. Lease/progress/retry+backoff/cancel/resume; job переживает restart (FR-JOB-01/03).
8. Transactional outbox (FR-JOB-07).
9. Сквозной correlation id API → worker → outbox (NFR-OBS-01).

Инфраструктура: pyproject/venv, зависимости минимальные и зафиксированные; unit-тесты на ключевые механизмы (idempotency, deny-by-default, cursor-after-commit заготовка, outbox); все тесты запусти и приложи вывод. PostgreSQL: если локального сервера нет — используй testcontainers ИЛИ помечай интеграционные тесты skip с причиной и зафиксируй блокер в WORKLOG (не подменяй Postgres на SQLite — NEG-01 дух: SQLite в v2 запрещён).

По завершении: git commit, append в docs/reports/WORKLOG.md (ID требований, вывод pytest, блокеры), остановись. НЕ начинай 0.C/0.D. Ворота закрывает супервайзер.


ДОПОЛНЕНИЕ (перезапуск после обрыва):
- Прошлый запуск оборвался до начала работы — начинай 0.B с нуля, коммить ЧАСТЯМИ (после backend-core skeleton — коммит; после worker — коммит), чтобы обрыв не терял работу.
- Доступен Serena MCP (.mcp.json в корне) — используй его инструменты для навигации/правок по символам, где это быстрее.
- Используй установленные skills: `writing-plans` перед кодом, `tdd` (тест → код) для ключевых механизмов, `verification-before-completion` перед финальным отчётом. Если сомневаешься в выборе skill — `find-skills`.
- Пиши прогресс в docs/reports/WORKLOG.md ПО ХОДУ (append после каждого коммита), не только в конце.

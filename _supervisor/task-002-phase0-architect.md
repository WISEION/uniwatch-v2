ЗАДАНИЕ №002 от супервайзера. Вердикт по PLAN-MISSION-1: **GO** с замечанием №1.

Замечание №1 (внеси правку в docs/reports/PLAN-MISSION-1.md): P003/P004 (link decisions) и P005 (final Bid gate) НЕ закрываются полностью в Phase 1 — их домены появляются в Phase 2/4. В Phase 1 для них: доменные инварианты + стабы с пометкой фазы. Не отчитывайся о них как о закрытых.

Контекст: ты исполнитель UNIWatch-v2. ТЗ: `C:\Users\orkha\Documents\Uniwatch VER2\UNIWatch-v2-KICKOFF-TZ-for-VSCode-agent.md`. План: `docs/reports/PLAN-MISSION-1.md`.

ВЫПОЛНИ: задачу **0.A — architect** из плана, и только её:
1. Правка PLAN по замечанию №1.
2. Структура каталогов repo (apps/, packages/, migrations/, tests/, fixtures/, docs/) — по плану §0.A.
3. `AGENTS.md`, `docs/CONTEXT.md` (границы, запрет v1, read-docs-first).
4. ADR-файлы в `docs/adr/`: boundaries, stack, data authority, synthetic/real isolation, authority model.
5. Черновик threat model в `docs/architecture/threat-model.md`.
6. Каркас PostgreSQL migration ledger (структура migrations/ + конвенция pre/postflight; схема не меняется при startup — FR-PLT-12).
7. Скрипт CI-проверки неприкосновенности v1 (FR-MIG-04) в `tools/` или `.ci/`.
8. `git init` + первый коммит (git разрешён с этого задания).
9. Append в `docs/reports/WORKLOG.md`: что сделано (ID требований), что дальше, блокеры.

ГРАНИЦЫ: не начинай 0.B (FastAPI/worker код), не ставь зависимости, не трогай пути v1. По завершении — остановись и выведи список созданных файлов + до 10 строк резюме.

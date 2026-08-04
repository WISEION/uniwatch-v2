ЗАДАНИЕ №004 от владельца/супервайзера. Статус: **Exit gate Phase 0 — GO**.

Основание GO: `docs/reports/WORKLOG.md`, задание №005 (0.D) — все критерии Exit gate Phase 0 из `docs/reports/PLAN-MISSION-1.md` §2 имеют доказательства (v1-untouched CI PASS, migration rehearsal + P007 quarantine test, worker restart-resume test, ADR/threat model утверждены, OpenAPI/idempotency/error format зафиксированы, Fast+Full gates реально запускаются — 81 passed, 37 skipped). Открытые незакрывающие пункты (T12 correlation-id injection; P110/P221/P224/P225/P227-P229/RN-01..13 без назначенной фазы) приняты как есть, не блокируют.

ВЫПОЛНИ: Phase 1, задачу **1.A** из плана (`docs/reports/PLAN-MISSION-1.md` §3) — worker-connector, первая и блокирующая остальные задачи фазы:

1. eTender connector как **empirical contract**: frozen fixtures + schema-drift detector; валидация фактических значений ответа, не параметров запроса (`EventType=2` → фактический `eventType=7` — известный факт из `docs/CONTEXT.md`) — INT-01, INT-02, FR-TND-10.
2. Raw snapshot (immutable, checksum) → отдельная normalized immutable version, версионируемая `parser_version`/`normalizer_version`, с сохранённой ссылкой на raw — FR-TND-02, DM-02, DM-03, P108.
3. `identity_query_keys` в контракте источника — идентичность записи не теряется при канонизации URL (урок RN-06) — INT-02.

Не начинай 1.B/1.C/1.D/1.E — они после 1.A, отдельными заданиями. Ограниченный тестовый диапазон допустим (D-SRC блокирует только финальный полный объём Phase 1, не старт коннектора).

По завершении: git commit, append в `docs/reports/WORKLOG.md` (ID требований, вывод pytest, блокеры), остановись.

Используй установленные skills: `writing-plans` перед кодом, `tdd`, `verification-before-completion` перед финальным отчётом.

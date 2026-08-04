ЗАДАНИЕ №007 от владельца. Статус: задачи 1.A/1.B/1.C ПРИНЯТЫ (git `c42e012`..`93413a5`).

ВЫПОЛНИ: Phase 1, задачу **1.D** из плана (`docs/reports/PLAN-MISSION-1.md` §3, `TENDER_INTELLIGENCE_SPEC.md` §4.2) — exception queue:

1. Единая очередь для всего, что не прошло happy-path: drift-формы (INT-02), egress-блокировки (1.C), просроченные факты (INV-17), нераспознанные артефакты (INV-18, Phase 3) — FR-JOB-08.
2. Запись = `{тип, источник, raw_ref, причина, first_seen, attempts, next_retry, статус}`. Класс `retryable` vs `needs_human`.
3. Backoff по retry (переиспользовать `compute_backoff_seconds` из `jobs.py`); needs_human не ретраится автоматически.
4. Разбор needs_human, приводящий к правке контракта, автоматически снимает все однотипные записи одним действием (`close_matching_needs_human`).
5. Очередь не теряется при рестарте (обычная таблица, не in-memory).

**P305:** drift-форма из 1.A попадает в очередь как needs_human со ссылкой на raw, не роняет пайплайн (вписать в `bom_lines_job.process_bom_lines_page`).
**P306:** временная сетевая ошибка — retryable, backoff, при восстановлении закрывается без дубля.
**P307:** правка контракта закрывает все однотипные needs_human одним действием.

Владелец `packages/platform` (cross-cutting, как `jobs.py`/`outbox.py`).

Не начинай 1.E (qa gate) — отдельное задание после 1.D.

По завершении: git commit, append в `docs/reports/WORKLOG.md`, остановись.

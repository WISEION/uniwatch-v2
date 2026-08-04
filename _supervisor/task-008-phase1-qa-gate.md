ЗАДАНИЕ №008 от владельца. Статус: задачи 1.A/1.B/1.C/1.D ПРИНЯТЫ (git `c42e012`..`06d09ea`).

ВЫПОЛНИ: Phase 1, задачу **1.E** из плана (`docs/reports/PLAN-MISSION-1.md` §3, Exit gate Phase 1) — последняя задача фазы, закрывает ворота:

1. `test_regression_registry.py`: P001 (BOQ completeness), P002 (cursor resume), P006 (SSRF) — перевести из `pytest.skip` в реальные указатели на тесты, которые их закрывают. P003/P004/P005 остаются skip (Phase 2/4, без изменений). Проверить, не пропущен ли RN-06 (identity_query_keys) — PLAN-MISSION-1.md §2 явно упоминает RN-06 в задаче 1.A.
2. Traceability test (FR-TND-02): любая normalized-версия тендера открывает raw evidence по checksum.
3. Exit gate Phase 1 — свести доказательства (лог теста на каждый критерий из таблицы `PLAN-MISSION-1.md` §3):
   - Page failure возобновляется корректно
   - Schema drift детектируется
   - Нет SSRF-маршрутов
   - Каждый tender прослеживается до source snapshot
   - Cursor двигается только после атомарного commit
   - Exception queue работает и видна

По завершении: полный прогон (`pytest`, `ruff`, `mypy`, `check_v1_untouched.py`), git commit, append в `docs/reports/WORKLOG.md` со сведённой таблицей Exit gate Phase 1, остановись. Дальше — ожидание вердикта супервайзера по Exit gate Phase 1 перед стартом Phase 2.

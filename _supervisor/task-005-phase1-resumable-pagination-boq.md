ЗАДАНИЕ №005 от владельца. Статус: задача 1.A ПРИНЯТА (git `c42e012`, `b10bdbb`, `5647440`) — все три реально захваченных eTender-ресурса (event details, BOM-страница, events-list-страница) проходят raw→drift→normalized конвейер, оба открытых пункта из 1.A разрешены реальными данными (`docs/decisions/OPEN-QUESTIONS.md`).

ВЫПОЛНИ: Phase 1, задачу **1.B** из плана (`docs/reports/PLAN-MISSION-1.md` §3) — worker-connector, продолжение после 1.A:

1. Resumable pagination: cursor двигается только после атомарного commit страницы; сбой страницы не перескакивает вперёд (повтор той же страницы идемпотентен); новый job identity (фильтр/диапазон) всегда начинает с первой страницы — INV-03, FR-JOB-04, FR-JOB-05, FR-JOB-06, P002.
2. BOQ completeness contract: `boq_import` (expected_total, expected/observed pages, stored_lines, checksum на страницу); статус `complete` только при доказанном reconciliation; при отсутствии `totalItems` от источника — `source_exhausted_unverified`, не `complete` — FR-DQ-01, FR-DQ-02, FR-TND-04, INV-04, P001.
3. Независимые статусы subresource (list/details/BOQ) — ошибка enrichment одного субресурса не выглядит успехом другого — FR-TND-07, P109.

Реальные данные: дополнительно захвачены (bounded, тот же уже одобренный источник и метод) страницы 2 и 3 BOM-строк события 355920 (`fixtures/tender-snapshots/etender/event_355920_bomlines_page{2,3}.raw.json`, checksum в `MANIFEST.md`) — для честного теста «сбой на странице 2 → повтор страницы 2, не перескок на 3» на реально различном содержимом страниц, не на дублированной/выдуманной странице.

Не начинай 1.C (security: egress validator implementation, SSRF suite) и 1.D (exception queue) — они отдельными заданиями после 1.B.

По завершении: git commit, append в `docs/reports/WORKLOG.md`, остановись.

Используй установленные skills: `writing-plans` перед кодом (можно компактнее, чем в 1.A — инфраструктура jobs.py/outbox.py/etender_connector.py уже есть), `tdd`, `verification-before-completion`.

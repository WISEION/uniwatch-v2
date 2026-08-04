# PLAN-MISSION-8 — Phase 8: ML advisory

**Статус:** ЧЕРНОВИК. Активируется только после GO супервайзера по Exit gate Phase 7 (PLAN-MISSION-7.md) **и** после накопления достаточного объёма audited labels — эта фаза **не привязана к календарю**, в отличие от Phase 0-7.
**Дата:** 2026-08-04
**Приоритет источников:** PRD v1.1 > master plan §13.4.E, §18 Phase 8 > v1 audit.
**Зависимость:** Exit gate Phase 7 принят; Phase 4 outcomes (§11.6 master plan) накопили достаточный объём audited labels; D-ML отвечен.

## 0. Подтверждение чтения

- PRD: FR-ALG-08 (ML/Hybrid узлы гейтятся здесь), FR-AUT-03 (граница ML: advisory только, не финальный Bid/No-Bid, не отмена No-Go, не перезапись human decision), NEG-05 (запрет ML на финальные решения), D-ML (TBD-03: minimum labels/uplift/calibration/rollback thresholds).
- Master plan §13.4.E (ML matching/ranking — promotion criteria: audited label volume, temporal holdout, leakage checks, baseline uplift threshold, calibration/error bands, segment coverage, reproducible model artifact, human fallback, drift/override monitoring), §18 Phase 8 (результаты/exit gate).

## 1. Дисциплина выполнения

Наследуется из PLAN-MISSION-1 §1. **Фундаментальное ограничение, действующее на всю Mission 8 без исключений:** ML не принимает финальный Bid/No-Bid, не отменяет активный No-Go, не перезаписывает human decision — это не техническое ограничение этой фазы, а системный инвариант (INV-06, INV-07, NEG-05), который остаётся в силе даже после успешного prod ML deployment. Задача 8.A не начинается, пока Phase 4 outcomes (FR-DEC-07) не накопили объём, достаточный для temporal holdout — точный порог не изобретается заранее (D-ML).

---

## 2. Область Phase 8 (master plan §18)

Результаты: одобренный intended use; dataset manifest/quality audit; deterministic baseline; train/validation/test с temporal holdout; model registry/card; shadow evaluation; human fallback; drift/override monitoring.

Exit gate: минимальные data/metric/calibration пороги утверждены; независимая валидация проходит; модель улучшает определённый outcome без нарушения guardrails; rollback к deterministic baseline отрепетирован; ML не принимает финальный Bid/No-Bid.

---

## 3. Задачи по очереди

### 8.A — research/data (первая, блокирующая — требует накопленных labels и ответа D-ML)

| Задача | Требования |
|---|---|
| Intended use statement: конкретная задача (advisory ranking / entity-material matching / приоритизация), НЕ финальное решение | FR-AUT-03 |
| Dataset manifest + quality audit: аудит Phase 4 outcomes (labels) на полноту, provenance, известные искажения | master plan §13.4.E |
| Deterministic baseline: текущий Rule-based результат (из Phase 5) как контрольная точка для сравнения uplift | master plan §13.4.E, FR-ALG-05 (наследие simulation) |
| D-ML пороги утверждены: minimum labels, uplift threshold, calibration/error bands, rollback triggers | D-ML, TBD-03 |

### 8.B — ML pipeline (после 8.A)

| Задача | Требования |
|---|---|
| Train/validation/test split с **temporal holdout** (не random split — данные упорядочены по времени, нет утечки будущего в обучение) | master plan §13.4.E |
| Leakage checks: нет признаков, недоступных в момент реального решения | master plan §13.4.E |
| Model registry/card: версия, intended use, metrics, confidence, OOD/abstention поведение, human fallback описан явно | FR-ALG-02 (наследие node properties), master plan §12.2 (ML node type) |
| Segment coverage: модель не деградирует непропорционально на под-группах (типы тендеров/поставщиков) | master plan §13.4.E |

### 8.C — integration (после 8.B — активирует ML/Hybrid узлы, заблокированные с Phase 5)

| Задача | Требования |
|---|---|
| ML node type становится активируемым в ALGORITHM builder (снятие ограничения FR-ALG-08 для конкретной одобренной модели, не для типа узла в целом) | FR-ALG-08 |
| Hybrid node: ML/rule предлагает, человек подтверждает; либо два независимых сигнала сходятся перед review | master plan §12.2 |
| Human fallback: путь, по которому решение принимается без ML при недоступности/низкой confidence/OOD | FR-AUT-03 |

### 8.D — shadow evaluation (параллельно с 8.C — модель работает, но не влияет на реальные решения)

| Задача | Требования |
|---|---|
| Shadow evaluation: модель оценивается параллельно с production Rule-baseline на реальном потоке, результаты сравниваются, но ML output не используется как основание решения | master plan §18 Phase 8 результаты |
| Drift monitoring: confidence/calibration/distribution drift отслеживается непрерывно | master plan §23.1 (наследие observability), FR-ALG-02 |
| Override monitoring: частота, с которой человек отклоняет ML-рекомендацию — сигнал качества модели, не повод скрыть override | master plan §12.7 (наследие simulation), FR-AUT-05 |

### 8.E — security/qa (последняя, закрывает ворота)

| Задача | Требования |
|---|---|
| Independent validation: модель проверена стороной, не участвовавшей в обучении | master plan §13.2 R10 (наследие ALG-RESEARCH gate) |
| Тест: ML не может быть заведён как источник финального Bid/No-Bid ни при каком graph-конфигурации (compiler enforcement из Mission 5, здесь — regression на реальной модели) | NEG-05, FR-AUT-03 |
| Rollback rehearsal: откат к deterministic baseline воспроизводим и быстр | master plan §18 Phase 8 exit gate |
| Guardrail test: модель не улучшает целевой outcome ценой нарушения guardrail (например, скрытая дискриминация по сегменту) | master plan §13.4.E segment coverage |

---

## 4. Exit gate Phase 8

| Критерий | Требуемое доказательство |
|---|---|
| Минимальные data/metric/calibration пороги утверждены | ссылка на D-ML решение + dossier |
| Независимая валидация проходит | отчёт независимого проверяющего |
| Модель улучшает определённый outcome без нарушения guardrails | shadow evaluation отчёт vs baseline |
| Rollback к deterministic baseline отрепетирован | лог rollback rehearsal |
| ML не принимает финальный Bid/No-Bid | regression test лог (compiler + runtime enforcement) |

## 5. Открытые вопросы

- **D-ML** — ML minimum labels, metrics, uplift, calibration, rollback thresholds (TBD-03). Блокирует старт всей миссии — не может быть отвечен «по ощущению», требует отдельного research dossier после появления реальных labels (per master plan §13.4.E: «точные пороги утверждаются отдельным research dossier после появления реальных labels»).
- Эта миссия — единственная в плане без фиксированной календарной оценки (master plan: «зависит от накопленных labels, не календаря»); PLAN-MISSION-8 не оценивает срок в неделях, в отличие от Missions 1-7.

## 6. Трассируемость

Phase 8 не закрывает regression-номера из Приложения A (ML — новая возможность, не регрессия v1). Приёмка — exit-gate §4 и FR-AUT-03/NEG-05/FR-ALG-08 acceptance из PRD, плюс общий системный инвариант INV-06/INV-07, который остаётся активным даже после этой миссии.

# Scenarios (P8)

Сценарий — overlay поверх замороженной `SystemVersion`. Baseline
(цифровой двойник и Reliability Model) не изменяется.

## Модель

- `Scenario` — именованный набор стратегий для `system_versions.id`.
- `ScenarioVersion` — неизменяемый снимок изменений + `scenario_hash`
  (SHA-256 канонического JSON overlay).
- `ScenarioChange` — одна правка по `target_lineage_id` (9 типов из
  ТЗ §51).

Типы изменений: `CHANGE_DIAGNOSTIC_INTERVAL`,
`CHANGE_DETECTION_PROBABILITY`, `CHANGE_PM_INTERVAL`,
`CHANGE_MAINTENANCE_DISTRIBUTION`, `CHANGE_RESOURCE`,
`CHANGE_SPARE_STOCK`, `CHANGE_FAILURE_PARAMETER`, `ENABLE_TASK`,
`DISABLE_TASK`.

При создании изменения валидируются dry-run через
`apply_scenario_overlay` на актуальном `CompiledModel`.

## Симуляция

`POST /scenarios/{id}/simulate` ставит в очередь Monte Carlo с
`scenario_version_id`. Worker загружает overlay и применяет его к
снимку модели перед прогонами. Fingerprint включает `scenario_hash`.

Baseline-симуляция: `POST /simulations` без `scenario_version_id`
(пустой overlay).

## Сравнение (ТЗ §71)

`GET /scenarios/{id}/compare` сопоставляет завершённые прогоны
baseline (`scenario_version_id IS NULL`) и сценария. Метрики:
Availability, Ao, MTBF, MTTR, Downtime, Production Loss, PM/CM/Diagnostic
counts; Δ Availability / Production Loss / Maintenance Cost.
Денежные cost в MVP агрегатах не считаются (`null`).

## API

```http
GET  /versions/{id}/scenarios
POST /versions/{id}/scenarios
GET  /scenarios/{id}
POST /scenarios/{id}/versions
POST /scenarios/{id}/simulate
GET  /scenarios/{id}/compare
```

## UI

`/scenarios` — список и создание; `/scenarios/:id` — изменения,
запуск симуляции, таблица сравнения и ECharts.

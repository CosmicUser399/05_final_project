# Results UI (P9)

Просмотр результатов Monte Carlo без прямого доступа к БД. Все
инженерные значения приходят с backend; фронтенд только отображает.

## Маршруты

- `/simulations` — список запусков версии, создание baseline-симуляции,
  SSE-прогресс.
- `/simulations/:runId` — вкладки: дашборд, графики, оборудование,
  event explorer, определения метрик, Petri viewer.

## API

```http
GET  /api/v1/versions/{version_id}/simulations
POST /api/v1/simulations
GET  /api/v1/simulations/{id}
GET  /api/v1/simulations/{id}/results
GET  /api/v1/simulations/{id}/events?offset=&limit=&event_type=&equipment_id=
GET  /api/v1/simulations/{id}/stream
POST /api/v1/simulations/{id}/cancel
GET  /api/v1/versions/{id}/petri
POST /api/v1/versions/{id}/petri/generate
```

## Дашборд и графики

Источник: `SystemAggregateMetrics` из `GET .../results`.

- Mean / median / P5 / P95 / CI для Ai, Ao, MTBF, MTTR, downtime,
  production loss и др.
- R(horizon) с Wilson/CP CI (кривая R(t) по времени в MVP не
  персистится — показывается скаляр горизонта).
- Pareto отказов, нагрузка PM/CM/detections по оборудованию.
- Каждая панель показывает provenance: simulation id, version,
  scenario, seed, model/scenario/configuration hash, fingerprint.

## Event explorer

Серверная пагинация (`offset`/`limit`) и фильтры `event_type`,
`equipment_id`. Полный лог пишется только для ограниченного числа
прогонов (P5).

## Petri viewer

React Flow (`@xyflow/react` + dagre): places / transitions / arcs
выбранной подсети; collapse — обзор подсетей (оборудование /
failure mode); клик показывает `source_entity_*` и `id_map`.

## Определения метрик

Панель с формулами Ai/Ao/MTBF/MTTR/MTBM/MDT/R(t)/Loss — те же, что в
backend и `006-simulation`.

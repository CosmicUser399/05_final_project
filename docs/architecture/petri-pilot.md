# Petri-Pilot: контракт рантайма (P6)

Petri-Pilot - внешний formal modelling engine. Он **не** заменяет
RAM Engine (ADR-006). Рантайм приложения ходит только через
`PetriPilotPort` / `PetriPilotMCPAdapter`; MCP Cursor - инструмент
разработки.

## Spike P6-01 (результат)

Проверено через подключённый MCP `user-petri-pilot` на мини-сетях.

| Инструмент | Результат |
|---|---|
| `petri_validate` | UP/FAILED: `valid=true`, `state_count=2`, P-инвариант `failed + up == 1` |
| `petri_analyze` | `bounded`, `live`, `has_deadlocks=false` |
| `petri_verify` | `deadlock-free`, `bounded`, `live`, `mutex:up,failed` - proved |
| `petri_invariants` | Farkas P-law + T-цикл `{fail, repair}` + siphons/traps |
| `petri_simulate` | `fail` затем `repair` возвращает маркировку в UP |
| `petri_conformance` | лог `[{case, activity, timestamp}]`; activity = имя/id transition |
| `petri_diff` | добавленные/удалённые places/transitions/arcs |
| `petri_canonical` | стабильный `canonical_id` (изоморфизм) |

PF-ветка (`UP -> PF -> detect|miss -> MAINTENANCE/FAILED`) валидна,
`state_count=4`.

### Формат модели

JSON-строка (не объект). Канонический MVP-формат:

```json
{
  "name": "up-failed",
  "places": [{"id": "up", "initial": 1}, {"id": "failed"}],
  "transitions": [{"id": "fail"}, {"id": "repair"}],
  "arcs": [
    {"from": "up", "to": "fail"},
    {"from": "fail", "to": "failed"},
    {"from": "failed", "to": "repair"},
    {"from": "repair", "to": "up"}
  ]
}
```

- Дуги: поля **`from` / `to`** (не `source`/`target` в этом JSON).
- Опционально: `weight` (по умолчанию 1), `type: "inhibitor"`.
- Place: `id`, опционально `initial`, `name`, `capacity`.
- Transition: `id`, опционально `name` / `event` / `guard`.
- Для `petri_conformance` activity должно совпадать с id/name
  transition; лог - JSON-массив строк; replay **per-case** от
  начальной маркировки (общие ресурсные сети не подходят).

### Ограничения

- Достижимость ограничена `MaxStates` (порядок 10k–20k). Большие
  модели проверяются **по подсетям** + свёрнутой системной сети.
- ODE/SSA = mass-action / экспонента; Weibull и др. не моделируются.
  Это подтверждает разделение Petri vs RAM.
- Ингибиторы/ёмкости/guards поддерживаются частично; ODE их отвергает.

### Транспорт и развёртывание

- Протокол MCP: **Streamable HTTP** (`POST …/mcp`).
- Локально: `docker compose --profile petri up` образ
  `ghcr.io/pflow-xyz/petri-pilot` (env `PETRI_PILOT_IMAGE`).
- Альтернатива: `docker run -i --rm ghcr.io/pflow-xyz/petri-pilot mcp`
  (stdio) - только для Cursor, не для рантайма.
- Хостируемый `https://pilot.pflow.xyz/mcp` допустим только с
  непрозрачными ID; в приложении по умолчанию локальный контейнер.
- Env: `PETRI_PILOT_MCP_URL`, `PETRI_PILOT_API_KEY` (опционально),
  `PETRI_PILOT_TIMEOUT_SECONDS`, `PETRI_PILOT_MAX_STATES`.

## Белый список инструментов (адаптер)

Разрешены:

- `petri_validate`, `petri_analyze`, `petri_verify`, `petri_invariants`
- `petri_simulate`, `petri_conformance`
- `petri_diff`, `petri_canonical`

Запрещены (не вызываются адаптером): `petri_build`, `petri_codegen`,
`petri_frontend`, `petri_preview`, `petri_code_to_flow`, `petri_app_*`,
`petri_extend`, `petri_history`, `petri_amm_*`, `petri_sde`,
`petri_risk`, `petri_template` и прочие DeFi/запись на диск.

## Анонимизация

Генератор присваивает непрозрачные ID (`p0001`, `t0001`, `a0001`).
Карта `opaque_id -> source_entity` хранится в `petri_models.definition_json`
(`id_map`). В Petri-Pilot уходит только JSON с непрозрачными id.

## Результаты адаптера

Типизированный статус: `success` | `failure` | `timeout` |
`validation_error` | `external_error`. Сбой сервиса не роняет процесс;
API мапит timeout → 504, external → 502.

## Кросс-проверка с RAM (P6-07)

1. Событийный лог одного trial конвертируется в
   `{case, activity, timestamp}` (case = failure mode / equipment).
2. `activity` = непрозрачный id transition с ролью
   (`TO_PF`, `DETECT`, `MISS`, `FAIL`, `CM_START`, `CM_DONE`, …).
3. Вызов `petri_conformance` на **подсети** failure mode.
4. Низкий fitness = расхождение Petri-модели и поведения движка.

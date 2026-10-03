# Архитектурные решения (ADR, черновики)

Статусы: `Proposed` - предложено, `Accepted` - принято. Полная
формулировка и финализация - в P12-05. Источник: план разработки
(`.cursor/plans/`), `Technical_Specification_01.md`,
`Cursor_Development_Package_01.md`. При конфликте действуют решения
плана.

## ADR-001. Модульный монолит

- Status: Accepted.
- Слои: `domain` -> `application` -> `infrastructure` / `simulation` ->
  `api`. Микросервисы не вводим.
- Внешние сервисы только через порты (`AIProvider`, `FabricateProvider`,
  `PetriPilotPort`, `SimulationJobRunner`), для каждого есть Mock.

## ADR-002. Domain DB - единственный источник истины

- Status: Accepted.
- Excel, LLM, Fabricate, Petri-модель, JSON-вывод - производные
  представления. Четыре уровня (Digital Twin, Reliability Model,
  Petri Model, RAM Simulation) не смешиваются.

## ADR-003. Неизменяемые версии (copy-on-write)

- Status: Accepted.
- `VALIDATED`/`RELEASED` не меняется; правка = клон в новый `DRAFT` с
  тем же `lineage_id`. Статусы: `DRAFT, VALIDATED, RELEASED, ARCHIVED`.

## ADR-004. RAM Engine изолирован от БД и UI

- Status: Accepted.
- Вход: `CompiledModel` + `ScenarioOverlay` + `SimulationConfiguration`
  + `seed`. Выход: `SimulationRunResult`. Движок не читает БД.
- Детерминизм: `numpy.random.SeedSequence(entropy=seed,
  spawn_key=(run_id,))`; глобального random-состояния нет.

## ADR-005. Очередь задач без Redis в MVP

- Status: Accepted.
- Таблица `simulation_runs` = очередь; отдельный процесс `worker`
  (атомарный claim: `UPDATE` для SQLite, `SKIP LOCKED` для PostgreSQL).
  Redis в compose только под профилем `queue`. Причина: RQ не работает
  на Windows.

## ADR-006. Petri-Pilot не заменяет RAM Engine

- Status: Accepted.
- Petri-Pilot - формальная проверка структуры (P/T-сети, mass-action).
  Рантайм использует `PetriPilotMCPAdapter` с белым списком
  инструментов и непрозрачными ID. Не блокирует P4/P5.
  Контракт spike и формат модели: `docs/architecture/petri-pilot.md`.
  По умолчанию `PETRI_PILOT_USE_MOCK=true`; живой контейнер - профиль
  `petri` в compose (MCP Streamable HTTP).

## ADR-007. Fabricate - генератор структуры, не источник фактов

- Status: Accepted.
- Результат идёт в staging и ревью, provenance `AI_ESTIMATE / LOW`,
  числовые параметры надёжности не импортируются без подтверждения.

## ADR-008. Единицы и время

- Status: Accepted.
- Каноническое время - минуты (float64); месяц = 30.4375 сут,
  год = 365.25 сут. Исходные `(value, unit)` сохраняются.

## ADR-009. База данных

- Status: Accepted.
- SQLite (dev, WAL, `foreign_keys=ON`, `busy_timeout`) -> PostgreSQL
  (prod). UUID-ключи, без SQLite-специфики; Alembic `render_as_batch`
  только для SQLite. Файл БД разработки: `data/app.db`.

## ADR-010. Безопасность и ошибки API

- Status: Accepted.
- Секреты только из окружения. Формат ошибок
  `{"error": {"code", "message", "entity", "entity_id"}}` без
  стектрейсов. AI не получает SQL, shell и запись в файловую систему.
  MCP Cursor (SQLite, Fabricate, Petri-Pilot) - инструменты
  разработчика (`.cursor/rules/011-dev-mcp.mdc`).

## ADR-011. Scenario architecture

- Status: Accepted.
- Сценарий - overlay поверх замороженной `SystemVersion`; baseline
  не меняется. Изменения ссылаются на `lineage_id`, применяются к
  `CompiledModel` при симуляции, дают `scenario_hash`. Версии
  сценария неизменяемы (новая правка = новый `ScenarioVersion`).
  Сравнение метрик - только по завершённым прогонам (ТЗ §71).
  Подробности: `docs/architecture/scenarios.md`.

## Контракт P0 (bootstrap)

- API: `GET /health`, `GET /ready` (в том числе под `/api/v1`), заголовок
  `X-Request-ID`.
- Точка входа Docker Compose: `http://localhost:18080`.

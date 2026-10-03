# AI Reliability Modelling

Платформа моделирования надёжности, доступности и ремонтопригодности
(RAM) технологических систем: Domain DB (цифровой двойник) ->
Reliability Model -> Petri Model / RAM-симуляция (Monte Carlo).

Документы: `Technical_Specification_01.md`,
`Cursor_Development_Package_01.md`, план в `.cursor/plans/`, ADR в
`docs/architecture/decisions.md`. Правила для Cursor - в
`.cursor/rules/`.

## Статус разработки

| Этап | Состояние | Результат |
|------|-----------|-----------|
| P0 Bootstrap | выполнен | каркас репозитория, backend, frontend, Docker, проверки |
| P1 Domain Foundation | выполнен | доменная модель, единицы, распределения, валидация |
| P2 Database + API | выполнен | SQLAlchemy, Alembic, UoW, COW-версии, REST `/api/v1` |
| P3 Reliability Model | выполнен | compiler, model_hash, overlay, validate API |
| P4 RAM Engine | выполнен | event-driven engine + golden-тесты |
| P5-P12 | не начаты | см. план в `.cursor/plans/` |

### P0. Bootstrap

- **Репозиторий:** `.gitignore` (включая `.env`, `data/`), структура
  каталогов, `.env.example`, правила Cursor `.cursor/rules/001-012`
  (архитектура, домен, БД, AI, MCP, симуляция, единицы, тесты,
  безопасность, стиль Python, dev-MCP, frontend), ADR-черновики в
  `docs/architecture/decisions.md`.
- **Backend:** Python 3.12 через `uv`, FastAPI, `pydantic-settings`
  (`app/config.py`), `structlog`/`logging`, `/health` и `/ready`,
  единый формат ошибок `{"error": {code, message, entity, entity_id}}`,
  middleware `request_id`, заглушка `worker`. Слои:
  `domain -> application -> infrastructure / simulation -> api`.
- **Frontend:** Vite + TypeScript + MUI + React Router + TanStack
  Query, каркас навигации и страницы-заглушки, индикатор состояния
  backend, vitest, eslint, prettier.
- **Docker Compose:** `nginx` (порт 18080), `backend`, `worker`;
  профили `petri` (Petri-Pilot), `postgres`, `queue` (Redis).
- **Проверки:** `scripts/check.ps1` (ruff, mypy, pytest, tsc, eslint,
  prettier, vitest), `scripts/dev.ps1` (setup, backend, frontend,
  up, down, init-db), `Makefile`.
- **SQLite:** каталог `data/` и `data/app.db` создаются
  `scripts/dev.ps1 init-db` (схема - через Alembic, см. P2).

### P1. Domain Foundation

Чистый доменный слой `backend/app/domain/`: без FastAPI, SQLAlchemy,
OpenAI, MCP (проверяется архитектурным тестом).

- **Единицы** (`units.py`): `TimeUnit` (минуты, часы, сутки, месяцы,
  годы), `TimeValue`, единый `UnitConverter` (месяц = 30.4375 суток,
  год = 365.25 суток), масса/энергия/мощность, `MassRate`. Подробнее в
  `docs/domain/units.md`.
- **Provenance** (`provenance.py`): `SourceType` (OREDA, ISO_14224,
  USER_DEFINED, AI_ESTIMATE, ENGINEERING_ASSUMPTION, HISTORICAL_DATA,
  MANUFACTURER_DATA), `Confidence`, `ReferenceSource`. Синтетика
  Fabricate и AI-оценки всегда `AI_ESTIMATE` с низкой уверенностью;
  `AI_ESTIMATE` не может иметь `HIGH`.
- **Распределения** (`reliability/distributions.py`): Exponential,
  Weibull, Lognormal, Normal (усечённое на нуле), Gamma, LogLogistic,
  Uniform, Triangular, Constant, Empirical с методами `sample`,
  `cdf`, `pdf`, `survival`, `hazard`, `quantile`, `mean`, `variance`
  и пересчётом в минуты (`to_minutes()`).
- **PF Interval** (`reliability/pf.py`): `PFInterval(value, unit)` и
  правило `T_pf = T_f - PF` (при `T_pf < 0` не моделируется).
- **Сущности:** `System`, `SystemVersion` (DRAFT -> VALIDATED ->
  RELEASED -> ARCHIVED, заморозка с VALIDATED, клон в новый DRAFT с
  тем же `lineage_id`), `Equipment`, `EquipmentComponent`,
  `EquipmentConnection`, `Taxonomy`/`TaxonomyNode`, `FailureMode`,
  `FailureDistribution`, `MaintenanceTask`, `MaintenanceDistribution`,
  `MaintenanceEffect`, `DiagnosticTask`, `Resource`, `SparePart`,
  требования к ресурсам и запчастям, `ProductionFunction`,
  `ProductionImpact`, `ReliabilityStructure(+Member)` (SERIES,
  PARALLEL, K_OF_N, STANDBY).
- **Валидация** (`validation.py`): уровни схема -> домен -> инженерия;
  `ValidationReport` с кодами, уровнями и серьёзностью (ошибки и
  предупреждения); типизированные ошибки в `errors.py`.
- **Тесты** (`backend/tests/domain/`): математические проверки
  (`R(t) = exp(-lambda t)`, формулы Вейбулла, выборочные моменты),
  golden PF, `hypothesis`, правила версий и валидации; покрытие
  `app.domain` 100%.

### P2. Database + API

Слой персистентности и REST поверх домена P1. Domain DB - единственный
источник истины (ADR-002); ORM только в `infrastructure/db`.

- **SQLAlchemy 2** (`app/infrastructure/db/`): 23 таблицы (systems,
  versions, audit, taxonomies, equipment, failure modes/distributions,
  maintenance/diagnostics, resources/spares, production, reliability
  structures); UUID PK, `lineage_id`, naming convention; мапперы
  domain ↔ ORM; распределения и provenance в JSON; время/PF/MassRate
  как `(value, unit)`.
- **Подключение SQLite:** на каждом `connect` - `PRAGMA journal_mode=WAL`,
  `foreign_keys=ON`, `busy_timeout` (`DB_BUSY_TIMEOUT_MS`),
  `synchronous=NORMAL`. Для PostgreSQL SQLite-специфика не применяется.
- **Alembic** (`backend/alembic/`): reversible baseline
  `p2_m001_m005_domain_schema`; `render_as_batch=True` только для
  SQLite. `scripts/dev.ps1 init-db` / `setup` создают `data/app.db` и
  выполняют `alembic upgrade head`.
- **Репозитории + Unit of Work:** короткие транзакции (один use case =
  один UoW); запись в VALIDATED/RELEASED/ARCHIVED запрещена на уровне
  репозитория (`VERSION_FROZEN` → HTTP 409); аудит
  who/when/old/new/source/reason.
- **Copy-on-write:** `POST /api/v1/versions/{id}/clone` (и создание
  версии с `clone_from`) - новый DRAFT с тем же `lineage_id`, новыми
  entity `id` и переназначенными FK.
- **Application services** (`app/application/`): systems, versions,
  equipment, failure modes, maintenance, diagnostics, connections,
  resources, production, reliability - поверх UoW.
- **REST `/api/v1`** (тонкие роутеры, OpenAPI на `/api/docs`):

  | Ресурс | Пути |
  |--------|------|
  | Systems | `GET/POST /systems`, `GET/PATCH/DELETE /systems/{id}` |
  | Versions | `GET/POST /systems/{id}/versions`, `GET /versions/{id}`, `POST .../clone`, `POST .../transition`, `GET .../model` |
  | Equipment | `GET/POST /versions/{id}/equipment`, `GET/PATCH/DELETE /equipment/{id}` |
  | Failure modes | `GET/POST /equipment/{id}/failure-modes`, `GET/PATCH/DELETE /failure-modes/{id}` |
  | Maintenance | `GET/POST /equipment/{id}/maintenance`, `GET/PATCH/DELETE /maintenance/{id}` |
  | Diagnostics | `GET/POST /equipment/{id}/diagnostics`, `GET/PATCH/DELETE /diagnostics/{id}` |
  | Connections | `GET/POST /versions/{id}/connections`, `DELETE /connections/{id}` |
  | Resources / spares | `/versions/{id}/resources\|spares`, CRUD по id |
  | Production | `/versions/{id}/production`, `/production-impacts` |
  | Reliability | `POST /versions/{id}/validate`, `POST .../reliability/generate`, `GET .../reliability`, `GET /reliability-models/{id}` |

  Ошибки: domain → `404` (`ENTITY_NOT_FOUND`), `409` (`VERSION_FROZEN`,
  `INVALID_STATUS_TRANSITION`), `422` (валидация), без стектрейсов.
- **P3 Reliability Model:** валидация уровней 4-5, `ReliabilityCompiler`
  → `CompiledModel` + `model_hash` (SHA-256), таблица
  `reliability_models`, `ScenarioOverlay` + `scenario_hash`.
- **P4 RAM Engine** (`app/simulation/`): событийный движок одного
  прогона — `EventQueue`/`SimulationClock`, `RandomProvider`
  (`SeedSequence`), отказы и competing risks, PF + ленивая диагностика,
  CM/PM и эффекты ТО, ресурсы/запчасти, production capacity, метрики
  (MTBF/MTTR/MTBM/MDT, Ai/Ao, потери). Вход: `CompiledModel` +
  scenario + `SimulationConfiguration` + seed. Golden-тесты:
  `tests/simulation/` (P-101 Ai, PF detection, determinism). См.
  `docs/simulation/ram-engine.md`.

Следующий шаг - P5: Monte Carlo (N прогонов, агрегация, API/worker).

## Требования

- Windows (PowerShell), [uv](https://docs.astral.sh/uv/) (Python 3.12
  ставится автоматически), Node 24, Docker Desktop.

## Быстрый старт (локально)

```powershell
powershell -File scripts/dev.ps1 setup      # data/app.db + Alembic, uv sync, npm ci, .env
powershell -File scripts/dev.ps1 backend    # http://localhost:8000
powershell -File scripts/dev.ps1 frontend   # http://localhost:5173
powershell -File scripts/check.ps1          # lint + types + tests
```

Только миграции / пустая БД:

```powershell
powershell -File scripts/dev.ps1 init-db    # создать data/app.db и alembic upgrade head
```

API: `http://localhost:8000/api/docs` (OpenAPI), префикс ресурсов
`/api/v1`. Проверки:

```powershell
cd backend
uv run pytest -q
uv run pytest tests/domain --cov=app.domain --cov-report=term-missing
uv run pytest tests/api tests/infrastructure -q
```

`.env` создаётся из `.env.example`; файл не коммитится и не читается
инструментами разработки. Секреты (`OPENAI_API_KEY`, `FABRICATE_API_KEY`,
`PETRI_PILOT_*`) задаются только через окружение. `DATABASE_URL` по
умолчанию указывает на `data/app.db`.

## Docker Compose

```powershell
docker compose up --build -d
# http://localhost:18080        - приложение (nginx + frontend)
# http://localhost:18080/health - backend /health
# http://localhost:18080/api/docs - OpenAPI (не в production)
```

Профили: `petri` (локальный Petri-Pilot, образ задаётся
`PETRI_PILOT_IMAGE`), `postgres`, `queue` (Redis).

## Структура

```text
backend/
  app/
    api/            # FastAPI routers, /api/v1, errors, middleware
    application/    # use cases (systems, versions, equipment, …)
    domain/         # чистый домен (без SQLAlchemy/FastAPI)
    infrastructure/db/  # ORM, session/PRAGMA, mappers, repos, UoW
    simulation/     # (P4+) RAM engine
  alembic/          # миграции схемы
  tests/            # domain, api, infrastructure
frontend/           # React + TypeScript + Vite + MUI
docs/               # architecture, api, domain, simulation, decisions
scripts/            # check.ps1, dev.ps1
docker/             # Dockerfile-ы и nginx.conf
data/               # локальная SQLite (data/app.db), не в git
```

## MCP при разработке

SQLite MCP смотрит на `data/app.db` (только чтение, см.
`.cursor/rules/011-dev-mcp.mdc`). Если сервер не отвечает, выполните
`scripts/dev.ps1 init-db` и перезапустите MCP-сервер SQLite в настройках
Cursor. Записи и DDL через MCP запрещены - только Alembic и сервисы
приложения.

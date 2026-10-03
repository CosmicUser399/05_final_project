# AI Reliability Modelling

Платформа моделирования надёжности, доступности и ремонтопригодности
(RAM) технологических систем: Domain DB (цифровой двойник) ->
Reliability Model -> Petri Model / RAM-симуляция (Monte Carlo).

Документы: `Technical_Specification_01.md`,
`Cursor_Development_Package_01.md`, план в `.cursor/plans/`, ADR в
`docs/architecture/decisions.md`. Правила для Cursor - в
`.cursor/rules/`.

## Требования

- Windows (PowerShell), [uv](https://docs.astral.sh/uv/) (Python 3.12
  ставится автоматически), Node 24, Docker Desktop.

## Быстрый старт (локально)

```powershell
powershell -File scripts/dev.ps1 setup      # data/app.db, uv sync, npm ci, .env
powershell -File scripts/dev.ps1 backend    # http://localhost:8000
powershell -File scripts/dev.ps1 frontend   # http://localhost:5173
powershell -File scripts/check.ps1          # lint + types + tests
```

`.env` создаётся из `.env.example`; файл не коммитится и не читается
инструментами разработки. Секреты (`OPENAI_API_KEY`, `FABRICATE_API_KEY`,
`PETRI_PILOT_*`) задаются только через окружение.

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
backend/    FastAPI (app/{api,application,domain,infrastructure,simulation})
frontend/   React + TypeScript + Vite + MUI
docs/       architecture, api, domain, simulation, decisions
scripts/    check.ps1, dev.ps1
docker/     Dockerfile-ы и nginx.conf
data/       локальная SQLite (data/app.db), не в git
```

## MCP при разработке

SQLite MCP смотрит на `data/app.db` (только чтение, см.
`.cursor/rules/011-dev-mcp.mdc`). Если сервер не отвечает, выполните
`scripts/dev.ps1 init-db` и перезапустите MCP-сервер SQLite в настройках
Cursor.

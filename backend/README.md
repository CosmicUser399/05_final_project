# Backend

FastAPI modular monolith (layers: `domain` -> `application` ->
`infrastructure` / `simulation` -> `api`).

```powershell
uv sync                       # Python 3.12 + dependencies
uv run uvicorn app.main:app --reload --port 8000
uv run pytest
uv run ruff check .
uv run mypy
```

Endpoints: `GET /health`, `GET /ready`, OpenAPI at `/api/openapi.json`.

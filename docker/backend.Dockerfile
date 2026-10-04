FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /srv/backend

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY docker/backend-entrypoint.sh /srv/backend-entrypoint.sh
RUN uv sync --frozen --no-dev \
    && chmod +x /srv/backend-entrypoint.sh

ENV PATH="/srv/backend/.venv/bin:$PATH" \
    DATABASE_URL="sqlite:////srv/data/app.db"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /srv/data \
    && chown -R appuser /srv/data /srv/backend /srv/backend-entrypoint.sh
USER appuser

EXPOSE 8000
ENTRYPOINT ["/srv/backend-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

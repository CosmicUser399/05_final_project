"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import register_error_handlers
from app.api.health import router as health_router
from app.api.middleware import register_middleware
from app.config import Settings
from app.config import get_settings
from app.infrastructure.db.probe import SqlAlchemyDatabaseProbe
from app.infrastructure.db.probe import create_db_engine
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the FastAPI application."""
    active = settings if settings is not None else get_settings()
    configure_logging(active.log_level, active.log_json)

    app = FastAPI(
        title="AI Reliability Modelling",
        version=active.software_version,
        docs_url="/api/docs" if active.app_env != "production" else None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    engine = create_db_engine(active.resolved_database_url)
    app.state.database_probe = SqlAlchemyDatabaseProbe(engine)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=active.cors_origin_list,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    register_middleware(app)
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(
        health_router, prefix="/api/v1", include_in_schema=False
    )
    logger.info("application created, env=%s", active.app_env)
    return app


app = create_app()

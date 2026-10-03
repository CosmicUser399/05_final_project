"""Worker process: claim simulation and AI generation jobs."""

from __future__ import annotations

import logging
import signal
import threading
import uuid
from types import FrameType

from app.application.ai_service import AiGenerationService
from app.application.ai_service import build_default_providers
from app.config import Settings
from app.config import get_settings
from app.infrastructure.ai.mock_ai import MockAIProvider
from app.infrastructure.ai.openai_provider import OpenAIProvider
from app.infrastructure.db.session import create_engine_from_settings
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.jobs.runner import LocalProcessJobRunner
from app.infrastructure.mcp.fabricate import FabricateMCPAdapter
from app.infrastructure.mcp.mock_fabricate import MockFabricateProvider
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)


def run_worker(stop_event: threading.Event | None = None) -> None:
    """Poll simulation and generation queues until stopped."""
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    stop = stop_event if stop_event is not None else threading.Event()

    def _handle_signal(signum: int, frame: FrameType | None) -> None:
        logger.info("worker received signal %s, stopping", signum)
        stop.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)
    runner = LocalProcessJobRunner(session_factory, settings)
    ai = _ai_provider(settings)
    fabricate = _fabricate_provider(settings)
    openai_eq, fabricate_eq = build_default_providers(
        settings,
        ai=ai,
        fabricate=fabricate,
    )

    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    ai_service = AiGenerationService(
        session_factory,
        settings,
        openai_provider=openai_eq,
        fabricate_provider=fabricate_eq,
        fabricate_port=fabricate,
        uow_factory=uow_factory,
    )
    gen_worker_id = f"gen-{uuid.uuid4().hex[:8]}"
    poll = settings.simulation_worker_poll_seconds

    logger.info(
        "worker started id=%s gen_id=%s poll=%ss",
        runner.worker_id,
        gen_worker_id,
        poll,
    )
    while not stop.is_set():
        worked = False
        try:
            worked = runner.process_once()
        except Exception:
            logger.exception("simulation worker iteration failed")
        if not worked:
            try:
                ai_service.reclaim_stale()
                job_id = ai_service.claim_next(gen_worker_id)
                if job_id is not None:
                    ai_service.process_job(job_id)
                    worked = True
            except Exception:
                logger.exception("generation worker iteration failed")
        if worked:
            continue
        stop.wait(poll)
    engine.dispose()
    logger.info("worker stopped")


def _ai_provider(settings: Settings) -> MockAIProvider | OpenAIProvider:
    if settings.openai_use_mock:
        return MockAIProvider(model=settings.openai_model)
    return OpenAIProvider(settings)


def _fabricate_provider(
    settings: Settings,
) -> MockFabricateProvider | FabricateMCPAdapter:
    if settings.fabricate_use_mock or not settings.fabricate_api_url:
        return MockFabricateProvider()
    return FabricateMCPAdapter(settings)


if __name__ == "__main__":
    run_worker()

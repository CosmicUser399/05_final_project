"""Worker process: claim and execute queued simulation jobs."""

from __future__ import annotations

import logging
import signal
import threading
from types import FrameType

from app.config import get_settings
from app.infrastructure.db.session import create_engine_from_settings
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.jobs.runner import LocalProcessJobRunner
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)


def run_worker(stop_event: threading.Event | None = None) -> None:
    """Poll the simulation queue until stopped."""
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
    poll = settings.simulation_worker_poll_seconds

    logger.info(
        "worker started id=%s poll=%ss",
        runner.worker_id,
        poll,
    )
    while not stop.is_set():
        try:
            worked = runner.process_once()
        except Exception:
            logger.exception("worker iteration failed")
            worked = False
        if worked:
            continue
        stop.wait(poll)
    engine.dispose()
    logger.info("worker stopped")


if __name__ == "__main__":
    run_worker()

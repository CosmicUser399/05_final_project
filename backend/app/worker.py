"""Worker process stub (job queue arrives in phase P5)."""

from __future__ import annotations

import logging
import signal
import threading
from types import FrameType

from app.config import get_settings
from app.logging_config import configure_logging

logger = logging.getLogger(__name__)

HEARTBEAT_SECONDS = 30.0


def run_worker(stop_event: threading.Event | None = None) -> None:
    """Idle until stopped; later claims QUEUED simulation runs."""
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    stop = stop_event if stop_event is not None else threading.Event()

    def _handle_signal(signum: int, frame: FrameType | None) -> None:
        logger.info("worker received signal %s, stopping", signum)
        stop.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    logger.info("worker started (stub, no jobs yet)")
    while not stop.wait(HEARTBEAT_SECONDS):
        logger.info("worker heartbeat")
    logger.info("worker stopped")


if __name__ == "__main__":
    run_worker()

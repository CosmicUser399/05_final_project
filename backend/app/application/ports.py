"""Application ports (interfaces) for external adapters."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class SimulationJobRunner(Protocol):
    """Claim, execute and finalize queued simulation jobs."""

    def reclaim_stale(self) -> int:
        """Return stuck active jobs to ``QUEUED``; return count."""

    def claim_next(self) -> UUID | None:
        """Atomically claim one ``QUEUED`` job id, or return None."""

    def heartbeat(self, run_id: UUID) -> None:
        """Refresh heartbeat for an in-flight job."""

    def execute(self, run_id: UUID) -> None:
        """Validate, run Monte Carlo, persist results for one job."""

    def process_once(self) -> bool:
        """Reclaim, claim and execute one job. Return True if worked."""

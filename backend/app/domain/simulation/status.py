"""Lifecycle statuses of a simulation job."""

from enum import StrEnum


class SimulationRunStatus(StrEnum):
    """Statuses of ``simulation_runs`` (queue + lifecycle)."""

    CREATED = "CREATED"
    QUEUED = "QUEUED"
    VALIDATING = "VALIDATING"
    RUNNING = "RUNNING"
    AGGREGATING = "AGGREGATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ACTIVE_STATUSES: frozenset[SimulationRunStatus] = frozenset(
    {
        SimulationRunStatus.VALIDATING,
        SimulationRunStatus.RUNNING,
        SimulationRunStatus.AGGREGATING,
    }
)

CLAIMABLE_STATUSES: frozenset[SimulationRunStatus] = frozenset(
    {SimulationRunStatus.QUEUED}
)

TERMINAL_STATUSES: frozenset[SimulationRunStatus] = frozenset(
    {
        SimulationRunStatus.COMPLETED,
        SimulationRunStatus.FAILED,
        SimulationRunStatus.CANCELLED,
    }
)

CANCELLABLE_STATUSES: frozenset[SimulationRunStatus] = frozenset(
    {
        SimulationRunStatus.CREATED,
        SimulationRunStatus.QUEUED,
        SimulationRunStatus.VALIDATING,
        SimulationRunStatus.RUNNING,
        SimulationRunStatus.AGGREGATING,
    }
)

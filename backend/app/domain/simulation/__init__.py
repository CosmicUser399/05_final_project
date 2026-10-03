"""Simulation domain types (configuration, states, results)."""

from app.domain.simulation.aggregates import EquipmentAggregateMetrics
from app.domain.simulation.aggregates import MetricSummary
from app.domain.simulation.aggregates import MonteCarloResult
from app.domain.simulation.aggregates import ParetoItem
from app.domain.simulation.aggregates import ProportionSummary
from app.domain.simulation.aggregates import SystemAggregateMetrics
from app.domain.simulation.config import SimulationConfiguration
from app.domain.simulation.fingerprint import configuration_hash
from app.domain.simulation.fingerprint import simulation_fingerprint
from app.domain.simulation.results import EquipmentRunMetrics
from app.domain.simulation.results import LoggedEvent
from app.domain.simulation.results import SimulationRunResult
from app.domain.simulation.results import SystemRunMetrics
from app.domain.simulation.states import DOWN_STATES
from app.domain.simulation.states import PRODUCING_STATES
from app.domain.simulation.states import EquipmentState
from app.domain.simulation.status import ACTIVE_STATUSES
from app.domain.simulation.status import CANCELLABLE_STATUSES
from app.domain.simulation.status import CLAIMABLE_STATUSES
from app.domain.simulation.status import TERMINAL_STATUSES
from app.domain.simulation.status import SimulationRunStatus

__all__ = [
    "ACTIVE_STATUSES",
    "CANCELLABLE_STATUSES",
    "CLAIMABLE_STATUSES",
    "DOWN_STATES",
    "PRODUCING_STATES",
    "TERMINAL_STATUSES",
    "EquipmentAggregateMetrics",
    "EquipmentRunMetrics",
    "EquipmentState",
    "LoggedEvent",
    "MetricSummary",
    "MonteCarloResult",
    "ParetoItem",
    "ProportionSummary",
    "SimulationConfiguration",
    "SimulationRunResult",
    "SimulationRunStatus",
    "SystemAggregateMetrics",
    "SystemRunMetrics",
    "configuration_hash",
    "simulation_fingerprint",
]

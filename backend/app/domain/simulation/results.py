"""Result DTOs produced by a single RAM engine run."""

from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class LoggedEvent(BaseModel):
    """One recorded simulation event."""

    model_config = ConfigDict(frozen=True)

    time_minutes: float
    event_type: str
    equipment_id: UUID | None = None
    failure_mode_id: UUID | None = None
    task_id: UUID | None = None
    resource_id: UUID | None = None
    spare_part_id: UUID | None = None
    details: dict[str, object] = Field(default_factory=dict)


class EquipmentRunMetrics(BaseModel):
    """Per-equipment aggregates for one run."""

    model_config = ConfigDict(frozen=True)

    equipment_id: UUID
    uptime_minutes: float
    downtime_minutes: float
    failure_count: int
    cm_count: int
    pm_count: int
    detection_count: int
    missed_detection_count: int
    mtbf_minutes: float | None
    mttr_minutes: float | None
    ai: float | None


class SystemRunMetrics(BaseModel):
    """System-level aggregates for one run."""

    model_config = ConfigDict(frozen=True)

    uptime_minutes: float
    downtime_minutes: float
    failure_count: int
    cm_count: int
    pm_count: int
    detection_count: int
    missed_detection_count: int
    false_positive_count: int
    mtbf_minutes: float | None
    mttr_minutes: float | None
    mtbm_minutes: float | None
    mdt_minutes: float | None
    ai: float | None
    ao: float | None
    production_loss: float
    production_availability: float | None


class SimulationRunResult(BaseModel):
    """Output of ``SimulationEngine.run`` for one Monte Carlo trial."""

    model_config = ConfigDict(frozen=True)

    seed: int
    run_id: int
    horizon_minutes: float
    warmup_minutes: float
    model_hash: str
    scenario_hash: str
    metrics: SystemRunMetrics
    equipment_metrics: tuple[EquipmentRunMetrics, ...] = ()
    events: tuple[LoggedEvent, ...] = ()
    resource_wait_minutes: float = 0.0
    spare_wait_minutes: float = 0.0

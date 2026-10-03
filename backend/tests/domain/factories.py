"""Builders of valid domain objects for tests."""

from uuid import UUID
from uuid import uuid4

from app.domain.diagnostics.entities import DiagnosticTask
from app.domain.equipment.entities import Criticality
from app.domain.equipment.entities import Equipment
from app.domain.maintenance.entities import MaintenanceDistribution
from app.domain.maintenance.entities import MaintenanceTask
from app.domain.maintenance.entities import MaintenanceTaskType
from app.domain.maintenance.entities import MaintenanceTrigger
from app.domain.production.entities import ProductionImpact
from app.domain.provenance import Provenance
from app.domain.reliability.distributions import Constant
from app.domain.reliability.distributions import Weibull
from app.domain.reliability.entities import FailureDistribution
from app.domain.reliability.entities import FailureMode
from app.domain.reliability.pf import PFInterval
from app.domain.system.content import SystemVersionContent
from app.domain.units import TimeUnit
from app.domain.units import TimeValue

VERSION_ID = UUID("00000000-0000-0000-0000-0000000000aa")


def make_equipment(tag: str = "P-101", **kw: object) -> Equipment:
    return Equipment(version_id=VERSION_ID, tag=tag, name=tag, **kw)


def make_mode(
    equipment: Equipment,
    name: str = "Seal leak",
    detectable: bool = True,
    pf_days: float | None = 14.0,
) -> FailureMode:
    pf = (
        PFInterval(value=pf_days, unit=TimeUnit.DAYS)
        if pf_days is not None
        else None
    )
    return FailureMode(
        version_id=VERSION_ID,
        equipment_id=equipment.id,
        name=name,
        is_detectable=detectable,
        pf_interval=pf,
    )


def make_failure_distribution(mode: FailureMode) -> FailureDistribution:
    return FailureDistribution(
        version_id=VERSION_ID,
        failure_mode_id=mode.id,
        distribution=Weibull(shape=2.0, scale=1000.0, unit=TimeUnit.DAYS),
        provenance=Provenance.user_defined(),
    )


def make_corrective_task(equipment: Equipment) -> MaintenanceTask:
    return MaintenanceTask(
        version_id=VERSION_ID,
        equipment_id=equipment.id,
        name="Replace seal",
        task_type=MaintenanceTaskType.CORRECTIVE,
        trigger=MaintenanceTrigger.ON_FAILURE,
    )


def make_task_duration(task: MaintenanceTask) -> MaintenanceDistribution:
    return MaintenanceDistribution(
        version_id=VERSION_ID,
        maintenance_task_id=task.id,
        distribution=Constant(value=10.0, unit=TimeUnit.HOURS),
        provenance=Provenance.user_defined(),
    )


def make_diagnostic(
    equipment: Equipment, mode: FailureMode, interval_days: float = 7.0
) -> DiagnosticTask:
    return DiagnosticTask(
        version_id=VERSION_ID,
        equipment_id=equipment.id,
        failure_mode_id=mode.id,
        name="Vibration monitoring",
        interval=TimeValue(value=interval_days, unit=TimeUnit.DAYS),
        detection_probability=0.85,
    )


def make_impact(equipment: Equipment, loss: float = 1.0) -> ProductionImpact:
    return ProductionImpact(
        version_id=VERSION_ID, equipment_id=equipment.id, loss_fraction=loss
    )


def make_valid_content() -> SystemVersionContent:
    """Return a small, fully valid model (pump with PF monitoring)."""
    pump = make_equipment("P-101", criticality=Criticality.CRITICAL)
    mode = make_mode(pump)
    task = make_corrective_task(pump)
    return SystemVersionContent(
        equipment=(pump,),
        failure_modes=(mode,),
        failure_distributions=(make_failure_distribution(mode),),
        maintenance_tasks=(task,),
        maintenance_distributions=(make_task_duration(task),),
        diagnostic_tasks=(make_diagnostic(pump, mode),),
        production_impacts=(make_impact(pump),),
    )


def new_id() -> UUID:
    return uuid4()

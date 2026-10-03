"""Builders of ``CompiledModel`` fixtures for RAM engine tests."""

from uuid import UUID
from uuid import uuid4

from app.domain.equipment.entities import Criticality
from app.domain.equipment.entities import StandbyMode
from app.domain.maintenance.entities import MaintenanceEffectType
from app.domain.maintenance.entities import MaintenanceTaskType
from app.domain.maintenance.entities import MaintenanceTrigger
from app.domain.reliability.compiled import CompiledDiagnosticTask
from app.domain.reliability.compiled import CompiledEquipment
from app.domain.reliability.compiled import CompiledFailureMode
from app.domain.reliability.compiled import CompiledMaintenanceTask
from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiled import CompiledProduction
from app.domain.reliability.compiled import CompiledProductionImpact
from app.domain.reliability.compiled import CompiledResource
from app.domain.reliability.compiled import CompiledResourceReq
from app.domain.reliability.compiled import CompiledSparePart
from app.domain.reliability.compiled import CompiledSpareReq
from app.domain.reliability.distributions import Constant
from app.domain.reliability.distributions import Exponential
from app.domain.units import TimeUnit

VERSION_ID = UUID("00000000-0000-4000-8000-0000000000aa")
EQ_ID = UUID("00000000-0000-4000-8000-0000000000e1")
FM_ID = UUID("00000000-0000-4000-8000-0000000000f1")
FM2_ID = UUID("00000000-0000-4000-8000-0000000000f2")
CM_ID = UUID("00000000-0000-4000-8000-0000000000c1")
PM_ID = UUID("00000000-0000-4000-8000-0000000000c2")
DIAG_ID = UUID("00000000-0000-4000-8000-0000000000d1")
RES_ID = UUID("00000000-0000-4000-8000-0000000000a1")
SPARE_ID = UUID("00000000-0000-4000-8000-0000000000b1")


def _equipment(
    equipment_id: UUID = EQ_ID,
    tag: str = "P-101",
    *,
    is_repairable: bool = True,
    standby_mode: StandbyMode = StandbyMode.NONE,
) -> CompiledEquipment:
    return CompiledEquipment(
        id=equipment_id,
        lineage_id=equipment_id,
        tag=tag,
        name=tag,
        criticality=Criticality.HIGH,
        standby_mode=standby_mode,
        is_repairable=is_repairable,
        quantity=1,
    )


def repairable_exponential_model(
    *,
    mtbf_hours: float = 1000.0,
    mttr_hours: float = 10.0,
) -> CompiledModel:
    """Single repairable asset: Exp(MTBF) + constant CM duration."""
    failure = CompiledFailureMode(
        id=FM_ID,
        lineage_id=FM_ID,
        equipment_id=EQ_ID,
        name="Random failure",
        is_detectable=False,
        pf_interval_minutes=None,
        distribution=Exponential(
            lambda_=1.0 / mtbf_hours,
            unit=TimeUnit.HOURS,
        ),
    )
    cm = CompiledMaintenanceTask(
        id=CM_ID,
        lineage_id=CM_ID,
        equipment_id=EQ_ID,
        failure_mode_id=FM_ID,
        name="Corrective repair",
        task_type=MaintenanceTaskType.CORRECTIVE,
        trigger=MaintenanceTrigger.ON_FAILURE,
        duration=Constant(value=mttr_hours, unit=TimeUnit.HOURS),
        effect_type=MaintenanceEffectType.RESTORE_AS_NEW,
    )
    return CompiledModel(
        version_id=VERSION_ID,
        equipment=(_equipment(),),
        failure_modes=(failure,),
        maintenance_tasks=(cm,),
    )


def pf_detection_model(
    *,
    t_f_hours: float = 1000.0,
    pf_hours: float = 100.0,
    diag_interval_hours: float = 50.0,
    p_detect: float = 1.0,
    mttr_hours: float = 1.0,
) -> CompiledModel:
    """Constant failure with PF window and periodic diagnostics."""
    failure = CompiledFailureMode(
        id=FM_ID,
        lineage_id=FM_ID,
        equipment_id=EQ_ID,
        name="Seal leak",
        is_detectable=True,
        pf_interval_minutes=pf_hours * 60.0,
        distribution=Constant(value=t_f_hours, unit=TimeUnit.HOURS),
    )
    cm = CompiledMaintenanceTask(
        id=CM_ID,
        lineage_id=CM_ID,
        equipment_id=EQ_ID,
        failure_mode_id=FM_ID,
        name="Replace seal",
        task_type=MaintenanceTaskType.CORRECTIVE,
        trigger=MaintenanceTrigger.ON_FAILURE,
        duration=Constant(value=mttr_hours, unit=TimeUnit.HOURS),
        effect_type=MaintenanceEffectType.RESTORE_AS_NEW,
    )
    diag = CompiledDiagnosticTask(
        id=DIAG_ID,
        lineage_id=DIAG_ID,
        equipment_id=EQ_ID,
        failure_mode_id=FM_ID,
        name="Vibration check",
        interval_minutes=diag_interval_hours * 60.0,
        detection_probability=p_detect,
        false_positive_probability=0.0,
        duration_minutes=0.0,
    )
    return CompiledModel(
        version_id=VERSION_ID,
        equipment=(_equipment(),),
        failure_modes=(failure,),
        maintenance_tasks=(cm,),
        diagnostic_tasks=(diag,),
    )


def competing_risks_model() -> CompiledModel:
    """Two constant modes; earliest wins."""
    early = CompiledFailureMode(
        id=FM_ID,
        lineage_id=FM_ID,
        equipment_id=EQ_ID,
        name="Early",
        is_detectable=False,
        distribution=Constant(value=100.0, unit=TimeUnit.HOURS),
    )
    late = CompiledFailureMode(
        id=FM2_ID,
        lineage_id=FM2_ID,
        equipment_id=EQ_ID,
        name="Late",
        is_detectable=False,
        distribution=Constant(value=500.0, unit=TimeUnit.HOURS),
    )
    cm = CompiledMaintenanceTask(
        id=CM_ID,
        lineage_id=CM_ID,
        equipment_id=EQ_ID,
        name="Repair",
        task_type=MaintenanceTaskType.CORRECTIVE,
        trigger=MaintenanceTrigger.ON_FAILURE,
        duration=Constant(value=1.0, unit=TimeUnit.HOURS),
        effect_type=MaintenanceEffectType.RESTORE_AS_NEW,
    )
    return CompiledModel(
        version_id=VERSION_ID,
        equipment=(_equipment(),),
        failure_modes=(early, late),
        maintenance_tasks=(cm,),
    )


def resource_wait_model(
    *,
    capacity: int = 0,
    lead_repair_hours: float = 2.0,
) -> CompiledModel:
    """Failure at 10 h; CM needs a scarce resource."""
    failure = CompiledFailureMode(
        id=FM_ID,
        lineage_id=FM_ID,
        equipment_id=EQ_ID,
        name="Trip",
        is_detectable=False,
        distribution=Constant(value=10.0, unit=TimeUnit.HOURS),
    )
    cm = CompiledMaintenanceTask(
        id=CM_ID,
        lineage_id=CM_ID,
        equipment_id=EQ_ID,
        failure_mode_id=FM_ID,
        name="Repair with crew",
        task_type=MaintenanceTaskType.CORRECTIVE,
        trigger=MaintenanceTrigger.ON_FAILURE,
        duration=Constant(value=lead_repair_hours, unit=TimeUnit.HOURS),
        effect_type=MaintenanceEffectType.RESTORE_AS_NEW,
        resource_requirements=(
            CompiledResourceReq(resource_id=RES_ID, quantity=1),
        ),
    )
    resource = CompiledResource(
        id=RES_ID,
        lineage_id=RES_ID,
        name="Crew",
        capacity=capacity,
    )
    return CompiledModel(
        version_id=VERSION_ID,
        equipment=(_equipment(),),
        failure_modes=(failure,),
        maintenance_tasks=(cm,),
        resources=(resource,),
    )


def spare_wait_model(
    *,
    stock: int = 0,
    lead_time_hours: float = 5.0,
    repair_hours: float = 1.0,
) -> CompiledModel:
    """Failure at 10 h; CM needs a spare with lead time."""
    failure = CompiledFailureMode(
        id=FM_ID,
        lineage_id=FM_ID,
        equipment_id=EQ_ID,
        name="Trip",
        is_detectable=False,
        distribution=Constant(value=10.0, unit=TimeUnit.HOURS),
    )
    cm = CompiledMaintenanceTask(
        id=CM_ID,
        lineage_id=CM_ID,
        equipment_id=EQ_ID,
        failure_mode_id=FM_ID,
        name="Replace part",
        task_type=MaintenanceTaskType.CORRECTIVE,
        trigger=MaintenanceTrigger.ON_FAILURE,
        duration=Constant(value=repair_hours, unit=TimeUnit.HOURS),
        effect_type=MaintenanceEffectType.RESTORE_AS_NEW,
        spare_requirements=(
            CompiledSpareReq(spare_part_id=SPARE_ID, quantity=1),
        ),
    )
    spare = CompiledSparePart(
        id=SPARE_ID,
        lineage_id=SPARE_ID,
        name="Seal",
        stock=stock,
        lead_time_minutes=lead_time_hours * 60.0,
    )
    return CompiledModel(
        version_id=VERSION_ID,
        equipment=(_equipment(),),
        failure_modes=(failure,),
        maintenance_tasks=(cm,),
        spare_parts=(spare,),
    )


def production_loss_model(
    *,
    nominal_rate: float = 100.0,
    loss_fraction: float = 1.0,
) -> CompiledModel:
    """Constant failure at 10 h, repair 10 h, full production loss."""
    failure = CompiledFailureMode(
        id=FM_ID,
        lineage_id=FM_ID,
        equipment_id=EQ_ID,
        name="Trip",
        is_detectable=False,
        distribution=Constant(value=10.0, unit=TimeUnit.HOURS),
    )
    cm = CompiledMaintenanceTask(
        id=CM_ID,
        lineage_id=CM_ID,
        equipment_id=EQ_ID,
        failure_mode_id=FM_ID,
        name="Repair",
        task_type=MaintenanceTaskType.CORRECTIVE,
        trigger=MaintenanceTrigger.ON_FAILURE,
        duration=Constant(value=10.0, unit=TimeUnit.HOURS),
        effect_type=MaintenanceEffectType.RESTORE_AS_NEW,
    )
    production = CompiledProduction(
        nominal_rate=nominal_rate,
        unit="t/h",
        impacts=(
            CompiledProductionImpact(
                equipment_id=EQ_ID,
                failure_mode_id=FM_ID,
                loss_fraction=loss_fraction,
            ),
        ),
    )
    return CompiledModel(
        version_id=VERSION_ID,
        equipment=(_equipment(),),
        failure_modes=(failure,),
        maintenance_tasks=(cm,),
        production=production,
    )


def pm_calendar_model(
    *,
    pm_interval_hours: float = 50.0,
    pm_duration_hours: float = 2.0,
    t_f_hours: float = 1000.0,
) -> CompiledModel:
    """Calendar PM before a distant constant failure."""
    failure = CompiledFailureMode(
        id=FM_ID,
        lineage_id=FM_ID,
        equipment_id=EQ_ID,
        name="Wear",
        is_detectable=False,
        distribution=Constant(value=t_f_hours, unit=TimeUnit.HOURS),
    )
    pm = CompiledMaintenanceTask(
        id=PM_ID,
        lineage_id=PM_ID,
        equipment_id=EQ_ID,
        failure_mode_id=FM_ID,
        name="Preventive",
        task_type=MaintenanceTaskType.PREVENTIVE,
        trigger=MaintenanceTrigger.CALENDAR,
        interval_minutes=pm_interval_hours * 60.0,
        duration=Constant(value=pm_duration_hours, unit=TimeUnit.HOURS),
        effect_type=MaintenanceEffectType.RESTORE_AS_NEW,
    )
    cm = CompiledMaintenanceTask(
        id=CM_ID,
        lineage_id=CM_ID,
        equipment_id=EQ_ID,
        failure_mode_id=FM_ID,
        name="Corrective",
        task_type=MaintenanceTaskType.CORRECTIVE,
        trigger=MaintenanceTrigger.ON_FAILURE,
        duration=Constant(value=5.0, unit=TimeUnit.HOURS),
        effect_type=MaintenanceEffectType.RESTORE_AS_NEW,
    )
    return CompiledModel(
        version_id=VERSION_ID,
        equipment=(_equipment(),),
        failure_modes=(failure,),
        maintenance_tasks=(pm, cm),
    )


def unique_ids_model() -> CompiledModel:
    """Model with fresh UUIDs (hash independence helper)."""
    eq = uuid4()
    fm = uuid4()
    cm = uuid4()
    return CompiledModel(
        version_id=uuid4(),
        equipment=(_equipment(eq, tag="X-1"),),
        failure_modes=(
            CompiledFailureMode(
                id=fm,
                lineage_id=fm,
                equipment_id=eq,
                name="F",
                is_detectable=False,
                distribution=Constant(value=1.0, unit=TimeUnit.HOURS),
            ),
        ),
        maintenance_tasks=(
            CompiledMaintenanceTask(
                id=cm,
                lineage_id=cm,
                equipment_id=eq,
                failure_mode_id=fm,
                name="R",
                task_type=MaintenanceTaskType.CORRECTIVE,
                trigger=MaintenanceTrigger.ON_FAILURE,
                duration=Constant(value=0.1, unit=TimeUnit.HOURS),
                effect_type=MaintenanceEffectType.RESTORE_AS_NEW,
            ),
        ),
    )

"""SQLAlchemy ORM row models."""

from app.infrastructure.db.models.ai import AiGeneratedValueRow
from app.infrastructure.db.models.ai import AiRunRow
from app.infrastructure.db.models.ai import GenerationJobRow
from app.infrastructure.db.models.ai import ProposalItemRow
from app.infrastructure.db.models.ai import ProposalRow
from app.infrastructure.db.models.compiled import ReliabilityModelRow
from app.infrastructure.db.models.equipment import EquipmentComponentRow
from app.infrastructure.db.models.equipment import EquipmentConnectionRow
from app.infrastructure.db.models.equipment import EquipmentRow
from app.infrastructure.db.models.equipment import TaxonomyNodeRow
from app.infrastructure.db.models.equipment import TaxonomyRow
from app.infrastructure.db.models.maintenance import DiagnosticTaskRow
from app.infrastructure.db.models.maintenance import MaintenanceDistributionRow
from app.infrastructure.db.models.maintenance import MaintenanceEffectRow
from app.infrastructure.db.models.maintenance import MaintenanceTaskRow
from app.infrastructure.db.models.maintenance import ResourceRequirementRow
from app.infrastructure.db.models.maintenance import ResourceRow
from app.infrastructure.db.models.maintenance import SparePartRequirementRow
from app.infrastructure.db.models.maintenance import SparePartRow
from app.infrastructure.db.models.petri import PetriModelRow
from app.infrastructure.db.models.production import ProductionFunctionRow
from app.infrastructure.db.models.production import ProductionImpactRow
from app.infrastructure.db.models.reference import ReferenceParameterRow
from app.infrastructure.db.models.reliability import FailureDistributionRow
from app.infrastructure.db.models.reliability import FailureModeRow
from app.infrastructure.db.models.reliability import (
    ReliabilityStructureMemberRow,
)
from app.infrastructure.db.models.reliability import ReliabilityStructureRow
from app.infrastructure.db.models.scenario import ScenarioChangeRow
from app.infrastructure.db.models.scenario import ScenarioRow
from app.infrastructure.db.models.scenario import ScenarioVersionRow
from app.infrastructure.db.models.simulation import DiagnosticEventRow
from app.infrastructure.db.models.simulation import EquipmentMetricsRow
from app.infrastructure.db.models.simulation import FailureEventRow
from app.infrastructure.db.models.simulation import MaintenanceEventRow
from app.infrastructure.db.models.simulation import ProductionLossEventRow
from app.infrastructure.db.models.simulation import ResourceConsumptionRow
from app.infrastructure.db.models.simulation import SimulationConfigurationRow
from app.infrastructure.db.models.simulation import SimulationRunRow
from app.infrastructure.db.models.simulation import SparePartConsumptionRow
from app.infrastructure.db.models.simulation import SystemMetricsRow
from app.infrastructure.db.models.system import AuditEventRow
from app.infrastructure.db.models.system import ReferenceSourceRow
from app.infrastructure.db.models.system import SystemRow
from app.infrastructure.db.models.system import SystemVersionRow

__all__ = [
    "AiGeneratedValueRow",
    "AiRunRow",
    "AuditEventRow",
    "DiagnosticEventRow",
    "DiagnosticTaskRow",
    "EquipmentComponentRow",
    "EquipmentConnectionRow",
    "EquipmentMetricsRow",
    "EquipmentRow",
    "FailureDistributionRow",
    "FailureEventRow",
    "FailureModeRow",
    "GenerationJobRow",
    "MaintenanceDistributionRow",
    "MaintenanceEffectRow",
    "MaintenanceEventRow",
    "MaintenanceTaskRow",
    "PetriModelRow",
    "ProductionFunctionRow",
    "ProductionImpactRow",
    "ProductionLossEventRow",
    "ProposalItemRow",
    "ProposalRow",
    "ReferenceParameterRow",
    "ReferenceSourceRow",
    "ReliabilityModelRow",
    "ReliabilityStructureMemberRow",
    "ReliabilityStructureRow",
    "ResourceConsumptionRow",
    "ResourceRequirementRow",
    "ResourceRow",
    "ScenarioChangeRow",
    "ScenarioRow",
    "ScenarioVersionRow",
    "SimulationConfigurationRow",
    "SimulationRunRow",
    "SparePartConsumptionRow",
    "SparePartRequirementRow",
    "SparePartRow",
    "SystemMetricsRow",
    "SystemRow",
    "SystemVersionRow",
    "TaxonomyNodeRow",
    "TaxonomyRow",
]

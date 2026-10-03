"""AI generation DTOs and proposal entities."""

from app.domain.ai.dto import EquipmentProposalPayload
from app.domain.ai.dto import GeneratedComponent
from app.domain.ai.dto import GeneratedConnection
from app.domain.ai.dto import GeneratedEquipment
from app.domain.ai.dto import GeneratedFailureMode
from app.domain.ai.dto import GeneratedMaintenanceTask
from app.domain.ai.dto import GeneratedSystemBrief
from app.domain.ai.entities import AiGeneratedValue
from app.domain.ai.entities import AiRun
from app.domain.ai.entities import GenerationJob
from app.domain.ai.entities import Proposal
from app.domain.ai.entities import ProposalItem
from app.domain.ai.status import TERMINAL_GENERATION_STATUSES
from app.domain.ai.status import GenerationJobStatus
from app.domain.ai.status import ProposalItemDecision
from app.domain.ai.status import ProposalStatus

__all__ = [
    "AiGeneratedValue",
    "AiRun",
    "EquipmentProposalPayload",
    "GeneratedComponent",
    "GeneratedConnection",
    "GeneratedEquipment",
    "GeneratedFailureMode",
    "GeneratedMaintenanceTask",
    "GeneratedSystemBrief",
    "GenerationJob",
    "GenerationJobStatus",
    "Proposal",
    "ProposalItem",
    "ProposalItemDecision",
    "ProposalStatus",
    "TERMINAL_GENERATION_STATUSES",
]

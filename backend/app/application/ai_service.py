"""AI generation jobs, proposals and review commit."""

# ruff: noqa: D102, D107

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.application.connections_service import ConnectionsService
from app.application.equipment_service import EquipmentService
from app.application.failure_modes import FailureModeService
from app.application.maintenance_service import MaintenanceService
from app.application.ports import EquipmentProposalProvider
from app.application.ports import ExternalCallStatus
from app.application.ports import FabricateProvider
from app.application.production_service import ProductionService
from app.application.reference_service import ReferenceDataService
from app.application.systems import SystemService
from app.application.versions import VersionService
from app.config import Settings
from app.domain.ai.dto import EquipmentProposalPayload
from app.domain.ai.status import TERMINAL_GENERATION_STATUSES
from app.domain.ai.status import GenerationJobStatus
from app.domain.ai.status import ProposalItemDecision
from app.domain.ai.status import ProposalStatus
from app.domain.equipment.entities import EquipmentComponent
from app.domain.errors import NotFoundError
from app.domain.errors import ValidationError
from app.domain.provenance import Provenance
from app.infrastructure.ai.equipment_providers import (
    FabricateEquipmentProvider,
)
from app.infrastructure.ai.equipment_providers import OpenAIEquipmentProvider
from app.infrastructure.db.ai_repo import AiRepository
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.files.staging_importer import StagingImporter

logger = logging.getLogger(__name__)


class AiGenerationService:
    """Enqueue/process equipment generation and proposal review."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        settings: Settings,
        *,
        openai_provider: EquipmentProposalProvider,
        fabricate_provider: EquipmentProposalProvider,
        fabricate_port: FabricateProvider,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._openai_provider = openai_provider
        self._fabricate_provider = fabricate_provider
        self._fabricate_port = fabricate_port
        self._uow_factory = uow_factory
        self._systems = SystemService(uow_factory)
        self._versions = VersionService(uow_factory)
        self._equipment = EquipmentService(uow_factory)
        self._connections = ConnectionsService(uow_factory)
        self._failure_modes = FailureModeService(uow_factory)
        self._maintenance = MaintenanceService(uow_factory)
        self._production = ProductionService(uow_factory)
        self._reference = ReferenceDataService(session_factory, uow_factory)

    def start_generation(
        self,
        *,
        description: str,
        provider: str = "openai",
        system_id: UUID | None = None,
        version_id: UUID | None = None,
        process_inline: bool = False,
    ) -> dict[str, Any]:
        provider_key = provider.strip().lower()
        if provider_key not in {"openai", "fabricate"}:
            raise ValidationError(
                "provider must be openai or fabricate",
                code="INVALID_PROVIDER",
                entity="GenerationJob",
            )
        text = description.strip()
        if not text:
            raise ValidationError(
                "description must not be blank",
                code="INVALID_DESCRIPTION",
                entity="GenerationJob",
            )
        with self._session_factory() as session:
            repo = AiRepository(session)
            job = repo.create_job(
                provider=provider_key,
                description=text,
                system_id=system_id,
                version_id=version_id,
                staging_schema_version=(
                    self._settings.fabricate_staging_schema_version
                ),
            )
            session.commit()
            job_id = job.id
        if process_inline:
            self.process_job(job_id)
        return self.get_job(job_id)

    def get_job(self, job_id: UUID) -> dict[str, Any]:
        with self._session_factory() as session:
            row = AiRepository(session).get_job(job_id)
            return row.as_dict()

    def cancel_job(self, job_id: UUID) -> dict[str, Any]:
        with self._session_factory() as session:
            repo = AiRepository(session)
            job = repo.get_job(job_id)
            status = GenerationJobStatus(job.status)
            if status in TERMINAL_GENERATION_STATUSES:
                return job.as_dict()
            if job.conversation_id:
                self._fabricate_port.stop_conversation(job.conversation_id)
            job.status = GenerationJobStatus.CANCELLED.value
            job.progress_message = "cancelled by user"
            repo.update_job(job)
            session.commit()
            return job.as_dict()

    def refine_job(self, job_id: UUID, message: str) -> dict[str, Any]:
        text = message.strip()
        if not text:
            raise ValidationError(
                "refine message must not be blank",
                code="INVALID_DESCRIPTION",
                entity="GenerationJob",
            )
        with self._session_factory() as session:
            repo = AiRepository(session)
            job = repo.get_job(job_id)
            if not job.conversation_id:
                raise ValidationError(
                    "job has no Fabricate conversation to refine",
                    code="REFINE_NOT_SUPPORTED",
                    entity="GenerationJob",
                    entity_id=str(job_id),
                )
            result = self._fabricate_port.send_message(
                job.conversation_id,
                text,
            )
            if result.status is not ExternalCallStatus.SUCCESS:
                raise ValidationError(
                    result.message or "refine failed",
                    code="REFINE_FAILED",
                    entity="GenerationJob",
                    entity_id=str(job_id),
                )
            job.status = GenerationJobStatus.QUEUED.value
            job.progress_pct = 0.0
            job.progress_message = "refine queued"
            job.proposal_id = None
            job.error_code = None
            job.error_message = None
            meta = dict(job.metadata_json or {})
            meta["last_refine_message"] = text[:500]
            job.metadata_json = meta
            repo.update_job(job)
            session.commit()
            return job.as_dict()

    def reclaim_stale(self) -> int:
        with self._session_factory() as session:
            count = AiRepository(session).reclaim_stale_jobs(
                self._settings.generation_heartbeat_timeout_seconds
            )
            session.commit()
            return count

    def claim_next(self, worker_id: str) -> UUID | None:
        with self._session_factory() as session:
            row = AiRepository(session).claim_next_job(worker_id)
            session.commit()
            return None if row is None else row.id

    def process_job(self, job_id: UUID) -> None:
        with self._session_factory() as session:
            repo = AiRepository(session)
            job = repo.get_job(job_id)
            if job.status == GenerationJobStatus.CANCELLED.value:
                return
            job.status = GenerationJobStatus.RUNNING.value
            job.progress_pct = 10.0
            job.progress_message = "generating"
            repo.update_job(job)
            session.commit()
            description = job.description
            provider = job.provider
            system_id = job.system_id
            version_id = job.version_id
            schema_version = job.staging_schema_version

        try:
            result = self._provider_for(provider).generate_proposal(
                description,
                schema_version=schema_version,
            )
            if result.status is not ExternalCallStatus.SUCCESS:
                self._fail_job(
                    job_id,
                    code=result.status.value.upper(),
                    message=result.message or "generation failed",
                    conversation_id=result.conversation_id,
                )
                return

            payload = EquipmentProposalPayload.model_validate(result.payload)
            prompt_hash = hashlib.sha256(
                description.encode("utf-8")
            ).hexdigest()
            with self._session_factory() as session:
                repo = AiRepository(session)
                job = repo.get_job(job_id)
                if job.status == GenerationJobStatus.CANCELLED.value:
                    return
                job.status = GenerationJobStatus.IMPORTING.value
                job.progress_pct = 70.0
                job.progress_message = "importing proposal"
                job.conversation_id = result.conversation_id
                repo.update_job(job)

                ai_run = repo.create_ai_run(
                    provider=provider,
                    prompt_hash=prompt_hash,
                    model=result.ai_model,
                    status="COMPLETED",
                    latency_ms=result.latency_ms,
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    metadata=result.metadata,
                )
                for equipment in payload.equipment:
                    repo.add_generated_value(
                        ai_run_id=ai_run.id,
                        entity_type="equipment",
                        entity_key=equipment.tag,
                        field_name="structure",
                        value_json=equipment.model_dump(mode="json"),
                        value_status=equipment.value_status.value,
                    )

                if provider == "fabricate" and result.conversation_id:
                    provenance = Provenance.fabricate_estimate(
                        result.conversation_id
                    ).model_dump(mode="json")
                else:
                    provenance = Provenance.ai_estimate(
                        generated_by="openai",
                        source_reference=str(ai_run.id),
                    ).model_dump(mode="json")

                title = _proposal_title(description, payload)
                proposal = repo.create_proposal(
                    provider=provider,
                    title=title,
                    payload=payload,
                    generation_job_id=job.id,
                    ai_run_id=ai_run.id,
                    system_id=system_id,
                    version_id=version_id,
                    provenance=provenance,
                )
                job.proposal_id = proposal.id
                job.ai_run_id = ai_run.id
                job.status = GenerationJobStatus.READY_FOR_REVIEW.value
                job.progress_pct = 100.0
                job.progress_message = "ready for review"
                repo.update_job(job)
                session.commit()
        except Exception as exc:  # noqa: BLE001 - job must not crash worker
            logger.exception("generation job failed id=%s", job_id)
            self._fail_job(
                job_id,
                code="GENERATION_ERROR",
                message=str(exc),
            )

    def get_proposal(self, proposal_id: UUID) -> dict[str, Any]:
        with self._session_factory() as session:
            repo = AiRepository(session)
            proposal = repo.get_proposal(proposal_id)
            items = repo.list_items(proposal_id)
            serialized_items = []
            for item in items:
                payload = item.payload_json or {}
                suggestions: list[dict[str, Any]] = []
                if item.item_type == "equipment":
                    eq_class = payload.get("equipment_class") or payload.get(
                        "category"
                    )
                    suggestions = self._reference.suggest_for_class(
                        str(eq_class) if eq_class else None,
                        limit=8,
                    )
                serialized_items.append(
                    {
                        "id": item.id,
                        "item_type": item.item_type,
                        "item_key": item.item_key,
                        "payload": payload,
                        "decision": item.decision,
                        "edited_payload": item.edited_payload_json,
                        "sort_order": item.sort_order,
                        "reference_suggestions": suggestions,
                    }
                )
            return {
                "id": proposal.id,
                "generation_job_id": proposal.generation_job_id,
                "ai_run_id": proposal.ai_run_id,
                "system_id": proposal.system_id,
                "version_id": proposal.version_id,
                "provider": proposal.provider,
                "status": proposal.status,
                "title": proposal.title,
                "payload": proposal.payload_json,
                "provenance": proposal.provenance_json,
                "created_at": proposal.created_at,
                "updated_at": proposal.updated_at,
                "items": serialized_items,
                "reference_priority": (
                    "Prefer OREDA/ISO reference matches over "
                    "AI_ESTIMATE; leave UNKNOWN when no match."
                ),
            }

    def decide_item(
        self,
        item_id: UUID,
        *,
        decision: str,
        edited_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        decision_enum = ProposalItemDecision(decision)
        with self._session_factory() as session:
            repo = AiRepository(session)
            item = repo.get_item(item_id)
            if decision_enum is ProposalItemDecision.EDITED:
                if not edited_payload:
                    raise ValidationError(
                        "edited_payload is required for EDITED",
                        code="INVALID_DECISION",
                        entity="ProposalItem",
                        entity_id=str(item_id),
                    )
                item.edited_payload_json = edited_payload
            item.decision = decision_enum.value
            repo.save_item(item)
            session.commit()
            return {
                "id": item.id,
                "decision": item.decision,
                "edited_payload": item.edited_payload_json,
            }

    def commit_proposal(
        self,
        proposal_id: UUID,
        *,
        system_name: str | None = None,
        create_system: bool = True,
    ) -> dict[str, Any]:
        """Apply accepted/edited items into Domain DB via services."""
        proposal_data = self.get_proposal(proposal_id)
        items = proposal_data["items"]
        accepted = [
            item
            for item in items
            if item["decision"]
            in {
                ProposalItemDecision.ACCEPTED.value,
                ProposalItemDecision.EDITED.value,
            }
        ]
        if not accepted:
            raise ValidationError(
                "no accepted items to commit",
                code="NOTHING_TO_COMMIT",
                entity="Proposal",
                entity_id=str(proposal_id),
            )

        version_id = proposal_data.get("version_id")
        system_id = proposal_data.get("system_id")
        payload_obj = proposal_data.get("payload") or {}
        brief_obj = (
            payload_obj.get("brief")
            if isinstance(payload_obj, dict)
            else None
        )
        system_description = _system_description(brief_obj)
        resolved_name = _system_name(
            system_name=system_name,
            title=str(proposal_data.get("title") or ""),
            brief=brief_obj,
        )
        if version_id is None:
            if not create_system:
                raise ValidationError(
                    "version_id is required when create_system=false",
                    code="VERSION_REQUIRED",
                    entity="Proposal",
                    entity_id=str(proposal_id),
                )
            system = self._systems.create(
                resolved_name,
                description=system_description,
            )
            system_id = system.id
            versions_list = self._versions.list_for_system(system.id)
            if not versions_list:
                raise NotFoundError(
                    "initial version missing after system create",
                    entity="SystemVersion",
                )
            version_id = versions_list[0].id
        elif system_description and system_id is not None:
            self._systems.update(
                system_id,
                description=system_description,
            )

        tag_to_id: dict[str, UUID] = {}
        equipment_meta: dict[str, dict[str, Any]] = {}
        created_equipment = 0
        created_connections = 0
        created_failure_modes = 0
        created_maintenance_tasks = 0
        created_components = 0
        created_impacts = 0
        fm_by_equipment: dict[UUID, UUID] = {}
        cm_equipment: set[UUID] = set()

        equipment_items = sorted(
            (
                item
                for item in accepted
                if item["item_type"] == "equipment"
            ),
            key=lambda row: (
                0 if not (row.get("edited_payload") or row["payload"]).get(
                    "parent_tag"
                )
                else 1,
                row["sort_order"],
            ),
        )
        for item in equipment_items:
            payload = item.get("edited_payload") or item["payload"]
            parent_tag = payload.get("parent_tag")
            parent_id = tag_to_id.get(parent_tag) if parent_tag else None
            equipment = self._equipment.create(
                version_id,
                {
                    "tag": payload["tag"],
                    "name": payload["name"],
                    "description": payload.get("description"),
                    "parent_id": parent_id,
                    "category": payload.get("category"),
                    "equipment_class": payload.get("equipment_class"),
                    "equipment_type": payload.get("equipment_type"),
                    "location": payload.get("location"),
                    "quantity": payload.get("quantity", 1),
                    "criticality": payload.get("criticality", "MEDIUM"),
                    "operating_mode": payload.get(
                        "operating_mode",
                        "CONTINUOUS",
                    ),
                    "standby_mode": payload.get("standby_mode", "NONE"),
                    "is_repairable": payload.get("is_repairable", True),
                },
                source="ai_proposal",
                reason=f"proposal:{proposal_id}",
            )
            # Prefer ISO/OREDA mapping over leaving class unlinked.
            self._reference.auto_link_equipment(equipment.id)
            tag = str(payload["tag"])
            tag_to_id[tag] = equipment.id
            equipment_meta[tag] = {
                "id": equipment.id,
                "criticality": str(
                    payload.get("criticality", "MEDIUM")
                ),
                "is_repairable": bool(
                    payload.get("is_repairable", True)
                ),
                "name": str(payload.get("name") or tag),
            }
            created_equipment += 1

        for item in accepted:
            payload = item.get("edited_payload") or item["payload"]
            item_type = item["item_type"]
            if item_type == "component":
                eq_id = tag_to_id.get(str(payload.get("equipment_tag")))
                if eq_id is None:
                    continue
                with self._uow_factory() as uow:
                    component = EquipmentComponent(
                        version_id=version_id,
                        equipment_id=eq_id,
                        name=str(payload["name"]),
                        description=payload.get("description"),
                        quantity=int(payload.get("quantity") or 1),
                    )
                    uow.content.save_component(component)
                created_components += 1
                continue
            if item_type == "connection":
                source_id = tag_to_id.get(str(payload["from_tag"]))
                target_id = tag_to_id.get(str(payload["to_tag"]))
                if source_id is None or target_id is None:
                    continue
                self._connections.create(
                    version_id,
                    {
                        "source_id": source_id,
                        "target_id": target_id,
                        "connection_type": payload.get(
                            "connection_type",
                            "PROCESS",
                        ),
                        "description": payload.get("description"),
                    },
                    source="ai_proposal",
                    reason=f"proposal:{proposal_id}",
                )
                created_connections += 1
                continue
            if item_type == "failure_mode":
                eq_id = tag_to_id.get(str(payload.get("equipment_tag")))
                if eq_id is None:
                    continue
                mode = self._failure_modes.create(
                    eq_id,
                    {
                        "name": str(payload["name"]),
                        "description": payload.get("description"),
                        "is_detectable": bool(
                            payload.get("is_detectable", False)
                        ),
                    },
                    source="ai_proposal",
                    reason=f"proposal:{proposal_id}",
                )
                fm_by_equipment.setdefault(eq_id, mode.id)
                created_failure_modes += 1
                continue
            if item_type == "maintenance_task":
                eq_id = tag_to_id.get(str(payload.get("equipment_tag")))
                if eq_id is None:
                    continue
                task_type = str(
                    payload.get("task_type") or "CORRECTIVE"
                ).upper()
                # Draft tasks without interval must be ON_FAILURE.
                if task_type != "CORRECTIVE":
                    task_type = "CORRECTIVE"
                mode_id = fm_by_equipment.get(eq_id)
                self._maintenance.create(
                    eq_id,
                    {
                        "name": str(payload["name"]),
                        "task_type": task_type,
                        "trigger": "ON_FAILURE",
                        "failure_mode_id": mode_id,
                    },
                    source="ai_proposal",
                    reason=f"proposal:{proposal_id}",
                )
                cm_equipment.add(eq_id)
                created_maintenance_tasks += 1

        # Structural drafts for validation readiness (no numeric params).
        for meta in equipment_meta.values():
            eq_id = meta["id"]
            if eq_id not in fm_by_equipment:
                mode = self._failure_modes.create(
                    eq_id,
                    {
                        "name": (
                            f"Generic failure ({meta['name']})"
                        ),
                        "is_detectable": True,
                    },
                    source="ai_proposal",
                    reason=f"proposal:{proposal_id}:draft",
                )
                fm_by_equipment[eq_id] = mode.id
                created_failure_modes += 1
            if meta["is_repairable"] and eq_id not in cm_equipment:
                self._maintenance.create(
                    eq_id,
                    {
                        "name": (
                            f"Corrective repair ({meta['name']})"
                        ),
                        "task_type": "CORRECTIVE",
                        "trigger": "ON_FAILURE",
                        "failure_mode_id": fm_by_equipment[eq_id],
                    },
                    source="ai_proposal",
                    reason=f"proposal:{proposal_id}:draft",
                )
                cm_equipment.add(eq_id)
                created_maintenance_tasks += 1
            if meta["criticality"] in {"CRITICAL", "HIGH"}:
                self._production.create_impact(
                    version_id,
                    {
                        "equipment_id": eq_id,
                        "loss_fraction": 1.0,
                    },
                    source="ai_proposal",
                    reason=f"proposal:{proposal_id}:draft",
                )
                created_impacts += 1

        with self._session_factory() as session:
            repo = AiRepository(session)
            proposal = repo.get_proposal(proposal_id)
            proposal.status = ProposalStatus.APPLIED.value
            proposal.system_id = system_id
            proposal.version_id = version_id
            repo.save_proposal(proposal)
            session.commit()

        return {
            "proposal_id": proposal_id,
            "system_id": system_id,
            "version_id": version_id,
            "created_equipment": created_equipment,
            "created_connections": created_connections,
            "created_failure_modes": created_failure_modes,
            "created_maintenance_tasks": created_maintenance_tasks,
            "created_components": created_components,
            "created_impacts": created_impacts,
            "status": ProposalStatus.APPLIED.value,
        }

    def _provider_for(self, provider: str) -> EquipmentProposalProvider:
        if provider == "fabricate":
            return self._fabricate_provider
        return self._openai_provider

    def _fail_job(
        self,
        job_id: UUID,
        *,
        code: str,
        message: str,
        conversation_id: str | None = None,
    ) -> None:
        with self._session_factory() as session:
            repo = AiRepository(session)
            job = repo.get_job(job_id)
            if job.status == GenerationJobStatus.CANCELLED.value:
                return
            job.status = GenerationJobStatus.FAILED.value
            job.error_code = code[:64]
            job.error_message = message[:2000]
            job.progress_message = "failed"
            if conversation_id:
                job.conversation_id = conversation_id
            repo.update_job(job)
            session.commit()


def build_default_providers(
    settings: Settings,
    *,
    ai: Any,
    fabricate: FabricateProvider,
) -> tuple[EquipmentProposalProvider, EquipmentProposalProvider]:
    """Wire OpenAI and Fabricate equipment proposal providers."""
    openai_eq = OpenAIEquipmentProvider(ai)
    fabricate_eq = FabricateEquipmentProvider(
        fabricate,
        importer=StagingImporter(
            max_bytes=settings.fabricate_max_artifact_bytes,
            max_equipment_rows=settings.fabricate_max_equipment_rows,
        ),
        schema_doc_path=_schema_doc_path(),
        poll_sleep_seconds=0.0 if settings.fabricate_use_mock else 0.5,
    )
    return openai_eq, fabricate_eq


def _schema_doc_path() -> Any:
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    path = root / "docs" / "api" / "fabricate-staging-schema.md"
    return path if path.is_file() else None


def _proposal_title(
    description: str,
    payload: EquipmentProposalPayload,
) -> str:
    if payload.brief is not None and payload.brief.summary:
        head = payload.brief.summary.split(".")[0].strip()
        if head:
            return f"Proposal: {head}"[:300]
    if payload.brief is not None and payload.brief.plant_type:
        return f"Proposal: {payload.brief.plant_type}"[:300]
    return f"Proposal: {description.strip()[:80]}"


def _system_description(brief: Any) -> str | None:
    if not isinstance(brief, dict):
        return None
    summary = brief.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()[:5000]
    return None


def _system_name(
    *,
    system_name: str | None,
    title: str,
    brief: Any,
) -> str:
    candidate = (system_name or "").strip()
    if candidate.startswith("Proposal:"):
        candidate = ""
    if not candidate and isinstance(brief, dict):
        summary = brief.get("summary")
        if isinstance(summary, str) and summary.strip():
            candidate = summary.split(".")[0].strip()
        elif isinstance(brief.get("plant_type"), str):
            candidate = str(brief["plant_type"]).replace("_", " ")
    if not candidate:
        candidate = title.strip() or "Generated system"
        if candidate.startswith("Proposal:"):
            candidate = candidate.removeprefix("Proposal:").strip()
    return candidate[:200] or "Generated system"

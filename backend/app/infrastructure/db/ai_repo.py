"""Repositories for AI runs, generation jobs and proposals."""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from uuid import UUID
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.domain.ai.dto import EquipmentProposalPayload
from app.domain.ai.status import GenerationJobStatus
from app.domain.ai.status import ProposalItemDecision
from app.domain.ai.status import ProposalStatus
from app.domain.errors import NotFoundError
from app.infrastructure.db.models.ai import AiGeneratedValueRow
from app.infrastructure.db.models.ai import AiRunRow
from app.infrastructure.db.models.ai import GenerationJobRow
from app.infrastructure.db.models.ai import ProposalItemRow
from app.infrastructure.db.models.ai import ProposalRow


class AiRepository:
    """Persist AI orchestration entities."""

    def __init__(self, session: Session) -> None:
        """Bind a SQLAlchemy session."""
        self._session = session

    def create_ai_run(
        self,
        *,
        provider: str,
        prompt_hash: str,
        model: str | None = None,
        context_hash: str | None = None,
        status: str = "COMPLETED",
        latency_ms: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AiRunRow:
        """Insert an ai_runs row."""
        row = AiRunRow(
            id=uuid4(),
            provider=provider,
            model=model,
            prompt_hash=prompt_hash,
            context_hash=context_hash,
            status=status,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            error_message=error_message,
            metadata_json=metadata or {},
        )
        self._session.add(row)
        self._session.flush()
        return row

    def add_generated_value(
        self,
        *,
        ai_run_id: UUID,
        entity_type: str,
        entity_key: str,
        field_name: str,
        value_json: dict[str, Any],
        confidence: str = "LOW",
        value_status: str = "ESTIMATED",
    ) -> AiGeneratedValueRow:
        """Insert one ai_generated_values row."""
        row = AiGeneratedValueRow(
            id=uuid4(),
            ai_run_id=ai_run_id,
            entity_type=entity_type,
            entity_key=entity_key,
            field_name=field_name,
            value_json=value_json,
            confidence=confidence,
            value_status=value_status,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def create_job(
        self,
        *,
        provider: str,
        description: str,
        system_id: UUID | None = None,
        version_id: UUID | None = None,
        staging_schema_version: str = "1",
        metadata: dict[str, Any] | None = None,
    ) -> GenerationJobRow:
        """Enqueue a generation job."""
        now = datetime.now(UTC)
        row = GenerationJobRow(
            id=uuid4(),
            provider=provider,
            status=GenerationJobStatus.QUEUED.value,
            description=description,
            system_id=system_id,
            version_id=version_id,
            staging_schema_version=staging_schema_version,
            progress_pct=0.0,
            progress_message="queued",
            attempt_count=0,
            metadata_json=metadata or {},
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get_job(self, job_id: UUID) -> GenerationJobRow:
        """Return a generation job or raise NotFoundError."""
        row = self._session.get(GenerationJobRow, job_id)
        if row is None:
            raise NotFoundError(
                "generation job not found",
                entity="GenerationJob",
                entity_id=str(job_id),
            )
        return row

    def reclaim_stale_jobs(self, timeout_seconds: int) -> int:
        """Return stuck running jobs to QUEUED."""
        cutoff = datetime.now(UTC) - timedelta(seconds=timeout_seconds)
        active = {
            GenerationJobStatus.RUNNING.value,
            GenerationJobStatus.DOWNLOADING.value,
            GenerationJobStatus.IMPORTING.value,
        }
        stmt = (
            update(GenerationJobRow)
            .where(GenerationJobRow.status.in_(active))
            .where(GenerationJobRow.heartbeat_at.is_not(None))
            .where(GenerationJobRow.heartbeat_at < cutoff)
            .values(
                status=GenerationJobStatus.QUEUED.value,
                worker_id=None,
                claimed_at=None,
                heartbeat_at=None,
                progress_message="reclaimed after heartbeat timeout",
                updated_at=datetime.now(UTC),
            )
        )
        result = self._session.execute(stmt)
        return int(getattr(result, "rowcount", 0) or 0)

    def claim_next_job(self, worker_id: str) -> GenerationJobRow | None:
        """Atomically claim one QUEUED generation job."""
        now = datetime.now(UTC)
        candidate = self._session.execute(
            select(GenerationJobRow.id)
            .where(GenerationJobRow.status == GenerationJobStatus.QUEUED.value)
            .order_by(GenerationJobRow.created_at)
            .limit(1)
        ).scalar_one_or_none()
        if candidate is None:
            return None
        stmt = (
            update(GenerationJobRow)
            .where(GenerationJobRow.id == candidate)
            .where(GenerationJobRow.status == GenerationJobStatus.QUEUED.value)
            .values(
                status=GenerationJobStatus.RUNNING.value,
                worker_id=worker_id,
                claimed_at=now,
                heartbeat_at=now,
                attempt_count=GenerationJobRow.attempt_count + 1,
                progress_message="running",
                updated_at=now,
            )
        )
        result = self._session.execute(stmt)
        if int(getattr(result, "rowcount", 0) or 0) != 1:
            return None
        self._session.flush()
        return self.get_job(candidate)

    def heartbeat_job(self, job_id: UUID) -> None:
        """Refresh heartbeat timestamp."""
        row = self.get_job(job_id)
        row.heartbeat_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)
        self._session.flush()

    def update_job(self, job: GenerationJobRow) -> GenerationJobRow:
        """Persist job field changes."""
        job.updated_at = datetime.now(UTC)
        self._session.add(job)
        self._session.flush()
        return job

    def create_proposal(
        self,
        *,
        provider: str,
        title: str,
        payload: EquipmentProposalPayload,
        generation_job_id: UUID | None = None,
        ai_run_id: UUID | None = None,
        system_id: UUID | None = None,
        version_id: UUID | None = None,
        provenance: dict[str, Any] | None = None,
    ) -> ProposalRow:
        """Store a proposal and flatten items for review."""
        now = datetime.now(UTC)
        row = ProposalRow(
            id=uuid4(),
            generation_job_id=generation_job_id,
            ai_run_id=ai_run_id,
            system_id=system_id,
            version_id=version_id,
            provider=provider,
            status=ProposalStatus.PENDING.value,
            title=title,
            payload_json=payload.model_dump(mode="json"),
            provenance_json=provenance or {},
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        sort_order = 0
        for equipment in payload.equipment:
            self._add_item(
                row.id,
                "equipment",
                equipment.tag,
                equipment.model_dump(mode="json"),
                sort_order,
            )
            sort_order += 1
        for component in payload.components:
            key = f"{component.equipment_tag}:{component.name}"
            self._add_item(
                row.id,
                "component",
                key,
                component.model_dump(mode="json"),
                sort_order,
            )
            sort_order += 1
        for connection in payload.connections:
            key = (
                f"{connection.from_tag}->{connection.to_tag}:"
                f"{connection.connection_type}"
            )
            self._add_item(
                row.id,
                "connection",
                key,
                connection.model_dump(mode="json"),
                sort_order,
            )
            sort_order += 1
        for failure_mode in payload.failure_modes:
            key = f"{failure_mode.equipment_tag}:{failure_mode.name}"
            self._add_item(
                row.id,
                "failure_mode",
                key,
                failure_mode.model_dump(mode="json"),
                sort_order,
            )
            sort_order += 1
        for task in payload.maintenance_tasks:
            key = f"{task.equipment_tag}:{task.name}"
            self._add_item(
                row.id,
                "maintenance_task",
                key,
                task.model_dump(mode="json"),
                sort_order,
            )
            sort_order += 1
        return row

    def get_proposal(self, proposal_id: UUID) -> ProposalRow:
        """Return a proposal row."""
        row = self._session.get(ProposalRow, proposal_id)
        if row is None:
            raise NotFoundError(
                "proposal not found",
                entity="Proposal",
                entity_id=str(proposal_id),
            )
        return row

    def list_items(self, proposal_id: UUID) -> list[ProposalItemRow]:
        """Return proposal items ordered for review UI."""
        stmt = (
            select(ProposalItemRow)
            .where(ProposalItemRow.proposal_id == proposal_id)
            .order_by(ProposalItemRow.sort_order, ProposalItemRow.created_at)
        )
        return list(self._session.scalars(stmt).all())

    def get_item(self, item_id: UUID) -> ProposalItemRow:
        """Return one proposal item."""
        row = self._session.get(ProposalItemRow, item_id)
        if row is None:
            raise NotFoundError(
                "proposal item not found",
                entity="ProposalItem",
                entity_id=str(item_id),
            )
        return row

    def save_item(self, item: ProposalItemRow) -> ProposalItemRow:
        """Persist item decision/edits."""
        self._session.add(item)
        self._session.flush()
        return item

    def save_proposal(self, proposal: ProposalRow) -> ProposalRow:
        """Persist proposal status changes."""
        proposal.updated_at = datetime.now(UTC)
        self._session.add(proposal)
        self._session.flush()
        return proposal

    def _add_item(
        self,
        proposal_id: UUID,
        item_type: str,
        item_key: str,
        payload: dict[str, Any],
        sort_order: int,
    ) -> ProposalItemRow:
        row = ProposalItemRow(
            id=uuid4(),
            proposal_id=proposal_id,
            item_type=item_type,
            item_key=item_key,
            payload_json=payload,
            decision=ProposalItemDecision.PENDING.value,
            sort_order=sort_order,
        )
        self._session.add(row)
        self._session.flush()
        return row

"""Persisted AI run / proposal aggregates (domain view)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.domain.ai.dto import EquipmentProposalPayload
from app.domain.ai.status import GenerationJobStatus
from app.domain.ai.status import ProposalItemDecision
from app.domain.ai.status import ProposalStatus
from app.domain.base import Entity
from app.domain.provenance import Confidence


class AiRun(Entity):
    """One AI/Fabricate invocation with prompt/context hashes."""

    provider: str = Field(min_length=1, max_length=64)
    model: str | None = Field(default=None, max_length=128)
    prompt_hash: str = Field(min_length=1, max_length=64)
    context_hash: str | None = Field(default=None, max_length=64)
    status: str = Field(default="COMPLETED", max_length=32)
    latency_ms: int | None = Field(default=None, ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AiGeneratedValue(Entity):
    """Audit row for a single generated field/value."""

    ai_run_id: UUID
    entity_type: str = Field(min_length=1, max_length=64)
    entity_key: str = Field(min_length=1, max_length=128)
    field_name: str = Field(min_length=1, max_length=128)
    value_json: dict[str, Any] = Field(default_factory=dict)
    confidence: Confidence = Confidence.LOW
    value_status: str = Field(default="ESTIMATED", max_length=32)


class GenerationJob(Entity):
    """Async equipment generation job (Fabricate or OpenAI)."""

    provider: str = Field(min_length=1, max_length=64)
    status: GenerationJobStatus = GenerationJobStatus.QUEUED
    description: str = Field(min_length=1, max_length=5000)
    system_id: UUID | None = None
    version_id: UUID | None = None
    proposal_id: UUID | None = None
    ai_run_id: UUID | None = None
    conversation_id: str | None = Field(default=None, max_length=128)
    staging_schema_version: str = Field(default="1", max_length=32)
    progress_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    progress_message: str | None = Field(default=None, max_length=500)
    error_code: str | None = Field(default=None, max_length=64)
    error_message: str | None = None
    attempt_count: int = Field(default=0, ge=0)
    worker_id: str | None = Field(default=None, max_length=64)
    claimed_at: datetime | None = None
    heartbeat_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProposalItem(Entity):
    """One reviewable row inside a proposal."""

    proposal_id: UUID
    item_type: str = Field(min_length=1, max_length=64)
    item_key: str = Field(min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)
    decision: ProposalItemDecision = ProposalItemDecision.PENDING
    edited_payload: dict[str, Any] | None = None
    sort_order: int = Field(default=0, ge=0)


class Proposal(Entity):
    """Stored AI/Fabricate proposal awaiting user review."""

    generation_job_id: UUID | None = None
    ai_run_id: UUID | None = None
    system_id: UUID | None = None
    version_id: UUID | None = None
    provider: str = Field(min_length=1, max_length=64)
    status: ProposalStatus = ProposalStatus.PENDING
    title: str = Field(min_length=1, max_length=300)
    payload: EquipmentProposalPayload
    items: list[ProposalItem] = Field(default_factory=list)
    provenance_json: dict[str, Any] = Field(default_factory=dict)

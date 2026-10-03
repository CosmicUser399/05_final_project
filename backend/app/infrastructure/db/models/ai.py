"""ORM rows for AI runs, proposals and generation jobs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import func
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import Uuid

from app.infrastructure.db.base import Base
from app.infrastructure.db.base import UuidPrimaryKey


class AiRunRow(Base):
    """One AI/Fabricate invocation metadata row."""

    __tablename__ = "ai_runs"

    id: Mapped[UuidPrimaryKey]
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    context_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="COMPLETED",
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class AiGeneratedValueRow(Base):
    """Single generated field with confidence."""

    __tablename__ = "ai_generated_values"

    id: Mapped[UuidPrimaryKey]
    ai_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_key: Mapped[str] = mapped_column(String(128), nullable=False)
    field_name: Mapped[str] = mapped_column(String(128), nullable=False)
    value_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="LOW",
    )
    value_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="ESTIMATED",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class GenerationJobRow(Base):
    """Async equipment generation job queue row."""

    __tablename__ = "generation_jobs"

    id: Mapped[UuidPrimaryKey]
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="QUEUED",
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    system_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("systems.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Soft reference (proposals.generation_job_id is the FK side).
    proposal_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True,
    )
    ai_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    conversation_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    staging_schema_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="1",
    )
    progress_pct: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    progress_message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def as_dict(self) -> dict[str, Any]:
        """Plain dict for API / SSE."""
        return {
            "id": self.id,
            "provider": self.provider,
            "status": self.status,
            "description": self.description,
            "system_id": self.system_id,
            "version_id": self.version_id,
            "proposal_id": self.proposal_id,
            "ai_run_id": self.ai_run_id,
            "conversation_id": self.conversation_id,
            "staging_schema_version": self.staging_schema_version,
            "progress_pct": self.progress_pct,
            "progress_message": self.progress_message,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "attempt_count": self.attempt_count,
            "metadata": self.metadata_json or {},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ProposalRow(Base):
    """Stored proposal awaiting review."""

    __tablename__ = "proposals"

    id: Mapped[UuidPrimaryKey]
    generation_job_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("generation_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ai_run_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    system_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("systems.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="PENDING",
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    provenance_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ProposalItemRow(Base):
    """One reviewable proposal row."""

    __tablename__ = "proposal_items"

    id: Mapped[UuidPrimaryKey]
    proposal_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    item_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    decision: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="PENDING",
    )
    edited_payload_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

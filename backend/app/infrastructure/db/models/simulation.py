"""ORM rows for simulation configuration, runs, metrics and events."""

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
from sqlalchemy import UniqueConstraint
from sqlalchemy import func
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import Uuid

from app.infrastructure.db.base import Base
from app.infrastructure.db.base import TimestampMixin
from app.infrastructure.db.base import UuidPrimaryKey
from app.infrastructure.db.types_json import JsonObject


class SimulationConfigurationRow(Base, TimestampMixin):
    """Persisted simulation configuration snapshot."""

    __tablename__ = "simulation_configurations"

    id: Mapped[UuidPrimaryKey]
    version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    configuration_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    payload_json: Mapped[JsonObject] = mapped_column(JSON, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)


class SimulationRunRow(Base, TimestampMixin):
    """Simulation job queue row and lifecycle record."""

    __tablename__ = "simulation_runs"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_simulation_runs_idempotency_key",
        ),
    )

    id: Mapped[UuidPrimaryKey]
    version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reliability_model_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reliability_models.id", ondelete="SET NULL"),
        nullable=True,
    )
    configuration_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("simulation_configurations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scenario_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scenario_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )
    progress: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    completed_runs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_runs: Mapped[int] = mapped_column(Integer, nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    model_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scenario_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    configuration_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    software_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    simulation_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    worker_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    aggregates_json: Mapped[JsonObject | None] = mapped_column(
        JSON,
        nullable=True,
    )

    def as_status_dict(self) -> dict[str, Any]:
        """Return a compact status payload for API/SSE."""
        return {
            "id": self.id,
            "version_id": self.version_id,
            "scenario_version_id": self.scenario_version_id,
            "status": self.status,
            "progress": self.progress,
            "completed_runs": self.completed_runs,
            "total_runs": self.total_runs,
            "random_seed": self.random_seed,
            "model_hash": self.model_hash,
            "scenario_hash": self.scenario_hash,
            "configuration_hash": self.configuration_hash,
            "software_version": self.software_version,
            "simulation_fingerprint": self.simulation_fingerprint,
            "error_message": self.error_message,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SystemMetricsRow(Base):
    """Persisted system-level aggregate metrics for one run."""

    __tablename__ = "system_metrics"

    id: Mapped[UuidPrimaryKey]
    simulation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    metrics_json: Mapped[JsonObject] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class EquipmentMetricsRow(Base):
    """Persisted per-equipment aggregate metrics."""

    __tablename__ = "equipment_metrics"

    id: Mapped[UuidPrimaryKey]
    simulation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    equipment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )
    metrics_json: Mapped[JsonObject] = mapped_column(JSON, nullable=False)


class FailureEventRow(Base):
    """Normalized failure / potential-failure events."""

    __tablename__ = "failure_events"

    id: Mapped[UuidPrimaryKey]
    simulation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trial_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    equipment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True,
    )
    failure_mode_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    details_json: Mapped[JsonObject] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )


class MaintenanceEventRow(Base):
    """Normalized CM/PM events."""

    __tablename__ = "maintenance_events"

    id: Mapped[UuidPrimaryKey]
    simulation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trial_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    equipment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True,
    )
    task_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    failure_mode_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    details_json: Mapped[JsonObject] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )


class DiagnosticEventRow(Base):
    """Normalized diagnostic / detection events."""

    __tablename__ = "diagnostic_events"

    id: Mapped[UuidPrimaryKey]
    simulation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trial_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    equipment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True,
    )
    task_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    failure_mode_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    details_json: Mapped[JsonObject] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )


class ProductionLossEventRow(Base):
    """Normalized production-change / loss events."""

    __tablename__ = "production_loss_events"

    id: Mapped[UuidPrimaryKey]
    simulation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trial_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    equipment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True,
    )
    details_json: Mapped[JsonObject] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )


class ResourceConsumptionRow(Base):
    """Normalized resource wait / consumption events."""

    __tablename__ = "resource_consumption"

    id: Mapped[UuidPrimaryKey]
    simulation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trial_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True,
    )
    equipment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    details_json: Mapped[JsonObject] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )


class SparePartConsumptionRow(Base):
    """Normalized spare request / availability events."""

    __tablename__ = "spare_part_consumption"

    id: Mapped[UuidPrimaryKey]
    simulation_run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("simulation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trial_run_id: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    spare_part_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        index=True,
    )
    equipment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    details_json: Mapped[JsonObject] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

"""ORM models for maintenance, resources and diagnostics."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import JSON
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import Uuid

from app.infrastructure.db.base import Base
from app.infrastructure.db.base import UuidPrimaryKey
from app.infrastructure.db.base import VersionedMixin
from app.infrastructure.db.types_json import DistributionJson
from app.infrastructure.db.types_json import ProvenanceJson


class ResourceRow(Base, VersionedMixin):
    """Crew, tool or other limited maintenance resource."""

    __tablename__ = "resources"

    id: Mapped[UuidPrimaryKey]
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cost_per_hour: Mapped[float | None] = mapped_column(Float, nullable=True)


class SparePartRow(Base, VersionedMixin):
    """Spare part with stock and replenishment lead time."""

    __tablename__ = "spare_parts"

    id: Mapped[UuidPrimaryKey]
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lead_time_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    lead_time_unit: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    unit_cost: Mapped[float | None] = mapped_column(Float, nullable=True)


class MaintenanceTaskRow(Base, VersionedMixin):
    """Maintenance task (inspection, preventive or corrective)."""

    __tablename__ = "maintenance_tasks"

    id: Mapped[UuidPrimaryKey]
    equipment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    failure_mode_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("failure_modes.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    interval_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    interval_unit: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)


class MaintenanceDistributionRow(Base, VersionedMixin):
    """Duration distribution of a maintenance task."""

    __tablename__ = "maintenance_distributions"

    id: Mapped[UuidPrimaryKey]
    maintenance_task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("maintenance_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    distribution: Mapped[DistributionJson] = mapped_column(
        JSON,
        nullable=False,
    )
    provenance: Mapped[ProvenanceJson] = mapped_column(JSON, nullable=False)


class MaintenanceEffectRow(Base, VersionedMixin):
    """Effect of a maintenance task on equipment or a failure mode."""

    __tablename__ = "maintenance_effects"

    id: Mapped[UuidPrimaryKey]
    maintenance_task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("maintenance_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    effect_type: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_mode_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("failure_modes.id", ondelete="SET NULL"),
        nullable=True,
    )
    parameter: Mapped[float | None] = mapped_column(Float, nullable=True)


class ResourceRequirementRow(Base, VersionedMixin):
    """Resource units required by a maintenance task."""

    __tablename__ = "resource_requirements"

    id: Mapped[UuidPrimaryKey]
    maintenance_task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("maintenance_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class SparePartRequirementRow(Base, VersionedMixin):
    """Spare part units consumed by a maintenance task."""

    __tablename__ = "spare_part_requirements"

    id: Mapped[UuidPrimaryKey]
    maintenance_task_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("maintenance_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    spare_part_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("spare_parts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class DiagnosticTaskRow(Base, VersionedMixin):
    """Condition monitoring / diagnostic check task."""

    __tablename__ = "diagnostic_tasks"

    id: Mapped[UuidPrimaryKey]
    equipment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    failure_mode_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("failure_modes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    method: Mapped[str | None] = mapped_column(String(200), nullable=True)
    interval_value: Mapped[float] = mapped_column(Float, nullable=False)
    interval_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    detection_probability: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    false_positive_probability: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
    )
    duration_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_unit: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    provenance: Mapped[ProvenanceJson | None] = mapped_column(
        JSON,
        nullable=True,
    )

"""ORM models for failure modes and reliability structures."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import Uuid

from app.infrastructure.db.base import Base
from app.infrastructure.db.base import UuidPrimaryKey
from app.infrastructure.db.base import VersionedMixin
from app.infrastructure.db.types_json import DistributionJson
from app.infrastructure.db.types_json import ProvenanceJson


class FailureModeRow(Base, VersionedMixin):
    """Failure mode of equipment or a component."""

    __tablename__ = "failure_modes"

    id: Mapped[UuidPrimaryKey]
    equipment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    component_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("equipment_components.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_detectable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    pf_interval_value: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    pf_interval_unit: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
    )


class FailureDistributionRow(Base, VersionedMixin):
    """Time-to-failure distribution for a failure mode."""

    __tablename__ = "failure_distributions"

    id: Mapped[UuidPrimaryKey]
    failure_mode_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("failure_modes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    distribution: Mapped[DistributionJson] = mapped_column(
        JSON,
        nullable=False,
    )
    provenance: Mapped[ProvenanceJson] = mapped_column(JSON, nullable=False)


class ReliabilityStructureRow(Base, VersionedMixin):
    """Node in the redundancy / reliability block tree."""

    __tablename__ = "reliability_structures"

    id: Mapped[UuidPrimaryKey]
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    structure_type: Mapped[str] = mapped_column(String(32), nullable=False)
    k: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_structure_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reliability_structures.id", ondelete="SET NULL"),
        nullable=True,
    )


class ReliabilityStructureMemberRow(Base, VersionedMixin):
    """Member of a reliability structure (equipment or nested structure)."""

    __tablename__ = "reliability_structure_members"

    id: Mapped[UuidPrimaryKey]
    structure_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reliability_structures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    equipment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=True,
    )
    child_structure_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reliability_structures.id", ondelete="CASCADE"),
        nullable=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

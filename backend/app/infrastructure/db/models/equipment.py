"""ORM models for equipment, taxonomies and connections."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean
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


class TaxonomyRow(Base):
    """Classification tree definition (business or ISO 14224)."""

    __tablename__ = "taxonomies"

    id: Mapped[UuidPrimaryKey]
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    version_label: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )


class TaxonomyNodeRow(Base):
    """Node in a taxonomy tree."""

    __tablename__ = "taxonomy_nodes"

    id: Mapped[UuidPrimaryKey]
    taxonomy_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("taxonomies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("taxonomy_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)


class EquipmentRow(Base, VersionedMixin):
    """Equipment item belonging to a system version."""

    __tablename__ = "equipment"

    id: Mapped[UuidPrimaryKey]
    tag: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("equipment.id", ondelete="SET NULL"),
        nullable=True,
    )
    taxonomy_node_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("taxonomy_nodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    equipment_class: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    equipment_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    criticality: Mapped[str] = mapped_column(String(32), nullable=False)
    operating_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    standby_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    is_repairable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )


class EquipmentComponentRow(Base, VersionedMixin):
    """Component (part) of a piece of equipment."""

    __tablename__ = "equipment_components"

    id: Mapped[UuidPrimaryKey]
    equipment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class EquipmentConnectionRow(Base, VersionedMixin):
    """Directed link between two equipment items."""

    __tablename__ = "equipment_connections"

    id: Mapped[UuidPrimaryKey]
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    connection_type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

"""ORM models for production functions and impacts."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import Uuid

from app.infrastructure.db.base import Base
from app.infrastructure.db.base import UuidPrimaryKey
from app.infrastructure.db.base import VersionedMixin


class ProductionFunctionRow(Base, VersionedMixin):
    """Nominal production output of a system version."""

    __tablename__ = "production_functions"

    id: Mapped[UuidPrimaryKey]
    product: Mapped[str] = mapped_column(String(200), nullable=False)
    rate_value: Mapped[float] = mapped_column(Float, nullable=False)
    mass_unit: Mapped[str] = mapped_column(String(32), nullable=False)
    time_unit: Mapped[str] = mapped_column(String(32), nullable=False)


class ProductionImpactRow(Base, VersionedMixin):
    """Production loss while equipment is unavailable."""

    __tablename__ = "production_impacts"

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
    loss_fraction: Mapped[float] = mapped_column(Float, nullable=False)

"""ORM models for reference parameters (OREDA / ISO extracts)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import JSON
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import Uuid

from app.infrastructure.db.base import Base
from app.infrastructure.db.base import TimestampMixin
from app.infrastructure.db.base import UuidPrimaryKey


class ReferenceParameterRow(Base, TimestampMixin):
    """Curated reliability parameter with bibliographic provenance."""

    __tablename__ = "reference_parameters"

    id: Mapped[UuidPrimaryKey]
    source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("reference_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    equipment_class: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        index=True,
    )
    equipment_class_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    failure_mode_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    failure_mode_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    parameter_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    parameter_kind: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    distribution_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    distribution_params_json: Mapped[dict[str, float] | None] = mapped_column(
        JSON, nullable=True
    )
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_document: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )
    source_reference: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

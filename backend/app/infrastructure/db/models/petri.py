"""Persisted Petri model snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import func
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import Uuid

from app.infrastructure.db.base import Base
from app.infrastructure.db.base import UuidPrimaryKey


class PetriModelRow(Base):
    """Derived Petri model linked to a reliability snapshot."""

    __tablename__ = "petri_models"

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
        index=True,
    )
    reliability_model_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    definition_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    schema_version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="1",
    )
    validation_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="PENDING",
    )
    petri_pilot_version: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def as_dict(self, *, include_definition: bool = True) -> dict[str, Any]:
        """Return a plain dict for API responses."""
        payload: dict[str, Any] = {
            "id": self.id,
            "version_id": self.version_id,
            "reliability_model_id": self.reliability_model_id,
            "reliability_model_hash": self.reliability_model_hash,
            "schema_version": self.schema_version,
            "validation_status": self.validation_status,
            "petri_pilot_version": self.petri_pilot_version,
            "generated_at": self.generated_at,
            "notes": self.notes,
        }
        if include_definition:
            payload["definition"] = self.definition_json
        return payload

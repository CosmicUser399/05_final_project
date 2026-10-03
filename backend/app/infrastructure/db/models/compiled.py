"""Persisted reliability model snapshots."""

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
from app.infrastructure.db.types_json import JsonObject


class ReliabilityModelRow(Base):
    """Immutable compiled reliability model for a system version."""

    __tablename__ = "reliability_models"

    id: Mapped[UuidPrimaryKey]
    version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_json: Mapped[JsonObject] = mapped_column(
        JSON,
        nullable=False,
    )
    validation_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="VALID",
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    def as_dict(self) -> dict[str, Any]:
        """Return a plain dict for API responses."""
        return {
            "id": self.id,
            "version_id": self.version_id,
            "model_hash": self.model_hash,
            "validation_status": self.validation_status,
            "generated_at": self.generated_at,
            "notes": self.notes,
            "snapshot": self.snapshot_json,
        }

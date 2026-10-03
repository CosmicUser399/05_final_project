"""ORM rows for scenarios, scenario versions and changes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.types import Uuid

from app.infrastructure.db.base import Base
from app.infrastructure.db.base import TimestampMixin
from app.infrastructure.db.base import UuidPrimaryKey
from app.infrastructure.db.types_json import JsonObject


class ScenarioRow(Base, TimestampMixin):
    """Named scenario attached to a system version."""

    __tablename__ = "scenarios"

    id: Mapped[UuidPrimaryKey]
    version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("system_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_version_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    versions: Mapped[list[ScenarioVersionRow]] = relationship(
        "ScenarioVersionRow",
        back_populates="scenario",
        cascade="all, delete-orphan",
        foreign_keys="ScenarioVersionRow.scenario_id",
    )


class ScenarioVersionRow(Base, TimestampMixin):
    """Immutable snapshot of scenario changes + hash."""

    __tablename__ = "scenario_versions"
    __table_args__ = (
        UniqueConstraint(
            "scenario_id",
            "version_number",
            name="uq_scenario_versions_scenario_id_version_number",
        ),
    )

    id: Mapped[UuidPrimaryKey]
    scenario_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scenarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    scenario: Mapped[ScenarioRow] = relationship(
        "ScenarioRow",
        back_populates="versions",
        foreign_keys=[scenario_id],
    )
    changes: Mapped[list[ScenarioChangeRow]] = relationship(
        "ScenarioChangeRow",
        back_populates="scenario_version",
        cascade="all, delete-orphan",
        order_by="ScenarioChangeRow.sort_order",
    )


class ScenarioChangeRow(Base, TimestampMixin):
    """One overlay change within a scenario version."""

    __tablename__ = "scenario_changes"

    id: Mapped[UuidPrimaryKey]
    scenario_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("scenario_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_lineage_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
    )
    parameters_json: Mapped[JsonObject] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    scenario_version: Mapped[ScenarioVersionRow] = relationship(
        "ScenarioVersionRow",
        back_populates="changes",
    )

    def as_dict(self) -> dict[str, Any]:
        """Serialize change for API responses."""
        return {
            "id": self.id,
            "scenario_version_id": self.scenario_version_id,
            "change_type": self.change_type,
            "target_lineage_id": self.target_lineage_id,
            "parameters": self.parameters_json,
            "sort_order": self.sort_order,
        }

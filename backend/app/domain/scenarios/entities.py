"""Persisted scenario aggregates (overlay on a frozen version)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import Field

from app.domain.base import Entity
from app.domain.reliability.compiled import ScenarioChange
from app.domain.reliability.compiled import ScenarioChangeType
from app.domain.reliability.compiled import ScenarioOverlay


class ScenarioChangeEntity(Entity):
    """One persisted overlay change targeting a lineage_id."""

    scenario_version_id: UUID
    change_type: ScenarioChangeType
    target_lineage_id: UUID
    parameters: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = Field(default=0, ge=0)

    def to_overlay_change(self) -> ScenarioChange:
        """Map to the runtime overlay DTO."""
        return ScenarioChange(
            change_type=self.change_type,
            target_lineage_id=self.target_lineage_id,
            parameters=dict(self.parameters),
        )


class ScenarioVersionEntity(Entity):
    """Immutable snapshot of scenario changes + scenario_hash."""

    scenario_id: UUID
    version_number: int = Field(ge=1)
    scenario_hash: str = Field(min_length=64, max_length=64)
    changes: list[ScenarioChangeEntity] = Field(default_factory=list)

    def to_overlay(self) -> ScenarioOverlay:
        """Build a runtime ScenarioOverlay from stored changes."""
        ordered = sorted(self.changes, key=lambda c: c.sort_order)
        return ScenarioOverlay(
            changes=tuple(c.to_overlay_change() for c in ordered)
        )


class ScenarioEntity(Entity):
    """Named scenario attached to a system version (baseline intact)."""

    version_id: UUID
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    current_version_id: UUID | None = None

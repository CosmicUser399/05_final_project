"""Input DTOs for creating scenarios and changes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.domain.reliability.compiled import ScenarioChangeType


class ScenarioChangeInput(BaseModel):
    """One change supplied when creating a scenario version."""

    model_config = ConfigDict(extra="forbid")

    change_type: ScenarioChangeType
    target_lineage_id: UUID
    parameters: dict[str, Any] = Field(default_factory=dict)


class ScenarioCreateInput(BaseModel):
    """Create a scenario with an initial change set."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    changes: list[ScenarioChangeInput] = Field(default_factory=list)


class ScenarioVersionCreateInput(BaseModel):
    """Create a new immutable scenario version (new change set)."""

    model_config = ConfigDict(extra="forbid")

    changes: list[ScenarioChangeInput] = Field(min_length=0)

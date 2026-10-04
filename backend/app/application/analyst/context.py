"""DTOs for AI Analyst chat."""

from __future__ import annotations

from typing import Any
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class AnalystChatContext(BaseModel):
    """Scoped ids for tool resolution (optional filters)."""

    model_config = ConfigDict(frozen=True)

    system_id: UUID | None = None
    version_id: UUID | None = None
    scenario_id: UUID | None = None
    simulation_run_id: UUID | None = None
    equipment_id: UUID | None = None


class AnalystChatTurn(BaseModel):
    """One prior turn in the analyst dialog."""

    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class AnalystToolCallRecord(BaseModel):
    """One executed typed tool invocation."""

    model_config = ConfigDict(frozen=True)

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    ok: bool
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class AnalystReference(BaseModel):
    """Provenance pointer attached to an analyst answer."""

    model_config = ConfigDict(frozen=True)

    kind: str
    entity_id: str | None = None
    label: str
    detail: dict[str, Any] = Field(default_factory=dict)


class AnalystChatRequest(BaseModel):
    """User question plus optional chat context."""

    model_config = ConfigDict(frozen=True)

    message: str = Field(min_length=1, max_length=4000)
    context: AnalystChatContext = Field(
        default_factory=AnalystChatContext,
    )
    history: list[AnalystChatTurn] = Field(
        default_factory=list,
        max_length=40,
    )


class AnalystChatResponse(BaseModel):
    """Grounded answer built only from tool results."""

    model_config = ConfigDict(frozen=True)

    answer: str
    references: list[AnalystReference] = Field(default_factory=list)
    tool_calls: list[AnalystToolCallRecord] = Field(
        default_factory=list,
    )
    grounded: bool = True
    model: str | None = None

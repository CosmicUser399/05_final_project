"""Helpers for writing audit events from application services."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infrastructure.db.types_json import JsonObject
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


def _to_json(value: Any) -> JsonObject | None:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    msg = f"unsupported audit payload type: {type(value)!r}"
    raise TypeError(msg)


def write_audit(
    uow: SqlAlchemyUnitOfWork,
    *,
    version_id: UUID | None,
    entity_type: str,
    entity_id: UUID,
    action: str,
    actor_id: UUID | None = None,
    old_value: Any = None,
    new_value: Any = None,
    source: str | None = None,
    reason: str | None = None,
) -> None:
    """Append an audit event for an engineering change."""
    uow.audit.add_event(
        version_id=version_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        old_value=_to_json(old_value),
        new_value=_to_json(new_value),
        source=source,
        reason=reason,
    )

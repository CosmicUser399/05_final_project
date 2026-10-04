"""Failure mode CRUD for equipment."""

# ruff: noqa: D102, D107

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.application.audit import write_audit
from app.domain.reliability.entities import FailureDistribution
from app.domain.reliability.entities import FailureMode
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class FailureModeService:
    """Manage failure modes and optional distributions."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def list_for_equipment(self, equipment_id: UUID) -> list[FailureMode]:
        with self._uow_factory() as uow:
            equipment = uow.content.get_equipment(equipment_id)
            return uow.content.list_failure_modes(
                equipment.version_id,
                equipment_id=equipment_id,
            )

    def list_for_version(
        self,
        version_id: UUID,
        *,
        equipment_id: UUID | None = None,
    ) -> list[FailureMode]:
        """List failure modes for a version (optional equipment filter)."""
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            return uow.content.list_failure_modes(
                version_id,
                equipment_id=equipment_id,
            )

    def get(self, failure_mode_id: UUID) -> FailureMode:
        with self._uow_factory() as uow:
            return uow.content.get_failure_mode(failure_mode_id)

    def create(
        self,
        equipment_id: UUID,
        data: dict[str, Any],
        *,
        distribution: dict[str, Any] | None = None,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> FailureMode:
        with self._uow_factory() as uow:
            equipment = uow.content.get_equipment(equipment_id)
            mode_data = {
                **data,
                "version_id": equipment.version_id,
                "equipment_id": equipment_id,
            }
            failure_mode = FailureMode(**mode_data)
            uow.content.save_failure_mode(failure_mode)
            write_audit(
                uow,
                version_id=failure_mode.version_id,
                entity_type="FailureMode",
                entity_id=failure_mode.id,
                action="CREATE",
                actor_id=actor_id,
                new_value=failure_mode,
                source=source,
                reason=reason,
            )
            if distribution is not None:
                dist = FailureDistribution(
                    version_id=equipment.version_id,
                    failure_mode_id=failure_mode.id,
                    **distribution,
                )
                uow.content.save_failure_distribution(dist)
                write_audit(
                    uow,
                    version_id=dist.version_id,
                    entity_type="FailureDistribution",
                    entity_id=dist.id,
                    action="CREATE",
                    actor_id=actor_id,
                    new_value=dist,
                    source=source,
                    reason=reason,
                )
            return failure_mode

    def update(
        self,
        failure_mode_id: UUID,
        data: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> FailureMode:
        with self._uow_factory() as uow:
            current = uow.content.get_failure_mode(failure_mode_id)
            updated = current.model_copy(update=data)
            uow.content.save_failure_mode(updated)
            write_audit(
                uow,
                version_id=updated.version_id,
                entity_type="FailureMode",
                entity_id=updated.id,
                action="UPDATE",
                actor_id=actor_id,
                old_value=current,
                new_value=updated,
                source=source,
                reason=reason,
            )
            return updated

    def delete(
        self,
        failure_mode_id: UUID,
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> None:
        with self._uow_factory() as uow:
            removed = uow.content.delete_failure_mode(failure_mode_id)
            write_audit(
                uow,
                version_id=removed.version_id,
                entity_type="FailureMode",
                entity_id=removed.id,
                action="DELETE",
                actor_id=actor_id,
                old_value=removed,
                source=source,
                reason=reason,
            )

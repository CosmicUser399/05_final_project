"""Equipment CRUD for a system version."""

# ruff: noqa: D102, D107

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.application.audit import write_audit
from app.domain.equipment.entities import Equipment
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class EquipmentService:
    """Manage equipment rows on a DRAFT version."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def list_for_version(self, version_id: UUID) -> list[Equipment]:
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            return uow.content.list_equipment(version_id)

    def get(self, equipment_id: UUID) -> Equipment:
        with self._uow_factory() as uow:
            return uow.content.get_equipment(equipment_id)

    def create(
        self,
        version_id: UUID,
        data: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> Equipment:
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            equipment = Equipment(version_id=version_id, **data)
            uow.content.save_equipment(equipment)
            write_audit(
                uow,
                version_id=version_id,
                entity_type="Equipment",
                entity_id=equipment.id,
                action="CREATE",
                actor_id=actor_id,
                new_value=equipment,
                source=source,
                reason=reason,
            )
            return equipment

    def update(
        self,
        equipment_id: UUID,
        data: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> Equipment:
        with self._uow_factory() as uow:
            current = uow.content.get_equipment(equipment_id)
            updated = current.model_copy(update=data)
            uow.content.save_equipment(updated)
            write_audit(
                uow,
                version_id=updated.version_id,
                entity_type="Equipment",
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
        equipment_id: UUID,
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> None:
        with self._uow_factory() as uow:
            removed = uow.content.delete_equipment(equipment_id)
            write_audit(
                uow,
                version_id=removed.version_id,
                entity_type="Equipment",
                entity_id=removed.id,
                action="DELETE",
                actor_id=actor_id,
                old_value=removed,
                source=source,
                reason=reason,
            )

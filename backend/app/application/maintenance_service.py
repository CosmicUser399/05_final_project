"""Maintenance task CRUD for equipment."""

# ruff: noqa: D102, D107

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.application.audit import write_audit
from app.domain.maintenance.entities import MaintenanceDistribution
from app.domain.maintenance.entities import MaintenanceTask
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class MaintenanceService:
    """Manage maintenance tasks on equipment."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def list_for_equipment(self, equipment_id: UUID) -> list[MaintenanceTask]:
        with self._uow_factory() as uow:
            equipment = uow.content.get_equipment(equipment_id)
            return uow.content.list_maintenance_tasks(
                equipment.version_id,
                equipment_id=equipment_id,
            )

    def get(self, task_id: UUID) -> MaintenanceTask:
        with self._uow_factory() as uow:
            return uow.content.get_maintenance_task(task_id)

    def create(
        self,
        equipment_id: UUID,
        data: dict[str, Any],
        *,
        duration: dict[str, Any] | None = None,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> MaintenanceTask:
        with self._uow_factory() as uow:
            equipment = uow.content.get_equipment(equipment_id)
            task = MaintenanceTask(
                version_id=equipment.version_id,
                equipment_id=equipment_id,
                **data,
            )
            uow.content.save_maintenance_task(task)
            write_audit(
                uow,
                version_id=task.version_id,
                entity_type="MaintenanceTask",
                entity_id=task.id,
                action="CREATE",
                actor_id=actor_id,
                new_value=task,
                source=source,
                reason=reason,
            )
            if duration is not None:
                dist = MaintenanceDistribution(
                    version_id=equipment.version_id,
                    maintenance_task_id=task.id,
                    **duration,
                )
                uow.content.save_maintenance_distribution(dist)
                write_audit(
                    uow,
                    version_id=dist.version_id,
                    entity_type="MaintenanceDistribution",
                    entity_id=dist.id,
                    action="CREATE",
                    actor_id=actor_id,
                    new_value=dist,
                    source=source,
                    reason=reason,
                )
            return task

    def update(
        self,
        task_id: UUID,
        data: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> MaintenanceTask:
        with self._uow_factory() as uow:
            current = uow.content.get_maintenance_task(task_id)
            updated = current.model_copy(update=data)
            uow.content.save_maintenance_task(updated)
            write_audit(
                uow,
                version_id=updated.version_id,
                entity_type="MaintenanceTask",
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
        task_id: UUID,
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> None:
        with self._uow_factory() as uow:
            removed = uow.content.delete_maintenance_task(task_id)
            write_audit(
                uow,
                version_id=removed.version_id,
                entity_type="MaintenanceTask",
                entity_id=removed.id,
                action="DELETE",
                actor_id=actor_id,
                old_value=removed,
                source=source,
                reason=reason,
            )

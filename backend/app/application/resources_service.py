"""Resource and spare part CRUD for a system version."""

# ruff: noqa: D102, D107

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.application.audit import write_audit
from app.domain.resources.entities import Resource
from app.domain.resources.entities import SparePart
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class ResourcesService:
    """Manage maintenance resources and spare parts."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def list_resources(self, version_id: UUID) -> list[Resource]:
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            return uow.content.list_resources(version_id)

    def get_resource(self, resource_id: UUID) -> Resource:
        with self._uow_factory() as uow:
            return uow.content.get_resource(resource_id)

    def create_resource(
        self,
        version_id: UUID,
        data: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> Resource:
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            resource = Resource(version_id=version_id, **data)
            uow.content.save_resource(resource)
            write_audit(
                uow,
                version_id=version_id,
                entity_type="Resource",
                entity_id=resource.id,
                action="CREATE",
                actor_id=actor_id,
                new_value=resource,
                source=source,
                reason=reason,
            )
            return resource

    def update_resource(
        self,
        resource_id: UUID,
        data: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> Resource:
        with self._uow_factory() as uow:
            current = uow.content.get_resource(resource_id)
            updated = current.model_copy(update=data)
            uow.content.save_resource(updated)
            write_audit(
                uow,
                version_id=updated.version_id,
                entity_type="Resource",
                entity_id=updated.id,
                action="UPDATE",
                actor_id=actor_id,
                old_value=current,
                new_value=updated,
                source=source,
                reason=reason,
            )
            return updated

    def delete_resource(
        self,
        resource_id: UUID,
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> None:
        with self._uow_factory() as uow:
            removed = uow.content.delete_resource(resource_id)
            write_audit(
                uow,
                version_id=removed.version_id,
                entity_type="Resource",
                entity_id=removed.id,
                action="DELETE",
                actor_id=actor_id,
                old_value=removed,
                source=source,
                reason=reason,
            )

    def list_spare_parts(self, version_id: UUID) -> list[SparePart]:
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            return uow.content.list_spare_parts(version_id)

    def get_spare_part(self, spare_part_id: UUID) -> SparePart:
        with self._uow_factory() as uow:
            return uow.content.get_spare_part(spare_part_id)

    def create_spare_part(
        self,
        version_id: UUID,
        data: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> SparePart:
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            part = SparePart(version_id=version_id, **data)
            uow.content.save_spare_part(part)
            write_audit(
                uow,
                version_id=version_id,
                entity_type="SparePart",
                entity_id=part.id,
                action="CREATE",
                actor_id=actor_id,
                new_value=part,
                source=source,
                reason=reason,
            )
            return part

    def update_spare_part(
        self,
        spare_part_id: UUID,
        data: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> SparePart:
        with self._uow_factory() as uow:
            current = uow.content.get_spare_part(spare_part_id)
            updated = current.model_copy(update=data)
            uow.content.save_spare_part(updated)
            write_audit(
                uow,
                version_id=updated.version_id,
                entity_type="SparePart",
                entity_id=updated.id,
                action="UPDATE",
                actor_id=actor_id,
                old_value=current,
                new_value=updated,
                source=source,
                reason=reason,
            )
            return updated

    def delete_spare_part(
        self,
        spare_part_id: UUID,
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> None:
        with self._uow_factory() as uow:
            removed = uow.content.delete_spare_part(spare_part_id)
            write_audit(
                uow,
                version_id=removed.version_id,
                entity_type="SparePart",
                entity_id=removed.id,
                action="DELETE",
                actor_id=actor_id,
                old_value=removed,
                source=source,
                reason=reason,
            )

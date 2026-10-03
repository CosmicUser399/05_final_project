"""Equipment connection CRUD for a system version."""

# ruff: noqa: D102, D107

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.application.audit import write_audit
from app.domain.equipment.entities import EquipmentConnection
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class ConnectionsService:
    """Manage directed links between equipment."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def list_for_version(self, version_id: UUID) -> list[EquipmentConnection]:
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            return uow.content.list_connections(version_id)

    def create(
        self,
        version_id: UUID,
        data: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> EquipmentConnection:
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            connection = EquipmentConnection(
                version_id=version_id,
                **data,
            )
            uow.content.save_connection(connection)
            write_audit(
                uow,
                version_id=version_id,
                entity_type="EquipmentConnection",
                entity_id=connection.id,
                action="CREATE",
                actor_id=actor_id,
                new_value=connection,
                source=source,
                reason=reason,
            )
            return connection

    def delete(
        self,
        connection_id: UUID,
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> None:
        with self._uow_factory() as uow:
            removed = uow.content.delete_connection(connection_id)
            write_audit(
                uow,
                version_id=removed.version_id,
                entity_type="EquipmentConnection",
                entity_id=removed.id,
                action="DELETE",
                actor_id=actor_id,
                old_value=removed,
                source=source,
                reason=reason,
            )

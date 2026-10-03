"""Application services for ``System`` aggregates."""

# ruff: noqa: D102

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from app.domain.system.entities import System
from app.domain.system.entities import SystemVersion
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class SystemService:
    """CRUD for systems and their initial version."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
    ) -> None:
        """Store the unit-of-work factory."""
        self._uow_factory = uow_factory

    def create(
        self,
        name: str,
        description: str | None = None,
        created_by: UUID | None = None,
    ) -> System:
        """Create a system and an initial DRAFT version (number 1)."""
        with self._uow_factory() as uow:
            system = System(
                name=name,
                description=description,
                created_by=created_by,
            )
            version = SystemVersion(
                system_id=system.id,
                version_number=1,
                created_by=created_by,
            )
            uow.systems.add(system)
            uow.versions.add(version)
            return system

    def get(self, system_id: UUID) -> System:
        """Return one system by id."""
        with self._uow_factory() as uow:
            return uow.systems.get(system_id)

    def list(self) -> list[System]:
        """Return all systems."""
        with self._uow_factory() as uow:
            return uow.systems.list()

    def update(
        self,
        system_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> System:
        """Update system metadata."""
        with self._uow_factory() as uow:
            system = uow.systems.get(system_id)
            updates: dict[str, object] = {}
            if name is not None:
                updates["name"] = name
            if description is not None:
                updates["description"] = description
            if updates:
                system = system.model_copy(update=updates)
                uow.systems.update(system)
            return system

    def delete(self, system_id: UUID) -> None:
        """Remove a system and its versions (cascade)."""
        with self._uow_factory() as uow:
            uow.systems.delete(system_id)

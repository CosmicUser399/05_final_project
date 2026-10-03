"""Application services for system versions."""

# ruff: noqa: D102

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID
from uuid import uuid4

from app.application.versioning import clone_version
from app.domain.errors import ValidationError
from app.domain.system.content import SystemVersionContent
from app.domain.system.entities import SystemVersion
from app.domain.system.entities import VersionStatus
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class VersionService:
    """List, create, transition and clone system versions."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
    ) -> None:
        """Store the unit-of-work factory."""
        self._uow_factory = uow_factory

    def list_for_system(self, system_id: UUID) -> list[SystemVersion]:
        """Return all versions of a system."""
        with self._uow_factory() as uow:
            uow.systems.get(system_id)
            return uow.versions.list_for_system(system_id)

    def get(self, version_id: UUID) -> SystemVersion:
        """Return one version."""
        with self._uow_factory() as uow:
            return uow.versions.get(version_id)

    def create(
        self,
        system_id: UUID,
        *,
        clone_from: UUID | None = None,
        comment: str | None = None,
        created_by: UUID | None = None,
    ) -> SystemVersion:
        """Create an empty DRAFT or clone from an existing version."""
        with self._uow_factory() as uow:
            uow.systems.get(system_id)
            if clone_from is not None:
                source = uow.versions.get(clone_from)
                if source.system_id != system_id:
                    raise ValidationError(
                        "clone_from must belong to the same system",
                        entity="SystemVersion",
                        entity_id=str(clone_from),
                    )
                return clone_version(uow, clone_from, created_by=created_by)

            existing = uow.versions.list_for_system(system_id)
            next_number = (
                max(v.version_number for v in existing) + 1 if existing else 1
            )
            version = SystemVersion(
                system_id=system_id,
                lineage_id=uuid4(),
                version_number=next_number,
                comment=comment,
                created_by=created_by,
            )
            uow.versions.add(version)
            return version

    def transition(
        self,
        version_id: UUID,
        target_status: VersionStatus,
    ) -> SystemVersion:
        """Change version lifecycle status."""
        with self._uow_factory() as uow:
            version = uow.versions.get(version_id)
            version.transition_to(target_status)
            uow.versions.update(version)
            return version

    def clone(
        self,
        version_id: UUID,
        created_by: UUID | None = None,
    ) -> SystemVersion:
        """Clone a version into a new DRAFT."""
        with self._uow_factory() as uow:
            return clone_version(uow, version_id, created_by=created_by)

    def get_model(
        self,
        version_id: UUID,
    ) -> tuple[SystemVersion, SystemVersionContent]:
        """Return version metadata and full content."""
        with self._uow_factory() as uow:
            version = uow.versions.get(version_id)
            content = uow.content.load_content(version_id)
            return version, content

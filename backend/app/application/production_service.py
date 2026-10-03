"""Production function and impact CRUD."""

# ruff: noqa: D102, D107

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.application.audit import write_audit
from app.domain.production.entities import ProductionFunction
from app.domain.production.entities import ProductionImpact
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class ProductionService:
    """Manage production functions and failure impacts."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def list_functions(self, version_id: UUID) -> list[ProductionFunction]:
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            return uow.content.list_production_functions(version_id)

    def get_function(self, function_id: UUID) -> ProductionFunction:
        with self._uow_factory() as uow:
            return uow.content.get_production_function(function_id)

    def create_function(
        self,
        version_id: UUID,
        data: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> ProductionFunction:
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            function = ProductionFunction(version_id=version_id, **data)
            uow.content.save_production_function(function)
            write_audit(
                uow,
                version_id=version_id,
                entity_type="ProductionFunction",
                entity_id=function.id,
                action="CREATE",
                actor_id=actor_id,
                new_value=function,
                source=source,
                reason=reason,
            )
            return function

    def update_function(
        self,
        function_id: UUID,
        data: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> ProductionFunction:
        with self._uow_factory() as uow:
            current = uow.content.get_production_function(function_id)
            updated = current.model_copy(update=data)
            uow.content.save_production_function(updated)
            write_audit(
                uow,
                version_id=updated.version_id,
                entity_type="ProductionFunction",
                entity_id=updated.id,
                action="UPDATE",
                actor_id=actor_id,
                old_value=current,
                new_value=updated,
                source=source,
                reason=reason,
            )
            return updated

    def delete_function(
        self,
        function_id: UUID,
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> None:
        with self._uow_factory() as uow:
            removed = uow.content.delete_production_function(function_id)
            write_audit(
                uow,
                version_id=removed.version_id,
                entity_type="ProductionFunction",
                entity_id=removed.id,
                action="DELETE",
                actor_id=actor_id,
                old_value=removed,
                source=source,
                reason=reason,
            )

    def list_impacts(self, version_id: UUID) -> list[ProductionImpact]:
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            return uow.content.list_production_impacts(version_id)

    def get_impact(self, impact_id: UUID) -> ProductionImpact:
        with self._uow_factory() as uow:
            return uow.content.get_production_impact(impact_id)

    def create_impact(
        self,
        version_id: UUID,
        data: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> ProductionImpact:
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            impact = ProductionImpact(version_id=version_id, **data)
            uow.content.save_production_impact(impact)
            write_audit(
                uow,
                version_id=version_id,
                entity_type="ProductionImpact",
                entity_id=impact.id,
                action="CREATE",
                actor_id=actor_id,
                new_value=impact,
                source=source,
                reason=reason,
            )
            return impact

    def update_impact(
        self,
        impact_id: UUID,
        data: dict[str, Any],
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> ProductionImpact:
        with self._uow_factory() as uow:
            current = uow.content.get_production_impact(impact_id)
            updated = current.model_copy(update=data)
            uow.content.save_production_impact(updated)
            write_audit(
                uow,
                version_id=updated.version_id,
                entity_type="ProductionImpact",
                entity_id=updated.id,
                action="UPDATE",
                actor_id=actor_id,
                old_value=current,
                new_value=updated,
                source=source,
                reason=reason,
            )
            return updated

    def delete_impact(
        self,
        impact_id: UUID,
        *,
        actor_id: UUID | None = None,
        source: str | None = None,
        reason: str | None = None,
    ) -> None:
        with self._uow_factory() as uow:
            removed = uow.content.delete_production_impact(impact_id)
            write_audit(
                uow,
                version_id=removed.version_id,
                entity_type="ProductionImpact",
                entity_id=removed.id,
                action="DELETE",
                actor_id=actor_id,
                old_value=removed,
                source=source,
                reason=reason,
            )

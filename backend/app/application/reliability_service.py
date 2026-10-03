"""Generate and validate compiled reliability models."""

# ruff: noqa: D102

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID
from uuid import uuid4

from sqlalchemy import select

from app.domain.errors import NotFoundError
from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiler import ReliabilityCompiler
from app.domain.reliability.model_validation import validate_for_compile
from app.domain.validation import ValidationReport
from app.infrastructure.db.models import ReliabilityModelRow
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork


class ReliabilityService:
    """Compile, persist and validate reliability models."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
        compiler: ReliabilityCompiler | None = None,
    ) -> None:
        """Store dependencies."""
        self._uow_factory = uow_factory
        self._compiler = compiler or ReliabilityCompiler()

    def validate(self, version_id: UUID) -> ValidationReport:
        """Run validation levels 2-5 for a version."""
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            content = uow.content.load_content(version_id)
            return validate_for_compile(content)

    def generate(
        self,
        version_id: UUID,
        *,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Compile and persist a reliability model snapshot."""
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            content = uow.content.load_content(version_id)
            compiled = self._compiler.compile(version_id, content)
            row = ReliabilityModelRow(
                id=uuid4(),
                version_id=version_id,
                model_hash=compiled.model_hash(),
                snapshot_json=compiled.model_dump(mode="json"),
                validation_status="VALID",
                notes=notes,
            )
            uow.session.add(row)
            uow.session.flush()
            uow.session.refresh(row)
            return row.as_dict()

    def get_latest(self, version_id: UUID) -> dict[str, Any] | None:
        """Return the newest reliability model for a version."""
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            row = uow.session.scalars(
                select(ReliabilityModelRow)
                .where(ReliabilityModelRow.version_id == version_id)
                .order_by(ReliabilityModelRow.generated_at.desc())
            ).first()
            return None if row is None else row.as_dict()

    def get(self, model_id: UUID) -> dict[str, Any]:
        """Return one reliability model by id."""
        with self._uow_factory() as uow:
            row = uow.session.get(ReliabilityModelRow, model_id)
            if row is None:
                raise NotFoundError(
                    "reliability model not found",
                    entity="ReliabilityModel",
                    entity_id=str(model_id),
                )
            return row.as_dict()

    def compile_only(
        self,
        version_id: UUID,
    ) -> CompiledModel:
        """Compile without persisting (for tests and overlays)."""
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            content = uow.content.load_content(version_id)
            return self._compiler.compile(version_id, content)

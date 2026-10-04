"""Load curated demo datasets into Domain DB."""

# ruff: noqa: D102, D107

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID
from uuid import uuid4

from app.application.excel_service import ExcelService
from app.domain.system.entities import System
from app.domain.system.entities import SystemVersion
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.demo.upp100 import DATASET_LABEL
from app.infrastructure.demo.upp100 import load_upp100_seed_file
from app.infrastructure.demo.upp100 import write_upp100_seed_file


class DemoService:
    """Seed demo plants marked for software testing."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
        excel_service: ExcelService | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._excel = excel_service or ExcelService(uow_factory)

    def seed_upp100(
        self,
        *,
        write_seed_file: bool = True,
        actor_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Create УПП-100 system+version and load the demo seed."""
        if write_seed_file:
            write_upp100_seed_file()
        preview = load_upp100_seed_file()
        with self._uow_factory() as uow:
            system = System(
                name=preview.system_name or "УПП-100",
                description=preview.system_description,
            )
            uow.systems.add(system)
            version = SystemVersion(
                system_id=system.id,
                lineage_id=uuid4(),
                version_number=1,
                comment=f"demo seed {DATASET_LABEL}",
                created_by=actor_id,
            )
            uow.versions.add(version)
            imported = self._excel.apply_preview(
                uow,
                version.id,
                preview,
                actor_id=actor_id,
                reason="upp100 demo seed",
                source="demo_seed",
            )
            return {
                "system_id": str(system.id),
                "version_id": str(version.id),
                "dataset_label": DATASET_LABEL,
                "for_software_testing": True,
                "equipment_count": imported["imported"]["equipment"],
                "failure_modes": imported["imported"]["failure_modes"],
                "diagnostics": imported["imported"]["diagnostics"],
                "pf_demo_tag": "P-101",
            }

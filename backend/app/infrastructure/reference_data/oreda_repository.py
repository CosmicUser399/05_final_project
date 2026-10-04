"""OREDA reference parameter repository and CSV ingestion."""

from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from uuid import UUID
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.provenance import Confidence
from app.domain.provenance import ReferenceSource
from app.domain.provenance import SourceType
from app.domain.reference.entities import ParameterKind
from app.domain.reference.entities import ReferenceParameter
from app.infrastructure.db.models.reference import ReferenceParameterRow
from app.infrastructure.db.models.system import ReferenceSourceRow

logger = logging.getLogger(__name__)

SEEDS_DIR = Path(__file__).resolve().parent / "seeds"
DEFAULT_OREDA_CSV = SEEDS_DIR / "oreda_demo_parameters.csv"

OREDA_SOURCE_TITLE = "OREDA demo extract (synthetic)"
OREDA_SOURCE_EDITION = "demo-1.0"


def _row_to_parameter(row: ReferenceParameterRow) -> ReferenceParameter:
    return ReferenceParameter(
        id=row.id,
        source_id=row.source_id,
        equipment_class=row.equipment_class,
        equipment_class_code=row.equipment_class_code,
        failure_mode_code=row.failure_mode_code,
        failure_mode_name=row.failure_mode_name,
        parameter_name=row.parameter_name,
        parameter_kind=ParameterKind(row.parameter_kind),
        value=row.value,
        unit=row.unit,
        distribution_type=row.distribution_type,
        distribution_params_json=row.distribution_params_json,
        source_type=SourceType(row.source_type),
        source_document=row.source_document,
        source_reference=row.source_reference,
        confidence=Confidence(row.confidence),
        notes=row.notes,
    )


def _source_to_domain(row: ReferenceSourceRow) -> ReferenceSource:
    return ReferenceSource(
        id=row.id,
        source_type=SourceType(row.source_type),
        title=row.title,
        edition=row.edition,
        locator=row.locator,
    )


class OREDARepository:
    """Load and search curated OREDA-style parameters.

    Business logic never hard-codes OREDA numbers; this repository is
    the only place that reads extracts from disk into Domain DB.
    """

    def __init__(self, session: Session) -> None:
        """Bind a SQLAlchemy session."""
        self._session = session

    def ensure_source(self) -> ReferenceSource:
        """Return the demo OREDA source row, creating it if needed."""
        stmt = select(ReferenceSourceRow).where(
            ReferenceSourceRow.source_type == SourceType.OREDA.value,
            ReferenceSourceRow.title == OREDA_SOURCE_TITLE,
        )
        row = self._session.scalars(stmt).first()
        if row is None:
            row = ReferenceSourceRow(
                id=uuid4(),
                source_type=SourceType.OREDA.value,
                title=OREDA_SOURCE_TITLE,
                edition=OREDA_SOURCE_EDITION,
                locator="infrastructure/reference_data/seeds",
            )
            self._session.add(row)
            self._session.flush()
        return _source_to_domain(row)

    def count_parameters(self) -> int:
        """Return how many OREDA parameters are stored."""
        stmt = (
            select(func.count())
            .select_from(ReferenceParameterRow)
            .where(ReferenceParameterRow.source_type == SourceType.OREDA.value)
        )
        return int(self._session.scalar(stmt) or 0)

    def ingest_csv(
        self,
        path: Path | None = None,
        *,
        replace: bool = False,
    ) -> int:
        """Ingest a curated CSV extract; return inserted row count."""
        csv_path = path or DEFAULT_OREDA_CSV
        if not csv_path.is_file():
            raise FileNotFoundError(f"OREDA CSV not found: {csv_path}")

        source = self.ensure_source()
        if replace:
            existing = select(ReferenceParameterRow).where(
                ReferenceParameterRow.source_id == source.id
            )
            for row in self._session.scalars(existing).all():
                self._session.delete(row)
            self._session.flush()
        elif self.count_parameters() > 0:
            logger.info("OREDA parameters already loaded; skip ingest")
            return 0

        inserted = 0
        with csv_path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                params_raw = (
                    raw.get("distribution_params_json") or ""
                ).strip()
                params: dict[str, float] | None = None
                if params_raw:
                    loaded = json.loads(params_raw)
                    params = {str(k): float(v) for k, v in loaded.items()}
                confidence_raw = (raw.get("confidence") or "MEDIUM").strip()
                row = ReferenceParameterRow(
                    id=uuid4(),
                    source_id=source.id,
                    equipment_class=raw["equipment_class"].strip(),
                    equipment_class_code=(
                        (raw.get("equipment_class_code") or "").strip() or None
                    ),
                    failure_mode_code=(
                        (raw.get("failure_mode_code") or "").strip() or None
                    ),
                    failure_mode_name=(
                        (raw.get("failure_mode_name") or "").strip() or None
                    ),
                    parameter_name=raw["parameter_name"].strip(),
                    parameter_kind=raw["parameter_kind"].strip(),
                    value=float(raw["value"]),
                    unit=raw["unit"].strip(),
                    distribution_type=(
                        (raw.get("distribution_type") or "").strip() or None
                    ),
                    distribution_params_json=params,
                    source_type=SourceType.OREDA.value,
                    source_document=OREDA_SOURCE_TITLE,
                    source_reference=raw["source_reference"].strip(),
                    confidence=confidence_raw,
                    notes=(raw.get("notes") or "").strip() or None,
                )
                self._session.add(row)
                inserted += 1
        self._session.flush()
        logger.info("ingested %s OREDA parameter rows", inserted)
        return inserted

    def get(self, parameter_id: UUID) -> ReferenceParameter | None:
        """Return one parameter by id."""
        row = self._session.get(ReferenceParameterRow, parameter_id)
        if row is None:
            return None
        return _row_to_parameter(row)

    def search(
        self,
        *,
        query: str | None = None,
        equipment_class: str | None = None,
        equipment_class_code: str | None = None,
        parameter_kind: str | None = None,
        limit: int = 50,
    ) -> list[ReferenceParameter]:
        """Search OREDA parameters by class / free text."""
        stmt = select(ReferenceParameterRow).where(
            ReferenceParameterRow.source_type == SourceType.OREDA.value
        )
        if equipment_class_code:
            code = equipment_class_code.strip().upper()
            stmt = stmt.where(
                func.upper(ReferenceParameterRow.equipment_class_code) == code
            )
        if equipment_class:
            needle = f"%{equipment_class.strip().lower()}%"
            stmt = stmt.where(
                func.lower(ReferenceParameterRow.equipment_class).like(needle)
            )
        if parameter_kind:
            stmt = stmt.where(
                ReferenceParameterRow.parameter_kind
                == parameter_kind.strip().upper()
            )
        if query:
            needle = f"%{query.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(ReferenceParameterRow.equipment_class).like(
                        needle
                    ),
                    func.lower(
                        ReferenceParameterRow.equipment_class_code
                    ).like(needle),
                    func.lower(ReferenceParameterRow.failure_mode_name).like(
                        needle
                    ),
                    func.lower(ReferenceParameterRow.parameter_name).like(
                        needle
                    ),
                    func.lower(ReferenceParameterRow.source_reference).like(
                        needle
                    ),
                )
            )
        stmt = stmt.order_by(
            ReferenceParameterRow.equipment_class,
            ReferenceParameterRow.parameter_name,
        ).limit(max(1, min(limit, 200)))
        return [
            _row_to_parameter(row) for row in self._session.scalars(stmt).all()
        ]

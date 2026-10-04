"""ISO 14224 taxonomy repository and JSON ingestion."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from uuid import UUID
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.equipment.entities import Taxonomy
from app.domain.equipment.entities import TaxonomyKind
from app.domain.equipment.entities import TaxonomyNode
from app.domain.provenance import ReferenceSource
from app.domain.provenance import SourceType
from app.infrastructure.db.models.equipment import TaxonomyNodeRow
from app.infrastructure.db.models.equipment import TaxonomyRow
from app.infrastructure.db.models.system import ReferenceSourceRow

logger = logging.getLogger(__name__)

SEEDS_DIR = Path(__file__).resolve().parent / "seeds"
DEFAULT_ISO_JSON = SEEDS_DIR / "iso14224_demo_taxonomy.json"


def _taxonomy_from_row(row: TaxonomyRow) -> Taxonomy:
    return Taxonomy(
        id=row.id,
        name=row.name,
        kind=TaxonomyKind(row.kind),
        version_label=row.version_label,
    )


def _node_from_row(row: TaxonomyNodeRow) -> TaxonomyNode:
    return TaxonomyNode(
        id=row.id,
        taxonomy_id=row.taxonomy_id,
        parent_id=row.parent_id,
        code=row.code,
        name=row.name,
    )


def _source_to_domain(row: ReferenceSourceRow) -> ReferenceSource:
    return ReferenceSource(
        id=row.id,
        source_type=SourceType(row.source_type),
        title=row.title,
        edition=row.edition,
        locator=row.locator,
    )


class ISO14224Repository:
    """Load and search ISO 14224 taxonomy nodes from curated JSON."""

    def __init__(self, session: Session) -> None:
        """Bind a SQLAlchemy session."""
        self._session = session

    def ensure_source(
        self,
        *,
        title: str,
        edition: str | None,
        locator: str | None,
    ) -> ReferenceSource:
        """Return the ISO source row, creating it if needed."""
        stmt = select(ReferenceSourceRow).where(
            ReferenceSourceRow.source_type == SourceType.ISO_14224.value,
            ReferenceSourceRow.title == title,
        )
        row = self._session.scalars(stmt).first()
        if row is None:
            row = ReferenceSourceRow(
                id=uuid4(),
                source_type=SourceType.ISO_14224.value,
                title=title,
                edition=edition,
                locator=locator,
            )
            self._session.add(row)
            self._session.flush()
        return _source_to_domain(row)

    def get_taxonomy(self) -> Taxonomy | None:
        """Return the ISO_14224 taxonomy if present."""
        stmt = select(TaxonomyRow).where(
            TaxonomyRow.kind == TaxonomyKind.ISO_14224.value
        )
        row = self._session.scalars(stmt).first()
        if row is None:
            return None
        return _taxonomy_from_row(row)

    def count_nodes(self) -> int:
        """Return number of ISO taxonomy nodes."""
        taxonomy = self.get_taxonomy()
        if taxonomy is None:
            return 0
        stmt = (
            select(func.count())
            .select_from(TaxonomyNodeRow)
            .where(TaxonomyNodeRow.taxonomy_id == taxonomy.id)
        )
        return int(self._session.scalar(stmt) or 0)

    def ingest_json(
        self,
        path: Path | None = None,
        *,
        replace: bool = False,
    ) -> int:
        """Ingest a curated ISO taxonomy JSON; return node count."""
        json_path = path or DEFAULT_ISO_JSON
        if not json_path.is_file():
            raise FileNotFoundError(f"ISO JSON not found: {json_path}")

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        tax_meta = payload["taxonomy"]
        source_meta = payload["source"]
        self.ensure_source(
            title=source_meta["title"],
            edition=source_meta.get("edition"),
            locator=source_meta.get("locator"),
        )

        existing = self.get_taxonomy()
        if existing is not None and not replace:
            if self.count_nodes() > 0:
                logger.info("ISO taxonomy already loaded; skip ingest")
                return 0
            taxonomy = existing
        else:
            if existing is not None and replace:
                nodes = select(TaxonomyNodeRow).where(
                    TaxonomyNodeRow.taxonomy_id == existing.id
                )
                for node in self._session.scalars(nodes).all():
                    self._session.delete(node)
                tax_row = self._session.get(TaxonomyRow, existing.id)
                if tax_row is not None:
                    self._session.delete(tax_row)
                self._session.flush()
            taxonomy_row = TaxonomyRow(
                id=uuid4(),
                name=tax_meta["name"],
                kind=TaxonomyKind.ISO_14224.value,
                version_label=tax_meta.get("version_label"),
            )
            self._session.add(taxonomy_row)
            self._session.flush()
            taxonomy = _taxonomy_from_row(taxonomy_row)

        code_to_id: dict[str, UUID] = {}
        inserted = 0
        # Parents must be inserted before children; seed is ordered.
        for node in payload["nodes"]:
            parent_code = node.get("parent_code")
            parent_id = code_to_id.get(parent_code) if parent_code else None
            row = TaxonomyNodeRow(
                id=uuid4(),
                taxonomy_id=taxonomy.id,
                parent_id=parent_id,
                code=str(node["code"]).strip(),
                name=str(node["name"]).strip(),
            )
            self._session.add(row)
            code_to_id[row.code] = row.id
            inserted += 1
        self._session.flush()
        logger.info("ingested %s ISO taxonomy nodes", inserted)
        return inserted

    def get_node(self, node_id: UUID) -> TaxonomyNode | None:
        """Return one taxonomy node."""
        row = self._session.get(TaxonomyNodeRow, node_id)
        if row is None:
            return None
        return _node_from_row(row)

    def find_by_code(self, code: str) -> TaxonomyNode | None:
        """Exact match on ISO code (case-insensitive)."""
        taxonomy = self.get_taxonomy()
        if taxonomy is None:
            return None
        needle = code.strip().upper()
        stmt = select(TaxonomyNodeRow).where(
            TaxonomyNodeRow.taxonomy_id == taxonomy.id,
            func.upper(TaxonomyNodeRow.code) == needle,
        )
        row = self._session.scalars(stmt).first()
        if row is None:
            return None
        return _node_from_row(row)

    def search_nodes(
        self,
        *,
        query: str | None = None,
        limit: int = 50,
    ) -> list[TaxonomyNode]:
        """Search taxonomy nodes by code or name substring."""
        taxonomy = self.get_taxonomy()
        if taxonomy is None:
            return []
        stmt = select(TaxonomyNodeRow).where(
            TaxonomyNodeRow.taxonomy_id == taxonomy.id
        )
        if query:
            needle = f"%{query.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(TaxonomyNodeRow.code).like(needle),
                    func.lower(TaxonomyNodeRow.name).like(needle),
                )
            )
        stmt = stmt.order_by(TaxonomyNodeRow.code).limit(
            max(1, min(limit, 200))
        )
        return [
            _node_from_row(row) for row in self._session.scalars(stmt).all()
        ]

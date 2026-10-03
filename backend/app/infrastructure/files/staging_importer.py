"""Safe import of Fabricate SQLite staging artifacts into DTOs."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from app.domain.ai.dto import EquipmentProposalPayload
from app.domain.ai.dto import GeneratedComponent
from app.domain.ai.dto import GeneratedConnection
from app.domain.ai.dto import GeneratedEquipment
from app.domain.ai.dto import GeneratedFailureMode
from app.domain.ai.dto import GeneratedMaintenanceTask
from app.domain.ai.dto import GeneratedSystemBrief
from app.domain.equipment.entities import ConnectionType
from app.domain.equipment.entities import Criticality
from app.domain.equipment.entities import OperatingMode
from app.domain.equipment.entities import StandbyMode
from app.domain.errors import ValidationError
from app.domain.provenance import ValueStatus
from app.infrastructure.files.staging_schema import ALLOWED_CATEGORIES
from app.infrastructure.files.staging_schema import WHITELISTED_TABLES


class StagingImporter:
    """Open a downloaded SQLite artifact read-only and map to DTOs."""

    def __init__(
        self,
        *,
        max_bytes: int = 50_000_000,
        max_equipment_rows: int = 500,
    ) -> None:
        """Configure size and row limits."""
        self._max_bytes = max_bytes
        self._max_equipment_rows = max_equipment_rows

    def import_bytes(
        self,
        data: bytes,
        *,
        conversation_id: str,
        brief: GeneratedSystemBrief | None = None,
    ) -> EquipmentProposalPayload:
        """Validate bytes and return a proposal payload."""
        if len(data) > self._max_bytes:
            raise ValidationError(
                f"artifact exceeds {self._max_bytes} bytes",
                code="STAGING_TOO_LARGE",
                entity="StagingArtifact",
            )
        if len(data) < 16 or data[:16] != b"SQLite format 3\x00":
            raise ValidationError(
                "artifact is not a SQLite database",
                code="STAGING_INVALID_FORMAT",
                entity="StagingArtifact",
            )
        with tempfile.TemporaryDirectory(prefix="fab_stage_") as tmp:
            path = Path(tmp) / "staging.db"
            path.write_bytes(data)
            return self.import_path(
                path,
                conversation_id=conversation_id,
                brief=brief,
            )

    def import_path(
        self,
        path: Path,
        *,
        conversation_id: str,
        brief: GeneratedSystemBrief | None = None,
    ) -> EquipmentProposalPayload:
        """Open ``path`` read-only and map whitelisted tables."""
        uri = f"file:{path.resolve().as_posix()}?mode=ro"
        try:
            conn = sqlite3.connect(uri, uri=True)
        except sqlite3.Error as exc:
            raise ValidationError(
                f"cannot open staging SQLite: {exc}",
                code="STAGING_OPEN_FAILED",
                entity="StagingArtifact",
            ) from exc
        try:
            conn.row_factory = sqlite3.Row
            check = conn.execute("PRAGMA integrity_check").fetchone()
            if check is None or str(check[0]).lower() != "ok":
                raise ValidationError(
                    "PRAGMA integrity_check failed",
                    code="STAGING_CORRUPT",
                    entity="StagingArtifact",
                )
            tables = self._list_tables(conn)
            equipment = self._read_equipment(conn, tables)
            components = self._read_components(conn, tables, equipment)
            connections = self._read_connections(conn, tables, equipment)
            failure_modes = self._read_failure_modes(conn, tables, equipment)
            maintenance = self._read_maintenance(conn, tables, equipment)
            self._assert_no_cycles(equipment)
        finally:
            conn.close()
        return EquipmentProposalPayload(
            brief=brief,
            equipment=equipment,
            components=components,
            connections=connections,
            failure_modes=failure_modes,
            maintenance_tasks=maintenance,
            metadata={
                "conversation_id": conversation_id,
                "generated_by": "fabricate",
                "staging_schema_version": "1",
            },
        )

    def _list_tables(self, conn: sqlite3.Connection) -> set[str]:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return {str(row[0]) for row in rows}

    def _table_columns(
        self,
        conn: sqlite3.Connection,
        table: str,
    ) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {str(row[1]) for row in rows}

    def _select_rows(
        self,
        conn: sqlite3.Connection,
        table: str,
        allowed: frozenset[str],
    ) -> list[dict[str, Any]]:
        cols = self._table_columns(conn, table) & allowed
        if not cols:
            return []
        if table not in WHITELISTED_TABLES:
            return []
        ordered = sorted(cols)
        # Table/column names come only from the whitelist constants.
        quoted_cols = ", ".join(f'"{name}"' for name in ordered)
        sql = f'SELECT {quoted_cols} FROM "{table}"'  # noqa: S608
        return [dict(row) for row in conn.execute(sql).fetchall()]

    def _read_equipment(
        self,
        conn: sqlite3.Connection,
        tables: set[str],
    ) -> list[GeneratedEquipment]:
        if "equipment" not in tables:
            raise ValidationError(
                "staging DB missing required table 'equipment'",
                code="STAGING_MISSING_TABLE",
                entity="equipment",
            )
        rows = self._select_rows(
            conn,
            "equipment",
            WHITELISTED_TABLES["equipment"],
        )
        if len(rows) > self._max_equipment_rows:
            raise ValidationError(
                f"equipment rows exceed {self._max_equipment_rows}",
                code="STAGING_TOO_MANY_ROWS",
                entity="equipment",
            )
        result: list[GeneratedEquipment] = []
        seen: set[str] = set()
        for row in rows:
            tag = str(row.get("tag") or "").strip()
            name = str(row.get("name") or "").strip()
            if not tag or not name:
                raise ValidationError(
                    "equipment row requires tag and name",
                    code="STAGING_INVALID_ROW",
                    entity="equipment",
                )
            if tag in seen:
                raise ValidationError(
                    f"duplicate equipment tag {tag!r}",
                    code="STAGING_DUPLICATE_TAG",
                    entity="equipment",
                    entity_id=tag,
                )
            seen.add(tag)
            category = _optional_str(row.get("category"))
            if category is not None and category not in ALLOWED_CATEGORIES:
                raise ValidationError(
                    f"invalid category {category!r}",
                    code="STAGING_INVALID_CATEGORY",
                    entity="equipment",
                    entity_id=tag,
                )
            result.append(
                GeneratedEquipment(
                    tag=tag,
                    name=name,
                    description=_optional_str(row.get("description")),
                    parent_tag=_optional_str(row.get("parent_tag")),
                    category=category,
                    equipment_class=_optional_str(
                        row.get("equipment_class")
                    ),
                    equipment_type=_optional_str(row.get("equipment_type")),
                    location=_optional_str(row.get("location")),
                    quantity=_int_or(row.get("quantity"), 1),
                    criticality=_enum_or(
                        row.get("criticality"),
                        Criticality,
                        Criticality.MEDIUM,
                    ),
                    operating_mode=_enum_or(
                        row.get("operating_mode"),
                        OperatingMode,
                        OperatingMode.CONTINUOUS,
                    ),
                    standby_mode=_enum_or(
                        row.get("standby_mode"),
                        StandbyMode,
                        StandbyMode.NONE,
                    ),
                    is_repairable=_bool_or(row.get("is_repairable"), True),
                    value_status=ValueStatus.ESTIMATED,
                )
            )
        tags = {item.tag for item in result}
        for item in result:
            if item.parent_tag and item.parent_tag not in tags:
                raise ValidationError(
                    f"parent_tag {item.parent_tag!r} missing",
                    code="STAGING_BROKEN_PARENT",
                    entity="equipment",
                    entity_id=item.tag,
                )
        return result

    def _read_components(
        self,
        conn: sqlite3.Connection,
        tables: set[str],
        equipment: list[GeneratedEquipment],
    ) -> list[GeneratedComponent]:
        if "components" not in tables:
            return []
        tags = {item.tag for item in equipment}
        rows = self._select_rows(
            conn,
            "components",
            WHITELISTED_TABLES["components"],
        )
        result: list[GeneratedComponent] = []
        for row in rows:
            eq_tag = str(row.get("equipment_tag") or "").strip()
            name = str(row.get("name") or "").strip()
            if not eq_tag or not name:
                raise ValidationError(
                    "component requires equipment_tag and name",
                    code="STAGING_INVALID_ROW",
                    entity="components",
                )
            if eq_tag not in tags:
                raise ValidationError(
                    f"component references missing tag {eq_tag!r}",
                    code="STAGING_BROKEN_REF",
                    entity="components",
                )
            result.append(
                GeneratedComponent(
                    equipment_tag=eq_tag,
                    name=name,
                    description=_optional_str(row.get("description")),
                    quantity=_int_or(row.get("quantity"), 1),
                )
            )
        return result

    def _read_connections(
        self,
        conn: sqlite3.Connection,
        tables: set[str],
        equipment: list[GeneratedEquipment],
    ) -> list[GeneratedConnection]:
        if "connections" not in tables:
            return []
        tags = {item.tag for item in equipment}
        rows = self._select_rows(
            conn,
            "connections",
            WHITELISTED_TABLES["connections"],
        )
        result: list[GeneratedConnection] = []
        for row in rows:
            from_tag = str(row.get("from_tag") or "").strip()
            to_tag = str(row.get("to_tag") or "").strip()
            if not from_tag or not to_tag:
                raise ValidationError(
                    "connection requires from_tag and to_tag",
                    code="STAGING_INVALID_ROW",
                    entity="connections",
                )
            if from_tag not in tags or to_tag not in tags:
                raise ValidationError(
                    f"connection references missing tag "
                    f"{from_tag!r}->{to_tag!r}",
                    code="STAGING_BROKEN_REF",
                    entity="connections",
                )
            result.append(
                GeneratedConnection(
                    from_tag=from_tag,
                    to_tag=to_tag,
                    connection_type=_enum_or(
                        row.get("connection_type"),
                        ConnectionType,
                        ConnectionType.PROCESS,
                    ),
                    description=_optional_str(row.get("description")),
                )
            )
        return result

    def _read_failure_modes(
        self,
        conn: sqlite3.Connection,
        tables: set[str],
        equipment: list[GeneratedEquipment],
    ) -> list[GeneratedFailureMode]:
        if "failure_modes" not in tables:
            return []
        tags = {item.tag for item in equipment}
        rows = self._select_rows(
            conn,
            "failure_modes",
            WHITELISTED_TABLES["failure_modes"],
        )
        result: list[GeneratedFailureMode] = []
        for row in rows:
            eq_tag = str(row.get("equipment_tag") or "").strip()
            name = str(row.get("name") or "").strip()
            if not eq_tag or not name or eq_tag not in tags:
                raise ValidationError(
                    "invalid failure_modes row",
                    code="STAGING_INVALID_ROW",
                    entity="failure_modes",
                )
            result.append(
                GeneratedFailureMode(
                    equipment_tag=eq_tag,
                    name=name,
                    description=_optional_str(row.get("description")),
                    is_detectable=_bool_or(row.get("is_detectable"), False),
                    value_status=ValueStatus.UNKNOWN,
                )
            )
        return result

    def _read_maintenance(
        self,
        conn: sqlite3.Connection,
        tables: set[str],
        equipment: list[GeneratedEquipment],
    ) -> list[GeneratedMaintenanceTask]:
        if "maintenance_tasks" not in tables:
            return []
        tags = {item.tag for item in equipment}
        rows = self._select_rows(
            conn,
            "maintenance_tasks",
            WHITELISTED_TABLES["maintenance_tasks"],
        )
        result: list[GeneratedMaintenanceTask] = []
        for row in rows:
            eq_tag = str(row.get("equipment_tag") or "").strip()
            name = str(row.get("name") or "").strip()
            if not eq_tag or not name or eq_tag not in tags:
                raise ValidationError(
                    "invalid maintenance_tasks row",
                    code="STAGING_INVALID_ROW",
                    entity="maintenance_tasks",
                )
            result.append(
                GeneratedMaintenanceTask(
                    equipment_tag=eq_tag,
                    name=name,
                    task_type=str(row.get("task_type") or "PREVENTIVE"),
                    value_status=ValueStatus.UNKNOWN,
                )
            )
        return result

    def _assert_no_cycles(
        self,
        equipment: list[GeneratedEquipment],
    ) -> None:
        parents = {
            item.tag: item.parent_tag
            for item in equipment
            if item.parent_tag
        }
        for tag in parents:
            seen: set[str] = set()
            current: str | None = tag
            while current is not None:
                if current in seen:
                    raise ValidationError(
                        f"parent cycle involving {tag!r}",
                        code="STAGING_PARENT_CYCLE",
                        entity="equipment",
                        entity_id=tag,
                    )
                seen.add(current)
                current = parents.get(current)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int_or(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(
            f"invalid integer {value!r}",
            code="STAGING_INVALID_ROW",
        ) from exc


def _bool_or(value: Any, default: bool) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return default


def _enum_or(value: Any, enum_cls: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    text = str(value).strip().upper()
    try:
        return enum_cls(text)
    except ValueError as exc:
        raise ValidationError(
            f"invalid {enum_cls.__name__} {value!r}",
            code="STAGING_INVALID_ENUM",
        ) from exc

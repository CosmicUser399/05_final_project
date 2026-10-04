"""Parse and validate Excel workbooks into import DTOs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from dataclasses import field
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from pydantic import BaseModel
from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from app.domain.equipment.entities import ConnectionType
from app.domain.equipment.entities import Criticality
from app.domain.equipment.entities import OperatingMode
from app.domain.equipment.entities import StandbyMode
from app.domain.errors import ValidationError
from app.domain.maintenance.entities import MaintenanceEffectType
from app.domain.maintenance.entities import MaintenanceTaskType
from app.domain.maintenance.entities import MaintenanceTrigger
from app.domain.provenance import Confidence
from app.domain.provenance import SourceType
from app.domain.reliability.distributions import parse_distribution
from app.domain.units import MassUnit
from app.domain.units import TimeUnit
from app.infrastructure.excel import schema as s


class ExcelIssue(BaseModel):
    """One validation issue from Excel parse/preview."""

    code: str
    message: str
    sheet: str | None = None
    row: int | None = None
    entity: str | None = None


class EquipmentImportRow(BaseModel):
    """Equipment row from Excel."""

    tag: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    parent_tag: str | None = None
    category: str | None = None
    equipment_class: str | None = None
    equipment_type: str | None = None
    location: str | None = None
    quantity: int = Field(default=1, ge=1)
    criticality: Criticality = Criticality.MEDIUM
    operating_mode: OperatingMode = OperatingMode.CONTINUOUS
    standby_mode: StandbyMode = StandbyMode.NONE
    is_repairable: bool = True


class ComponentImportRow(BaseModel):
    """Component row from Excel."""

    equipment_tag: str
    name: str
    description: str | None = None
    quantity: int = Field(default=1, ge=1)


class ConnectionImportRow(BaseModel):
    """Connection row from Excel."""

    from_tag: str
    to_tag: str
    connection_type: ConnectionType = ConnectionType.PROCESS
    description: str | None = None


class FailureModeImportRow(BaseModel):
    """Failure mode row from Excel."""

    equipment_tag: str
    name: str
    description: str | None = None
    is_detectable: bool = False
    component_name: str | None = None
    pf_value: float | None = None
    pf_unit: TimeUnit | None = None


class FailureDistributionImportRow(BaseModel):
    """Failure distribution row from Excel."""

    equipment_tag: str
    failure_mode_name: str
    distribution: dict[str, Any]
    source_type: SourceType = SourceType.USER_DEFINED
    confidence: Confidence = Confidence.MEDIUM
    source_reference: str | None = None
    generated_by: str | None = None


class MaintenanceImportRow(BaseModel):
    """Maintenance task row from Excel."""

    equipment_tag: str
    name: str
    task_type: MaintenanceTaskType
    trigger: MaintenanceTrigger
    failure_mode_name: str | None = None
    interval_value: float | None = None
    interval_unit: TimeUnit | None = None
    cost: float | None = None
    duration_distribution: dict[str, Any] | None = None
    duration_source_type: SourceType | None = None
    duration_confidence: Confidence | None = None


class MaintenanceEffectImportRow(BaseModel):
    """Maintenance effect row from Excel."""

    equipment_tag: str
    maintenance_name: str
    effect_type: MaintenanceEffectType
    failure_mode_name: str | None = None
    parameter: float | None = None


class DiagnosticImportRow(BaseModel):
    """Diagnostic task row from Excel."""

    equipment_tag: str
    failure_mode_name: str
    name: str
    method: str | None = None
    interval_value: float = Field(gt=0)
    interval_unit: TimeUnit
    detection_probability: float = Field(ge=0, le=1)
    false_positive_probability: float = Field(default=0, ge=0, le=1)


class ResourceImportRow(BaseModel):
    """Resource row from Excel."""

    name: str
    resource_type: str | None = None
    capacity: int = Field(default=1, ge=1)
    cost_per_hour: float | None = None


class SparePartImportRow(BaseModel):
    """Spare part row from Excel."""

    name: str
    stock: int = Field(default=0, ge=0)
    lead_time_value: float | None = None
    lead_time_unit: TimeUnit | None = None
    unit_cost: float | None = None


class ProductionImportRow(BaseModel):
    """Production function or impact row from Excel."""

    kind: str
    product: str | None = None
    nominal_rate_value: float | None = None
    mass_unit: MassUnit | None = None
    time_unit: TimeUnit | None = None
    equipment_tag: str | None = None
    failure_mode_name: str | None = None
    loss_fraction: float | None = None


@dataclass
class ImportPreview:
    """Parsed Excel payload ready for preview or commit."""

    system_name: str | None = None
    system_description: str | None = None
    dataset_label: str | None = None
    for_software_testing: bool = True
    equipment: list[EquipmentImportRow] = field(default_factory=list)
    components: list[ComponentImportRow] = field(default_factory=list)
    connections: list[ConnectionImportRow] = field(default_factory=list)
    failure_modes: list[FailureModeImportRow] = field(default_factory=list)
    failure_distributions: list[FailureDistributionImportRow] = field(
        default_factory=list
    )
    maintenance: list[MaintenanceImportRow] = field(default_factory=list)
    maintenance_effects: list[MaintenanceEffectImportRow] = field(
        default_factory=list
    )
    diagnostics: list[DiagnosticImportRow] = field(default_factory=list)
    resources: list[ResourceImportRow] = field(default_factory=list)
    spare_parts: list[SparePartImportRow] = field(default_factory=list)
    production: list[ProductionImportRow] = field(default_factory=list)
    issues: list[ExcelIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True when there are no blocking issues."""
        return not any(
            not issue.code.endswith("_WARN") for issue in self.issues
        )

    def summary(self) -> dict[str, Any]:
        """Return counts for API responses."""
        return {
            "is_valid": self.is_valid,
            "system_name": self.system_name,
            "dataset_label": self.dataset_label,
            "for_software_testing": self.for_software_testing,
            "counts": {
                "equipment": len(self.equipment),
                "components": len(self.components),
                "connections": len(self.connections),
                "failure_modes": len(self.failure_modes),
                "failure_distributions": len(self.failure_distributions),
                "maintenance": len(self.maintenance),
                "maintenance_effects": len(self.maintenance_effects),
                "diagnostics": len(self.diagnostics),
                "resources": len(self.resources),
                "spare_parts": len(self.spare_parts),
                "production": len(self.production),
            },
            "issues": [issue.model_dump() for issue in self.issues],
        }


def _cell_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell_bool(value: object, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "да"}:
        return True
    if text in {"0", "false", "no", "n", "нет"}:
        return False
    return default


def _read_sheet(
    ws: Worksheet,
    columns: tuple[str, ...],
) -> list[dict[str, Any]]:
    header_cells = [
        _cell_str(ws.cell(row=1, column=i).value) for i in range(1, 64)
    ]
    headers = [h for h in header_cells if h is not None]
    if not headers:
        return []
    index = {name: idx for idx, name in enumerate(headers)}
    missing = [c for c in columns if c not in index and c == columns[0]]
    # Only require the first identifying columns; others optional.
    rows: list[dict[str, Any]] = []
    for row_idx in range(2, (ws.max_row or 1) + 1):
        raw: dict[str, Any] = {"_row": row_idx}
        empty = True
        for name in columns:
            col = index.get(name)
            if col is None:
                continue
            value = ws.cell(row=row_idx, column=col + 1).value
            if value is not None and str(value).strip() != "":
                empty = False
            raw[name] = value
        if not empty:
            rows.append(raw)
    if missing:
        pass
    return rows


def parse_workbook(data: bytes) -> ImportPreview:
    """Parse ``.xlsx`` bytes into an ``ImportPreview``."""
    if len(data) > s.EXCEL_MAX_BYTES:
        raise ValidationError(
            f"Excel file exceeds {s.EXCEL_MAX_BYTES} bytes",
            code="EXCEL_TOO_LARGE",
            entity="ExcelWorkbook",
        )
    if len(data) < 4 or data[:2] != b"PK":
        raise ValidationError(
            "file is not a valid .xlsx workbook",
            code="EXCEL_INVALID_FORMAT",
            entity="ExcelWorkbook",
        )
    try:
        wb = load_workbook(BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise ValidationError(
            f"cannot open workbook: {exc}",
            code="EXCEL_INVALID_FORMAT",
            entity="ExcelWorkbook",
        ) from exc

    preview = ImportPreview()
    names = set(wb.sheetnames)
    for required in (s.SHEET_EQUIPMENT,):
        if required not in names:
            preview.issues.append(
                ExcelIssue(
                    code="EXCEL_MISSING_SHEET",
                    message=f"missing sheet {required}",
                    sheet=required,
                )
            )
            return preview

    if s.SHEET_SYSTEMS in names:
        for raw in _read_sheet(wb[s.SHEET_SYSTEMS], s.SYSTEM_COLUMNS):
            preview.system_name = _cell_str(raw.get("name"))
            preview.system_description = _cell_str(raw.get("description"))
            preview.dataset_label = _cell_str(raw.get("dataset_label"))
            preview.for_software_testing = _cell_bool(
                raw.get("for_software_testing"),
                default=True,
            )
            break

    for raw in _read_sheet(wb[s.SHEET_EQUIPMENT], s.EQUIPMENT_COLUMNS):
        try:
            preview.equipment.append(
                EquipmentImportRow(
                    tag=_cell_str(raw.get("tag")) or "",
                    name=_cell_str(raw.get("name")) or "",
                    description=_cell_str(raw.get("description")),
                    parent_tag=_cell_str(raw.get("parent_tag")),
                    category=_cell_str(raw.get("category")),
                    equipment_class=_cell_str(raw.get("equipment_class")),
                    equipment_type=_cell_str(raw.get("equipment_type")),
                    location=_cell_str(raw.get("location")),
                    quantity=int(raw.get("quantity") or 1),
                    criticality=Criticality(
                        _cell_str(raw.get("criticality")) or "MEDIUM"
                    ),
                    operating_mode=OperatingMode(
                        _cell_str(raw.get("operating_mode")) or "CONTINUOUS"
                    ),
                    standby_mode=StandbyMode(
                        _cell_str(raw.get("standby_mode")) or "NONE"
                    ),
                    is_repairable=_cell_bool(
                        raw.get("is_repairable"),
                        default=True,
                    ),
                )
            )
        except (PydanticValidationError, ValueError, TypeError) as exc:
            preview.issues.append(
                ExcelIssue(
                    code="EXCEL_ROW_INVALID",
                    message=str(exc),
                    sheet=s.SHEET_EQUIPMENT,
                    row=int(raw.get("_row", 0)),
                    entity="Equipment",
                )
            )

    tags = {eq.tag for eq in preview.equipment}
    if len(tags) != len(preview.equipment):
        preview.issues.append(
            ExcelIssue(
                code="EXCEL_DUPLICATE_TAG",
                message="equipment tags must be unique",
                sheet=s.SHEET_EQUIPMENT,
                entity="Equipment",
            )
        )

    if s.SHEET_COMPONENTS in names:
        for raw in _read_sheet(wb[s.SHEET_COMPONENTS], s.COMPONENT_COLUMNS):
            try:
                comp_row = ComponentImportRow(
                    equipment_tag=_cell_str(raw.get("equipment_tag")) or "",
                    name=_cell_str(raw.get("name")) or "",
                    description=_cell_str(raw.get("description")),
                    quantity=int(raw.get("quantity") or 1),
                )
                if comp_row.equipment_tag not in tags:
                    preview.issues.append(
                        ExcelIssue(
                            code="EXCEL_UNKNOWN_TAG",
                            message=(
                                "unknown equipment_tag "
                                f"{comp_row.equipment_tag}"
                            ),
                            sheet=s.SHEET_COMPONENTS,
                            row=int(raw.get("_row", 0)),
                        )
                    )
                else:
                    preview.components.append(comp_row)
            except (PydanticValidationError, ValueError, TypeError) as exc:
                preview.issues.append(
                    ExcelIssue(
                        code="EXCEL_ROW_INVALID",
                        message=str(exc),
                        sheet=s.SHEET_COMPONENTS,
                        row=int(raw.get("_row", 0)),
                    )
                )

    if s.SHEET_CONNECTIONS in names:
        for raw in _read_sheet(wb[s.SHEET_CONNECTIONS], s.CONNECTION_COLUMNS):
            try:
                conn_row = ConnectionImportRow(
                    from_tag=_cell_str(raw.get("from_tag")) or "",
                    to_tag=_cell_str(raw.get("to_tag")) or "",
                    connection_type=ConnectionType(
                        _cell_str(raw.get("connection_type")) or "PROCESS"
                    ),
                    description=_cell_str(raw.get("description")),
                )
                if (
                    conn_row.from_tag not in tags
                    or conn_row.to_tag not in tags
                ):
                    preview.issues.append(
                        ExcelIssue(
                            code="EXCEL_UNKNOWN_TAG",
                            message=(
                                "connection tags "
                                f"{conn_row.from_tag}->{conn_row.to_tag}"
                            ),
                            sheet=s.SHEET_CONNECTIONS,
                            row=int(raw.get("_row", 0)),
                        )
                    )
                else:
                    preview.connections.append(conn_row)
            except (PydanticValidationError, ValueError, TypeError) as exc:
                preview.issues.append(
                    ExcelIssue(
                        code="EXCEL_ROW_INVALID",
                        message=str(exc),
                        sheet=s.SHEET_CONNECTIONS,
                        row=int(raw.get("_row", 0)),
                    )
                )

    pf_map: dict[tuple[str, str], tuple[float, TimeUnit]] = {}
    if s.SHEET_PF_INTERVALS in names:
        for raw in _read_sheet(
            wb[s.SHEET_PF_INTERVALS], s.PF_INTERVAL_COLUMNS
        ):
            eq_tag = _cell_str(raw.get("equipment_tag")) or ""
            fm_name = _cell_str(raw.get("failure_mode_name")) or ""
            try:
                raw_value = raw.get("value")
                if raw_value is None:
                    raise ValueError("PF value required")
                value = float(raw_value)
                unit = TimeUnit(_cell_str(raw.get("unit")) or "DAYS")
                if value <= 0:
                    raise ValueError("PF value must be > 0")
                pf_map[(eq_tag, fm_name)] = (value, unit)
            except (TypeError, ValueError) as exc:
                preview.issues.append(
                    ExcelIssue(
                        code="EXCEL_ROW_INVALID",
                        message=str(exc),
                        sheet=s.SHEET_PF_INTERVALS,
                        row=int(raw.get("_row", 0)),
                    )
                )

    if s.SHEET_FAILURE_MODES in names:
        for raw in _read_sheet(
            wb[s.SHEET_FAILURE_MODES],
            s.FAILURE_MODE_COLUMNS,
        ):
            try:
                eq_tag = _cell_str(raw.get("equipment_tag")) or ""
                name = _cell_str(raw.get("name")) or ""
                pf = pf_map.get((eq_tag, name))
                fm_row = FailureModeImportRow(
                    equipment_tag=eq_tag,
                    name=name,
                    description=_cell_str(raw.get("description")),
                    is_detectable=_cell_bool(raw.get("is_detectable")),
                    component_name=_cell_str(raw.get("component_name")),
                    pf_value=pf[0] if pf else None,
                    pf_unit=pf[1] if pf else None,
                )
                if fm_row.equipment_tag not in tags:
                    preview.issues.append(
                        ExcelIssue(
                            code="EXCEL_UNKNOWN_TAG",
                            message=f"unknown tag {fm_row.equipment_tag}",
                            sheet=s.SHEET_FAILURE_MODES,
                            row=int(raw.get("_row", 0)),
                        )
                    )
                else:
                    preview.failure_modes.append(fm_row)
            except (PydanticValidationError, ValueError, TypeError) as exc:
                preview.issues.append(
                    ExcelIssue(
                        code="EXCEL_ROW_INVALID",
                        message=str(exc),
                        sheet=s.SHEET_FAILURE_MODES,
                        row=int(raw.get("_row", 0)),
                    )
                )

    if s.SHEET_FAILURE_DISTRIBUTIONS in names:
        for raw in _read_sheet(
            wb[s.SHEET_FAILURE_DISTRIBUTIONS],
            s.FAILURE_DISTRIBUTION_COLUMNS,
        ):
            try:
                dist_raw = raw.get("distribution_json")
                if isinstance(dist_raw, str):
                    dist_data = json.loads(dist_raw)
                elif isinstance(dist_raw, dict):
                    dist_data = dist_raw
                else:
                    raise ValueError("distribution_json required")
                parse_distribution(dist_data)
                dist_row = FailureDistributionImportRow(
                    equipment_tag=_cell_str(raw.get("equipment_tag")) or "",
                    failure_mode_name=(
                        _cell_str(raw.get("failure_mode_name")) or ""
                    ),
                    distribution=dist_data,
                    source_type=SourceType(
                        _cell_str(raw.get("source_type")) or "USER_DEFINED"
                    ),
                    confidence=Confidence(
                        _cell_str(raw.get("confidence")) or "MEDIUM"
                    ),
                    source_reference=_cell_str(raw.get("source_reference")),
                    generated_by=_cell_str(raw.get("generated_by")),
                )
                preview.failure_distributions.append(dist_row)
            except (
                PydanticValidationError,
                ValueError,
                TypeError,
                json.JSONDecodeError,
            ) as exc:
                preview.issues.append(
                    ExcelIssue(
                        code="EXCEL_ROW_INVALID",
                        message=str(exc),
                        sheet=s.SHEET_FAILURE_DISTRIBUTIONS,
                        row=int(raw.get("_row", 0)),
                    )
                )

    if s.SHEET_MAINTENANCE in names:
        for raw in _read_sheet(wb[s.SHEET_MAINTENANCE], s.MAINTENANCE_COLUMNS):
            try:
                duration_json = raw.get("duration_distribution_json")
                duration: dict[str, Any] | None = None
                if duration_json:
                    if isinstance(duration_json, str):
                        duration = json.loads(duration_json)
                    elif isinstance(duration_json, dict):
                        duration = duration_json
                    if duration is not None:
                        parse_distribution(duration)
                maint_row = MaintenanceImportRow(
                    equipment_tag=_cell_str(raw.get("equipment_tag")) or "",
                    name=_cell_str(raw.get("name")) or "",
                    task_type=MaintenanceTaskType(
                        _cell_str(raw.get("task_type")) or "CORRECTIVE"
                    ),
                    trigger=MaintenanceTrigger(
                        _cell_str(raw.get("trigger")) or "ON_FAILURE"
                    ),
                    failure_mode_name=_cell_str(raw.get("failure_mode_name")),
                    interval_value=(
                        float(raw["interval_value"])
                        if raw.get("interval_value") is not None
                        else None
                    ),
                    interval_unit=(
                        TimeUnit(_cell_str(raw.get("interval_unit")) or "DAYS")
                        if raw.get("interval_unit")
                        else None
                    ),
                    cost=(
                        float(raw["cost"])
                        if raw.get("cost") is not None
                        else None
                    ),
                    duration_distribution=duration,
                    duration_source_type=(
                        SourceType(
                            _cell_str(raw.get("duration_source_type"))
                            or "USER_DEFINED"
                        )
                        if duration
                        else None
                    ),
                    duration_confidence=(
                        Confidence(
                            _cell_str(raw.get("duration_confidence"))
                            or "MEDIUM"
                        )
                        if duration
                        else None
                    ),
                )
                if maint_row.equipment_tag not in tags:
                    preview.issues.append(
                        ExcelIssue(
                            code="EXCEL_UNKNOWN_TAG",
                            message=(f"unknown tag {maint_row.equipment_tag}"),
                            sheet=s.SHEET_MAINTENANCE,
                            row=int(raw.get("_row", 0)),
                        )
                    )
                else:
                    preview.maintenance.append(maint_row)
            except (
                PydanticValidationError,
                ValueError,
                TypeError,
                json.JSONDecodeError,
            ) as exc:
                preview.issues.append(
                    ExcelIssue(
                        code="EXCEL_ROW_INVALID",
                        message=str(exc),
                        sheet=s.SHEET_MAINTENANCE,
                        row=int(raw.get("_row", 0)),
                    )
                )

    if s.SHEET_MAINTENANCE_EFFECTS in names:
        for raw in _read_sheet(
            wb[s.SHEET_MAINTENANCE_EFFECTS],
            s.MAINTENANCE_EFFECT_COLUMNS,
        ):
            try:
                preview.maintenance_effects.append(
                    MaintenanceEffectImportRow(
                        equipment_tag=(
                            _cell_str(raw.get("equipment_tag")) or ""
                        ),
                        maintenance_name=(
                            _cell_str(raw.get("maintenance_name")) or ""
                        ),
                        effect_type=MaintenanceEffectType(
                            _cell_str(raw.get("effect_type"))
                            or "RESTORE_AS_NEW"
                        ),
                        failure_mode_name=_cell_str(
                            raw.get("failure_mode_name")
                        ),
                        parameter=(
                            float(raw["parameter"])
                            if raw.get("parameter") is not None
                            else None
                        ),
                    )
                )
            except (PydanticValidationError, ValueError, TypeError) as exc:
                preview.issues.append(
                    ExcelIssue(
                        code="EXCEL_ROW_INVALID",
                        message=str(exc),
                        sheet=s.SHEET_MAINTENANCE_EFFECTS,
                        row=int(raw.get("_row", 0)),
                    )
                )

    if s.SHEET_DIAGNOSTICS in names:
        for raw in _read_sheet(wb[s.SHEET_DIAGNOSTICS], s.DIAGNOSTIC_COLUMNS):
            try:
                diag_row = DiagnosticImportRow(
                    equipment_tag=_cell_str(raw.get("equipment_tag")) or "",
                    failure_mode_name=(
                        _cell_str(raw.get("failure_mode_name")) or ""
                    ),
                    name=_cell_str(raw.get("name")) or "",
                    method=_cell_str(raw.get("method")),
                    interval_value=float(raw.get("interval_value") or 0),
                    interval_unit=TimeUnit(
                        _cell_str(raw.get("interval_unit")) or "DAYS"
                    ),
                    detection_probability=float(
                        raw.get("detection_probability") or 0
                    ),
                    false_positive_probability=float(
                        raw.get("false_positive_probability") or 0
                    ),
                )
                if diag_row.equipment_tag not in tags:
                    preview.issues.append(
                        ExcelIssue(
                            code="EXCEL_UNKNOWN_TAG",
                            message=f"unknown tag {diag_row.equipment_tag}",
                            sheet=s.SHEET_DIAGNOSTICS,
                            row=int(raw.get("_row", 0)),
                        )
                    )
                else:
                    preview.diagnostics.append(diag_row)
            except (PydanticValidationError, ValueError, TypeError) as exc:
                preview.issues.append(
                    ExcelIssue(
                        code="EXCEL_ROW_INVALID",
                        message=str(exc),
                        sheet=s.SHEET_DIAGNOSTICS,
                        row=int(raw.get("_row", 0)),
                    )
                )

    if s.SHEET_RESOURCES in names:
        for raw in _read_sheet(wb[s.SHEET_RESOURCES], s.RESOURCE_COLUMNS):
            try:
                preview.resources.append(
                    ResourceImportRow(
                        name=_cell_str(raw.get("name")) or "",
                        resource_type=_cell_str(raw.get("resource_type")),
                        capacity=int(raw.get("capacity") or 1),
                        cost_per_hour=(
                            float(raw["cost_per_hour"])
                            if raw.get("cost_per_hour") is not None
                            else None
                        ),
                    )
                )
            except (PydanticValidationError, ValueError, TypeError) as exc:
                preview.issues.append(
                    ExcelIssue(
                        code="EXCEL_ROW_INVALID",
                        message=str(exc),
                        sheet=s.SHEET_RESOURCES,
                        row=int(raw.get("_row", 0)),
                    )
                )

    if s.SHEET_SPARE_PARTS in names:
        for raw in _read_sheet(wb[s.SHEET_SPARE_PARTS], s.SPARE_PART_COLUMNS):
            try:
                preview.spare_parts.append(
                    SparePartImportRow(
                        name=_cell_str(raw.get("name")) or "",
                        stock=int(raw.get("stock") or 0),
                        lead_time_value=(
                            float(raw["lead_time_value"])
                            if raw.get("lead_time_value") is not None
                            else None
                        ),
                        lead_time_unit=(
                            TimeUnit(
                                _cell_str(raw.get("lead_time_unit")) or "DAYS"
                            )
                            if raw.get("lead_time_unit")
                            else None
                        ),
                        unit_cost=(
                            float(raw["unit_cost"])
                            if raw.get("unit_cost") is not None
                            else None
                        ),
                    )
                )
            except (PydanticValidationError, ValueError, TypeError) as exc:
                preview.issues.append(
                    ExcelIssue(
                        code="EXCEL_ROW_INVALID",
                        message=str(exc),
                        sheet=s.SHEET_SPARE_PARTS,
                        row=int(raw.get("_row", 0)),
                    )
                )

    if s.SHEET_PRODUCTION in names:
        for raw in _read_sheet(wb[s.SHEET_PRODUCTION], s.PRODUCTION_COLUMNS):
            try:
                preview.production.append(
                    ProductionImportRow(
                        kind=_cell_str(raw.get("kind")) or "function",
                        product=_cell_str(raw.get("product")),
                        nominal_rate_value=(
                            float(raw["nominal_rate_value"])
                            if raw.get("nominal_rate_value") is not None
                            else None
                        ),
                        mass_unit=(
                            MassUnit(_cell_str(raw.get("mass_unit")) or "KG")
                            if raw.get("mass_unit")
                            else None
                        ),
                        time_unit=(
                            TimeUnit(
                                _cell_str(raw.get("time_unit")) or "HOURS"
                            )
                            if raw.get("time_unit")
                            else None
                        ),
                        equipment_tag=_cell_str(raw.get("equipment_tag")),
                        failure_mode_name=_cell_str(
                            raw.get("failure_mode_name")
                        ),
                        loss_fraction=(
                            float(raw["loss_fraction"])
                            if raw.get("loss_fraction") is not None
                            else None
                        ),
                    )
                )
            except (PydanticValidationError, ValueError, TypeError) as exc:
                preview.issues.append(
                    ExcelIssue(
                        code="EXCEL_ROW_INVALID",
                        message=str(exc),
                        sheet=s.SHEET_PRODUCTION,
                        row=int(raw.get("_row", 0)),
                    )
                )

    for eq in preview.equipment:
        if eq.parent_tag and eq.parent_tag not in tags:
            preview.issues.append(
                ExcelIssue(
                    code="EXCEL_UNKNOWN_TAG",
                    message=f"unknown parent_tag {eq.parent_tag}",
                    sheet=s.SHEET_EQUIPMENT,
                    entity="Equipment",
                )
            )

    wb.close()
    return preview

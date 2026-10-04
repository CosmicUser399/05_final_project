"""Workbook sheet names and column layouts for Excel exchange."""

from __future__ import annotations

from typing import Final

# Max upload size for Excel import (security limit).
EXCEL_MAX_BYTES: Final[int] = 20_000_000

SHEET_SYSTEMS: Final[str] = "Systems"
SHEET_EQUIPMENT: Final[str] = "Equipment"
SHEET_COMPONENTS: Final[str] = "Components"
SHEET_CONNECTIONS: Final[str] = "Connections"
SHEET_FAILURE_MODES: Final[str] = "FailureModes"
SHEET_FAILURE_DISTRIBUTIONS: Final[str] = "FailureDistributions"
SHEET_PF_INTERVALS: Final[str] = "PFIntervals"
SHEET_MAINTENANCE: Final[str] = "Maintenance"
SHEET_MAINTENANCE_EFFECTS: Final[str] = "MaintenanceEffects"
SHEET_DIAGNOSTICS: Final[str] = "Diagnostics"
SHEET_RESOURCES: Final[str] = "Resources"
SHEET_SPARE_PARTS: Final[str] = "SpareParts"
SHEET_PRODUCTION: Final[str] = "Production"

ALL_SHEETS: Final[tuple[str, ...]] = (
    SHEET_SYSTEMS,
    SHEET_EQUIPMENT,
    SHEET_COMPONENTS,
    SHEET_CONNECTIONS,
    SHEET_FAILURE_MODES,
    SHEET_FAILURE_DISTRIBUTIONS,
    SHEET_PF_INTERVALS,
    SHEET_MAINTENANCE,
    SHEET_MAINTENANCE_EFFECTS,
    SHEET_DIAGNOSTICS,
    SHEET_RESOURCES,
    SHEET_SPARE_PARTS,
    SHEET_PRODUCTION,
)

EQUIPMENT_COLUMNS: Final[tuple[str, ...]] = (
    "tag",
    "name",
    "description",
    "parent_tag",
    "category",
    "equipment_class",
    "equipment_type",
    "location",
    "quantity",
    "criticality",
    "operating_mode",
    "standby_mode",
    "is_repairable",
)

COMPONENT_COLUMNS: Final[tuple[str, ...]] = (
    "equipment_tag",
    "name",
    "description",
    "quantity",
)

CONNECTION_COLUMNS: Final[tuple[str, ...]] = (
    "from_tag",
    "to_tag",
    "connection_type",
    "description",
)

FAILURE_MODE_COLUMNS: Final[tuple[str, ...]] = (
    "equipment_tag",
    "name",
    "description",
    "is_detectable",
    "component_name",
)

PF_INTERVAL_COLUMNS: Final[tuple[str, ...]] = (
    "equipment_tag",
    "failure_mode_name",
    "value",
    "unit",
)

FAILURE_DISTRIBUTION_COLUMNS: Final[tuple[str, ...]] = (
    "equipment_tag",
    "failure_mode_name",
    "distribution_json",
    "source_type",
    "confidence",
    "source_reference",
    "generated_by",
)

MAINTENANCE_COLUMNS: Final[tuple[str, ...]] = (
    "equipment_tag",
    "name",
    "task_type",
    "trigger",
    "failure_mode_name",
    "interval_value",
    "interval_unit",
    "cost",
    "duration_distribution_json",
    "duration_source_type",
    "duration_confidence",
)

MAINTENANCE_EFFECT_COLUMNS: Final[tuple[str, ...]] = (
    "equipment_tag",
    "maintenance_name",
    "effect_type",
    "failure_mode_name",
    "parameter",
)

DIAGNOSTIC_COLUMNS: Final[tuple[str, ...]] = (
    "equipment_tag",
    "failure_mode_name",
    "name",
    "method",
    "interval_value",
    "interval_unit",
    "detection_probability",
    "false_positive_probability",
)

RESOURCE_COLUMNS: Final[tuple[str, ...]] = (
    "name",
    "resource_type",
    "capacity",
    "cost_per_hour",
)

SPARE_PART_COLUMNS: Final[tuple[str, ...]] = (
    "name",
    "stock",
    "lead_time_value",
    "lead_time_unit",
    "unit_cost",
)

PRODUCTION_COLUMNS: Final[tuple[str, ...]] = (
    "kind",
    "product",
    "nominal_rate_value",
    "mass_unit",
    "time_unit",
    "equipment_tag",
    "failure_mode_name",
    "loss_fraction",
)

SYSTEM_COLUMNS: Final[tuple[str, ...]] = (
    "name",
    "description",
    "dataset_label",
    "for_software_testing",
)

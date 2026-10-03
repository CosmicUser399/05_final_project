"""Whitelist and constants for Fabricate staging SQLite artifacts."""

from __future__ import annotations

STAGING_SCHEMA_VERSION = "1"

ALLOWED_CATEGORIES: frozenset[str] = frozenset(
    {
        "PROCESS",
        "ROTATING",
        "STATIC",
        "ELECTRICAL",
        "INSTRUMENT",
        "UTILITY",
        "OTHER",
    }
)

EQUIPMENT_COLUMNS: frozenset[str] = frozenset(
    {
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
    }
)

COMPONENT_COLUMNS: frozenset[str] = frozenset(
    {
        "equipment_tag",
        "name",
        "description",
        "quantity",
    }
)

CONNECTION_COLUMNS: frozenset[str] = frozenset(
    {
        "from_tag",
        "to_tag",
        "connection_type",
        "description",
    }
)

FAILURE_MODE_COLUMNS: frozenset[str] = frozenset(
    {
        "equipment_tag",
        "name",
        "description",
        "is_detectable",
    }
)

MAINTENANCE_COLUMNS: frozenset[str] = frozenset(
    {
        "equipment_tag",
        "name",
        "task_type",
    }
)

WHITELISTED_TABLES: dict[str, frozenset[str]] = {
    "equipment": EQUIPMENT_COLUMNS,
    "components": COMPONENT_COLUMNS,
    "connections": CONNECTION_COLUMNS,
    "failure_modes": FAILURE_MODE_COLUMNS,
    "maintenance_tasks": MAINTENANCE_COLUMNS,
}

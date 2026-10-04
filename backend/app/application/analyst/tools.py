"""Whitelist of typed read-only tools for AI Analyst."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationError as PydanticValidationError

from app.application.equipment_service import EquipmentService
from app.application.failure_modes import FailureModeService
from app.application.maintenance_service import MaintenanceService
from app.application.reference_service import ReferenceDataService
from app.application.scenario_service import ScenarioService
from app.application.simulation_service import SimulationService
from app.application.systems import SystemService
from app.application.versions import VersionService
from app.domain.errors import DomainError
from app.domain.errors import NotFoundError
from app.domain.errors import ValidationError

# Forbidden tool names (never registered).
FORBIDDEN_TOOLS: frozenset[str] = frozenset(
    {
        "sql.execute",
        "shell.execute",
        "filesystem.write",
        "filesystem.read",
        "db.execute",
    }
)

TOOL_WHITELIST: frozenset[str] = frozenset(
    {
        "system.get",
        "equipment.search",
        "failure_mode.search",
        "maintenance.search",
        "simulation.get_metrics",
        "simulation.get_events",
        "simulation.compare",
        "scenario.get",
        "reference.search",
    }
)


class ToolSpec(BaseModel):
    """JSON-schema-like description of one typed tool."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class PlannedToolCall(BaseModel):
    """Tool name + arguments chosen by the planner."""

    model_config = ConfigDict(frozen=True)

    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="system.get",
        description="Fetch a system and optional version summary.",
        parameters={
            "type": "object",
            "properties": {
                "system_id": {"type": "string", "format": "uuid"},
                "version_id": {"type": "string", "format": "uuid"},
            },
        },
    ),
    ToolSpec(
        name="equipment.search",
        description=("Search equipment in a version by tag/name substring."),
        parameters={
            "type": "object",
            "properties": {
                "version_id": {"type": "string", "format": "uuid"},
                "query": {"type": "string"},
                "equipment_id": {"type": "string", "format": "uuid"},
                "limit": {"type": "integer", "minimum": 1},
            },
            "required": ["version_id"],
        },
    ),
    ToolSpec(
        name="failure_mode.search",
        description="List/search failure modes for equipment/version.",
        parameters={
            "type": "object",
            "properties": {
                "version_id": {"type": "string", "format": "uuid"},
                "equipment_id": {"type": "string", "format": "uuid"},
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1},
            },
            "required": ["version_id"],
        },
    ),
    ToolSpec(
        name="maintenance.search",
        description="List/search maintenance tasks for equipment/version.",
        parameters={
            "type": "object",
            "properties": {
                "version_id": {"type": "string", "format": "uuid"},
                "equipment_id": {"type": "string", "format": "uuid"},
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1},
            },
            "required": ["version_id"],
        },
    ),
    ToolSpec(
        name="simulation.get_metrics",
        description=("Return stored Monte Carlo metrics for a completed run."),
        parameters={
            "type": "object",
            "properties": {
                "simulation_run_id": {
                    "type": "string",
                    "format": "uuid",
                },
            },
            "required": ["simulation_run_id"],
        },
    ),
    ToolSpec(
        name="simulation.get_events",
        description="Page of stored simulation events for a run.",
        parameters={
            "type": "object",
            "properties": {
                "simulation_run_id": {
                    "type": "string",
                    "format": "uuid",
                },
                "event_type": {"type": "string"},
                "equipment_id": {"type": "string", "format": "uuid"},
                "offset": {"type": "integer", "minimum": 0},
                "limit": {"type": "integer", "minimum": 1},
            },
            "required": ["simulation_run_id"],
        },
    ),
    ToolSpec(
        name="simulation.compare",
        description=(
            "Compare baseline vs scenario completed simulation metrics."
        ),
        parameters={
            "type": "object",
            "properties": {
                "scenario_id": {"type": "string", "format": "uuid"},
                "baseline_run_id": {
                    "type": "string",
                    "format": "uuid",
                },
                "scenario_run_id": {
                    "type": "string",
                    "format": "uuid",
                },
            },
            "required": ["scenario_id"],
        },
    ),
    ToolSpec(
        name="scenario.get",
        description="Fetch a scenario and its current changes.",
        parameters={
            "type": "object",
            "properties": {
                "scenario_id": {"type": "string", "format": "uuid"},
            },
            "required": ["scenario_id"],
        },
    ),
    ToolSpec(
        name="reference.search",
        description=("Search OREDA/ISO reference parameters and taxonomy."),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "equipment_class": {"type": "string"},
                "equipment_class_code": {"type": "string"},
                "parameter_kind": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1},
            },
        },
    ),
)


def assert_tool_allowed(name: str) -> None:
    """Raise if the tool is forbidden or not whitelisted."""
    if name in FORBIDDEN_TOOLS:
        raise ValidationError(
            f"tool '{name}' is forbidden",
            code="TOOL_FORBIDDEN",
            entity="AnalystTool",
            entity_id=name,
        )
    if name not in TOOL_WHITELIST:
        raise ValidationError(
            f"tool '{name}' is not allowed",
            code="TOOL_NOT_ALLOWED",
            entity="AnalystTool",
            entity_id=name,
        )


class AnalystToolExecutor:
    """Dispatch whitelisted tools to application read services."""

    def __init__(
        self,
        *,
        systems: SystemService,
        versions: VersionService,
        equipment: EquipmentService,
        failure_modes: FailureModeService,
        maintenance: MaintenanceService,
        simulations: SimulationService,
        scenarios: ScenarioService,
        reference: ReferenceDataService | None = None,
    ) -> None:
        """Bind read services used by tools."""
        self._systems = systems
        self._versions = versions
        self._equipment = equipment
        self._failure_modes = failure_modes
        self._maintenance = maintenance
        self._simulations = simulations
        self._scenarios = scenarios
        self._reference = reference
        self._handlers: dict[
            str,
            Callable[[dict[str, Any]], dict[str, Any]],
        ] = {
            "system.get": self._system_get,
            "equipment.search": self._equipment_search,
            "failure_mode.search": self._failure_mode_search,
            "maintenance.search": self._maintenance_search,
            "simulation.get_metrics": self._simulation_get_metrics,
            "simulation.get_events": self._simulation_get_events,
            "simulation.compare": self._simulation_compare,
            "scenario.get": self._scenario_get,
            "reference.search": self._reference_search,
        }

    def execute(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run one tool; return a JSON-serializable payload."""
        assert_tool_allowed(name)
        args = dict(arguments or {})
        handler = self._handlers[name]
        try:
            return handler(args)
        except (DomainError, NotFoundError, ValidationError):
            raise
        except (TypeError, ValueError, PydanticValidationError) as exc:
            raise ValidationError(
                f"invalid tool arguments for {name}: {exc}",
                code="TOOL_ARGUMENT_ERROR",
                entity="AnalystTool",
                entity_id=name,
            ) from exc

    def _system_get(self, args: dict[str, Any]) -> dict[str, Any]:
        system_id = _optional_uuid(args.get("system_id"))
        version_id = _optional_uuid(args.get("version_id"))
        if system_id is None and version_id is None:
            raise ValidationError(
                "system_id or version_id is required",
                code="TOOL_ARGUMENT_ERROR",
                entity="AnalystTool",
                entity_id="system.get",
            )
        payload: dict[str, Any] = {}
        if version_id is not None:
            version = self._versions.get(version_id)
            payload["version"] = version.model_dump(mode="json")
            system_id = system_id or version.system_id
        if system_id is not None:
            system = self._systems.get(system_id)
            payload["system"] = system.model_dump(mode="json")
        return payload

    def _equipment_search(self, args: dict[str, Any]) -> dict[str, Any]:
        version_id = _require_uuid(args, "version_id")
        query = str(args.get("query") or "").strip().lower()
        equipment_id = _optional_uuid(args.get("equipment_id"))
        limit = _limit(args.get("limit"), default=50)
        rows = self._equipment.list_for_version(version_id)
        items = []
        for row in rows:
            if equipment_id is not None and row.id != equipment_id:
                continue
            if (
                query
                and query not in row.tag.lower()
                and query not in (row.name or "").lower()
            ):
                continue
            items.append(row.model_dump(mode="json"))
            if len(items) >= limit:
                break
        return {
            "version_id": str(version_id),
            "query": query or None,
            "count": len(items),
            "items": items,
        }

    def _failure_mode_search(self, args: dict[str, Any]) -> dict[str, Any]:
        version_id = _require_uuid(args, "version_id")
        equipment_id = _optional_uuid(args.get("equipment_id"))
        query = str(args.get("query") or "").strip().lower()
        limit = _limit(args.get("limit"), default=50)
        modes = self._failure_modes.list_for_version(
            version_id,
            equipment_id=equipment_id,
        )
        items = []
        for mode in modes:
            if query and query not in mode.name.lower():
                continue
            items.append(mode.model_dump(mode="json"))
            if len(items) >= limit:
                break
        return {
            "version_id": str(version_id),
            "equipment_id": (str(equipment_id) if equipment_id else None),
            "count": len(items),
            "items": items,
        }

    def _maintenance_search(self, args: dict[str, Any]) -> dict[str, Any]:
        version_id = _require_uuid(args, "version_id")
        equipment_id = _optional_uuid(args.get("equipment_id"))
        query = str(args.get("query") or "").strip().lower()
        limit = _limit(args.get("limit"), default=50)
        tasks = self._maintenance.list_for_version(
            version_id,
            equipment_id=equipment_id,
        )
        items = []
        for task in tasks:
            if query and query not in task.name.lower():
                continue
            items.append(task.model_dump(mode="json"))
            if len(items) >= limit:
                break
        return {
            "version_id": str(version_id),
            "equipment_id": (str(equipment_id) if equipment_id else None),
            "count": len(items),
            "items": items,
        }

    def _simulation_get_metrics(
        self,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = _require_uuid(args, "simulation_run_id")
        return self._simulations.get_results(run_id)

    def _simulation_get_events(
        self,
        args: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = _require_uuid(args, "simulation_run_id")
        equipment_id = _optional_uuid(args.get("equipment_id"))
        event_type = args.get("event_type")
        offset = int(args.get("offset") or 0)
        limit = _limit(args.get("limit"), default=50, maximum=200)
        return self._simulations.get_events(
            run_id,
            offset=offset,
            limit=limit,
            event_type=str(event_type) if event_type else None,
            equipment_id=equipment_id,
        )

    def _simulation_compare(self, args: dict[str, Any]) -> dict[str, Any]:
        scenario_id = _require_uuid(args, "scenario_id")
        baseline = _optional_uuid(args.get("baseline_run_id"))
        scenario_run = _optional_uuid(args.get("scenario_run_id"))
        return self._scenarios.compare(
            scenario_id,
            baseline_run_id=baseline,
            scenario_run_id=scenario_run,
        )

    def _scenario_get(self, args: dict[str, Any]) -> dict[str, Any]:
        scenario_id = _require_uuid(args, "scenario_id")
        return self._scenarios.get(scenario_id)

    def _reference_search(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query") or "").strip()
        limit = _limit(args.get("limit"), default=20)
        if self._reference is None:
            return {
                "query": query or None,
                "available": False,
                "message": "Reference data service is not configured.",
                "count": 0,
                "items": [],
                "limit": limit,
            }
        equipment_class = (
            str(args.get("equipment_class") or "").strip() or None
        )
        equipment_class_code = (
            str(args.get("equipment_class_code") or "").strip() or None
        )
        parameter_kind = (
            str(args.get("parameter_kind") or "").strip() or None
        )
        result = self._reference.search_parameters(
            query=query or None,
            equipment_class=equipment_class,
            equipment_class_code=equipment_class_code,
            parameter_kind=parameter_kind,
            limit=limit,
        )
        # Planner may pass a full sentence; retry on significant tokens.
        if result["count"] == 0 and query:
            for token in _reference_tokens(query):
                result = self._reference.search_parameters(
                    query=token,
                    equipment_class=equipment_class,
                    equipment_class_code=equipment_class_code,
                    parameter_kind=parameter_kind,
                    limit=limit,
                )
                if result["count"] > 0:
                    result["query"] = query
                    result["matched_token"] = token
                    break
        if not result["available"]:
            result["message"] = (
                "Reference data is empty; call POST /reference/ingest "
                "to load the demo extract."
            )
        taxonomy_query = query
        if result.get("matched_token"):
            taxonomy_query = str(result["matched_token"])
        taxonomy = self._reference.search_taxonomy(
            query=taxonomy_query or None,
            limit=min(limit, 20),
        )
        result["taxonomy_nodes"] = taxonomy.get("items", [])
        return result


_REFERENCE_STOPWORDS = frozenset(
    {
        "найди",
        "найти",
        "параметры",
        "параметр",
        "для",
        "the",
        "for",
        "and",
        "oreda",
        "iso",
        "14224",
        "reference",
        "данные",
        "справочник",
    }
)


def _reference_tokens(query: str) -> list[str]:
    """Return searchable tokens from a free-text analyst query."""
    parts = [part.strip(".,;:?!") for part in query.lower().split()]
    return [
        part
        for part in parts
        if len(part) >= 3 and part not in _REFERENCE_STOPWORDS
    ]


def _require_uuid(args: dict[str, Any], key: str) -> UUID:
    raw = args.get(key)
    if raw is None or str(raw).strip() == "":
        raise ValidationError(
            f"{key} is required",
            code="TOOL_ARGUMENT_ERROR",
            entity="AnalystTool",
            entity_id=key,
        )
    return UUID(str(raw))


def _optional_uuid(raw: Any) -> UUID | None:
    if raw is None or str(raw).strip() == "":
        return None
    return UUID(str(raw))


def _limit(
    raw: Any,
    *,
    default: int,
    maximum: int = 100,
) -> int:
    try:
        value = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        value = default
    return min(max(value, 1), maximum)

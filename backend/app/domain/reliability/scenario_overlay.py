"""Apply scenario changes onto a compiled model."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from typing import cast
from uuid import UUID

from app.domain.errors import ValidationError
from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiled import ScenarioChange
from app.domain.reliability.compiled import ScenarioChangeType
from app.domain.reliability.compiled import ScenarioOverlay
from app.domain.reliability.distributions import DistributionSpec
from app.domain.reliability.distributions import parse_distribution
from app.domain.units import TimeUnit
from app.domain.units import TimeValue


def apply_scenario_overlay(
    model: CompiledModel,
    overlay: ScenarioOverlay,
) -> CompiledModel:
    """Return a new compiled model with overlay changes applied."""
    data = model.model_dump(mode="python")
    disabled: set[UUID] = set()
    for change in overlay.changes:
        _apply_one(data, change, disabled)
    if disabled:
        data["maintenance_tasks"] = [
            t
            for t in data["maintenance_tasks"]
            if t["lineage_id"] not in disabled and t["id"] not in disabled
        ]
        data["diagnostic_tasks"] = [
            t
            for t in data["diagnostic_tasks"]
            if t["lineage_id"] not in disabled and t["id"] not in disabled
        ]
    return CompiledModel.model_validate(data)


def _apply_one(
    data: dict[str, Any],
    change: ScenarioChange,
    disabled: set[UUID],
) -> None:
    target = change.target_lineage_id
    params = change.parameters
    kind = change.change_type

    if kind is ScenarioChangeType.DISABLE_TASK:
        disabled.add(target)
        return
    if kind is ScenarioChangeType.ENABLE_TASK:
        disabled.discard(target)
        return

    if kind is ScenarioChangeType.CHANGE_DIAGNOSTIC_INTERVAL:
        diag = _find_diag(data, target)
        diag["interval_minutes"] = _minutes_from_params(params)
        return
    if kind is ScenarioChangeType.CHANGE_DETECTION_PROBABILITY:
        diag = _find_diag(data, target)
        p = float(params["detection_probability"])
        if not 0.0 <= p <= 1.0:
            raise ValidationError(
                "detection_probability must be in [0, 1]",
                code="INVALID_PROBABILITY",
            )
        diag["detection_probability"] = p
        return
    if kind is ScenarioChangeType.CHANGE_PM_INTERVAL:
        task = _find_task(data, target)
        task["interval_minutes"] = _minutes_from_params(params)
        return
    if kind is ScenarioChangeType.CHANGE_MAINTENANCE_DISTRIBUTION:
        task = _find_task(data, target)
        task["duration"] = _distribution_from_params(params)
        return
    if kind is ScenarioChangeType.CHANGE_RESOURCE:
        resource = _find_resource(data, target)
        if "capacity" in params:
            resource["capacity"] = int(params["capacity"])
        return
    if kind is ScenarioChangeType.CHANGE_SPARE_STOCK:
        spare = _find_spare(data, target)
        spare["stock"] = int(params["stock"])
        return
    if kind is ScenarioChangeType.CHANGE_FAILURE_PARAMETER:
        mode = _find_mode(data, target)
        dist = deepcopy(mode["distribution"])
        if hasattr(dist, "model_dump"):
            dist = dist.model_dump(mode="python")
        for key, value in params.items():
            if key in dist:
                dist[key] = value
        mode["distribution"] = parse_distribution(dist)
        return
    raise ValidationError(
        f"unsupported scenario change {kind}",
        code="UNSUPPORTED_SCENARIO_CHANGE",
    )


def _minutes_from_params(params: dict[str, Any]) -> float:
    if "minutes" in params:
        value = float(params["minutes"])
        if value <= 0:
            raise ValidationError(
                "interval must be > 0",
                code="INVALID_INTERVAL",
            )
        return value
    value = float(params["value"])
    unit = TimeUnit(params["unit"])
    return TimeValue(value=value, unit=unit).to_minutes()


def _distribution_from_params(params: dict[str, Any]) -> DistributionSpec:
    return cast(
        DistributionSpec,
        parse_distribution(params["distribution"]),
    )


def _find_diag(data: dict[str, Any], lineage_id: UUID) -> dict[str, Any]:
    for item in data["diagnostic_tasks"]:
        if item["lineage_id"] == lineage_id or item["id"] == lineage_id:
            return cast(dict[str, Any], item)
    raise ValidationError(
        "diagnostic task not found for scenario change",
        code="SCENARIO_TARGET_NOT_FOUND",
        entity="DiagnosticTask",
        entity_id=str(lineage_id),
    )


def _find_task(data: dict[str, Any], lineage_id: UUID) -> dict[str, Any]:
    for item in data["maintenance_tasks"]:
        if item["lineage_id"] == lineage_id or item["id"] == lineage_id:
            return cast(dict[str, Any], item)
    raise ValidationError(
        "maintenance task not found for scenario change",
        code="SCENARIO_TARGET_NOT_FOUND",
        entity="MaintenanceTask",
        entity_id=str(lineage_id),
    )


def _find_resource(data: dict[str, Any], lineage_id: UUID) -> dict[str, Any]:
    for item in data["resources"]:
        if item["lineage_id"] == lineage_id or item["id"] == lineage_id:
            return cast(dict[str, Any], item)
    raise ValidationError(
        "resource not found for scenario change",
        code="SCENARIO_TARGET_NOT_FOUND",
        entity="Resource",
        entity_id=str(lineage_id),
    )


def _find_spare(data: dict[str, Any], lineage_id: UUID) -> dict[str, Any]:
    for item in data["spare_parts"]:
        if item["lineage_id"] == lineage_id or item["id"] == lineage_id:
            return cast(dict[str, Any], item)
    raise ValidationError(
        "spare part not found for scenario change",
        code="SCENARIO_TARGET_NOT_FOUND",
        entity="SparePart",
        entity_id=str(lineage_id),
    )


def _find_mode(data: dict[str, Any], lineage_id: UUID) -> dict[str, Any]:
    for item in data["failure_modes"]:
        if item["lineage_id"] == lineage_id or item["id"] == lineage_id:
            return cast(dict[str, Any], item)
    raise ValidationError(
        "failure mode not found for scenario change",
        code="SCENARIO_TARGET_NOT_FOUND",
        entity="FailureMode",
        entity_id=str(lineage_id),
    )

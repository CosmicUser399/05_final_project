"""Model validation levels 4 (MODEL) and 5 (SIMULATION)."""

from __future__ import annotations

from collections import defaultdict
from collections import deque
from uuid import UUID

from app.domain.equipment.entities import Criticality
from app.domain.maintenance.entities import MaintenanceTaskType
from app.domain.system.content import SystemVersionContent
from app.domain.validation import Severity
from app.domain.validation import ValidationIssue
from app.domain.validation import ValidationLevel
from app.domain.validation import ValidationReport
from app.domain.validation import validate_content


def validate_model(content: SystemVersionContent) -> ValidationReport:
    """Level 4: every enabled entity is complete enough to compile."""
    issues: list[ValidationIssue] = []
    modes = {m.id: m for m in content.failure_modes}
    dist_by_mode = {
        d.failure_mode_id: d for d in content.failure_distributions
    }
    dur_by_task = {
        d.maintenance_task_id: d for d in content.maintenance_distributions
    }
    equipment = {e.id: e for e in content.equipment}

    if not content.equipment:
        issues.append(
            ValidationIssue(
                code="MODEL_EMPTY",
                message="model has no equipment",
                level=ValidationLevel.MODEL,
            )
        )

    for mode in content.failure_modes:
        if mode.equipment_id not in equipment:
            continue
        if mode.id not in dist_by_mode:
            issues.append(
                ValidationIssue(
                    code="MISSING_FAILURE_DISTRIBUTION",
                    message="failure mode has no distribution",
                    level=ValidationLevel.MODEL,
                    entity="FailureMode",
                    entity_id=str(mode.id),
                )
            )
        if mode.is_detectable and mode.pf_interval is None:
            issues.append(
                ValidationIssue(
                    code="INVALID_PF_INTERVAL",
                    message="detectable mode needs a PF interval",
                    level=ValidationLevel.MODEL,
                    entity="FailureMode",
                    entity_id=str(mode.id),
                )
            )

    for task in content.maintenance_tasks:
        if task.id not in dur_by_task:
            issues.append(
                ValidationIssue(
                    code="MISSING_MAINTENANCE_DURATION",
                    message="maintenance task has no duration",
                    level=ValidationLevel.MODEL,
                    entity="MaintenanceTask",
                    entity_id=str(task.id),
                )
            )
        if (
            task.task_type is MaintenanceTaskType.CORRECTIVE
            and task.failure_mode_id is not None
            and task.failure_mode_id not in modes
        ):
            issues.append(
                ValidationIssue(
                    code="CM_UNKNOWN_FAILURE_MODE",
                    message="corrective task points to unknown mode",
                    level=ValidationLevel.MODEL,
                    entity="MaintenanceTask",
                    entity_id=str(task.id),
                )
            )

    for eq in content.equipment:
        if eq.criticality is Criticality.CRITICAL:
            has_impact = any(
                i.equipment_id == eq.id for i in content.production_impacts
            )
            if not has_impact:
                issues.append(
                    ValidationIssue(
                        code="CRITICAL_WITHOUT_PRODUCTION_IMPACT",
                        message=("critical equipment needs production impact"),
                        level=ValidationLevel.MODEL,
                        entity="Equipment",
                        entity_id=str(eq.id),
                    )
                )

    for link in content.connections:
        if link.source_id not in equipment or link.target_id not in equipment:
            issues.append(
                ValidationIssue(
                    code="BROKEN_CONNECTION",
                    message="connection endpoints are incomplete",
                    level=ValidationLevel.MODEL,
                    entity="EquipmentConnection",
                    entity_id=str(link.id),
                )
            )

    for diag in content.diagnostic_tasks:
        target = modes.get(diag.failure_mode_id)
        if target is None:
            continue
        if not target.is_detectable or target.pf_interval is None:
            issues.append(
                ValidationIssue(
                    code="DIAGNOSTIC_WITHOUT_PF",
                    message="diagnostic needs a detectable mode with PF",
                    level=ValidationLevel.MODEL,
                    entity="DiagnosticTask",
                    entity_id=str(diag.id),
                )
            )

    issues.extend(_unreachable_equipment_issues(content))
    return ValidationReport(tuple(issues))


def validate_simulation_readiness(
    content: SystemVersionContent,
) -> ValidationReport:
    """Level 5: model can be compiled and simulated."""
    issues: list[ValidationIssue] = []
    if not content.failure_modes:
        issues.append(
            ValidationIssue(
                code="NO_FAILURE_MODES",
                message="simulation needs at least one failure mode",
                level=ValidationLevel.SIMULATION,
                severity=Severity.ERROR,
            )
        )
    modes_with_dist = {
        d.failure_mode_id for d in content.failure_distributions
    }
    for mode in content.failure_modes:
        if mode.id not in modes_with_dist:
            issues.append(
                ValidationIssue(
                    code="UNSUPPORTED_OR_MISSING_DISTRIBUTION",
                    message=("every failure mode needs a distribution"),
                    level=ValidationLevel.SIMULATION,
                    entity="FailureMode",
                    entity_id=str(mode.id),
                )
            )
    cm_by_equipment = {
        t.equipment_id
        for t in content.maintenance_tasks
        if t.task_type is MaintenanceTaskType.CORRECTIVE
    }
    for eq in content.equipment:
        if eq.is_repairable and eq.id not in cm_by_equipment:
            issues.append(
                ValidationIssue(
                    code="REPAIRABLE_WITHOUT_CM",
                    message=("repairable equipment needs a corrective task"),
                    level=ValidationLevel.SIMULATION,
                    severity=Severity.WARNING,
                    entity="Equipment",
                    entity_id=str(eq.id),
                )
            )
    return ValidationReport(tuple(issues))


def validate_for_compile(
    content: SystemVersionContent,
) -> ValidationReport:
    """Run levels 2-5 required before compiling."""
    report = validate_content(content)
    report = report.merge(validate_model(content))
    report = report.merge(validate_simulation_readiness(content))
    return report


def _unreachable_equipment_issues(
    content: SystemVersionContent,
) -> list[ValidationIssue]:
    """Flag equipment disconnected from the main topology."""
    equipment_ids = {e.id for e in content.equipment}
    if len(equipment_ids) < 2:
        return []

    adjacency: dict[UUID, set[UUID]] = defaultdict(set)
    edge_count = 0
    for link in content.connections:
        if (
            link.source_id in equipment_ids
            and link.target_id in equipment_ids
            and link.source_id != link.target_id
        ):
            adjacency[link.source_id].add(link.target_id)
            adjacency[link.target_id].add(link.source_id)
            edge_count += 1
    for item in content.equipment:
        if (
            item.parent_id is not None
            and item.parent_id in equipment_ids
            and item.parent_id != item.id
        ):
            adjacency[item.id].add(item.parent_id)
            adjacency[item.parent_id].add(item.id)
            edge_count += 1

    if edge_count == 0:
        return []

    components = _connected_components(equipment_ids, adjacency)
    if len(components) <= 1:
        return []

    main = max(components, key=lambda part: (len(part), min(map(str, part))))
    issues: list[ValidationIssue] = []
    for component in components:
        if component is main:
            continue
        for eq_id in sorted(component, key=str):
            issues.append(
                ValidationIssue(
                    code="UNREACHABLE_EQUIPMENT",
                    message=(
                        "equipment is disconnected from the main topology"
                    ),
                    level=ValidationLevel.MODEL,
                    entity="Equipment",
                    entity_id=str(eq_id),
                )
            )
    return issues


def _connected_components(
    nodes: set[UUID],
    adjacency: dict[UUID, set[UUID]],
) -> list[set[UUID]]:
    """Return connected components of an undirected graph."""
    remaining = set(nodes)
    components: list[set[UUID]] = []
    while remaining:
        start = min(remaining, key=str)
        queue: deque[UUID] = deque([start])
        seen: set[UUID] = {start}
        while queue:
            node = queue.popleft()
            for neighbour in adjacency.get(node, ()):
                if neighbour in remaining and neighbour not in seen:
                    seen.add(neighbour)
                    queue.append(neighbour)
        components.append(seen)
        remaining -= seen
    return components

"""Domain validation, levels 1-3.

1. ``SCHEMA`` - field types and ranges (pydantic, see
   ``schema_issues``).
2. ``DOMAIN`` - references, uniqueness, cycles, structure rules.
3. ``ENGINEERING`` - engineering plausibility (criticality, PF vs life,
   diagnostic interval vs PF, resource capacity).

Levels 4-6 (model, Petri, simulation readiness) are added later.
"""

from collections import Counter
from collections.abc import Hashable
from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from enum import StrEnum
from uuid import UUID

from pydantic import ValidationError as PydanticValidationError

from app.domain.equipment.entities import Criticality
from app.domain.errors import ValidationError
from app.domain.provenance import Provenance
from app.domain.reliability.entities import StructureType
from app.domain.system.content import SystemVersionContent


class ValidationLevel(StrEnum):
    """Validation level, from cheapest to most specific."""

    SCHEMA = "SCHEMA"
    DOMAIN = "DOMAIN"
    ENGINEERING = "ENGINEERING"
    MODEL = "MODEL"
    PETRI = "PETRI"
    SIMULATION = "SIMULATION"


class Severity(StrEnum):
    """Issue severity; only errors make a report invalid."""

    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True)
class ValidationIssue:
    """One finding of a validation run."""

    code: str
    message: str
    level: ValidationLevel
    severity: Severity = Severity.ERROR
    entity: str | None = None
    entity_id: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    """Result of a validation run."""

    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)

    @property
    def errors(self) -> tuple[ValidationIssue, ...]:
        """Return issues with ``ERROR`` severity."""
        return tuple(i for i in self.issues if i.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        """Return issues with ``WARNING`` severity."""
        return tuple(i for i in self.issues if i.severity is Severity.WARNING)

    @property
    def is_valid(self) -> bool:
        """Return True if there are no errors."""
        return not self.errors

    def codes(self) -> frozenset[str]:
        """Return the set of issue codes."""
        return frozenset(i.code for i in self.issues)

    def merge(self, other: "ValidationReport") -> "ValidationReport":
        """Return a report with the issues of both reports."""
        return ValidationReport(self.issues + other.issues)

    def raise_if_invalid(self) -> None:
        """Raise ``ValidationError`` carrying all errors, if any."""
        errors = self.errors
        if not errors:
            return
        first = errors[0]
        raise ValidationError(
            f"{len(errors)} validation error(s); first: {first.message}",
            code=first.code,
            entity=first.entity,
            entity_id=first.entity_id,
            issues=errors,
        )


def schema_issues(
    exc: PydanticValidationError, entity: str | None = None
) -> list[ValidationIssue]:
    """Convert a pydantic error to level-1 issues."""
    issues: list[ValidationIssue] = []
    for item in exc.errors():
        location = ".".join(str(part) for part in item["loc"])
        issues.append(
            ValidationIssue(
                code="SCHEMA_ERROR",
                message=f"{location}: {item['msg']}",
                level=ValidationLevel.SCHEMA,
                entity=entity,
            )
        )
    return issues


class _Collector:
    """Accumulates issues of one level."""

    def __init__(self, level: ValidationLevel) -> None:
        self.level = level
        self.issues: list[ValidationIssue] = []

    def error(
        self, code: str, message: str, entity: str, entity_id: UUID
    ) -> None:
        self._add(Severity.ERROR, code, message, entity, entity_id)

    def warning(
        self, code: str, message: str, entity: str, entity_id: UUID
    ) -> None:
        self._add(Severity.WARNING, code, message, entity, entity_id)

    def _add(
        self,
        severity: Severity,
        code: str,
        message: str,
        entity: str,
        entity_id: UUID,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                code=code,
                message=message,
                level=self.level,
                severity=severity,
                entity=entity,
                entity_id=str(entity_id),
            )
        )


def _find_cycle_members(
    parent_of: dict[UUID, UUID | None],
) -> set[UUID]:
    """Return all nodes that lie on a cycle of a parent mapping."""
    on_cycle: set[UUID] = set()
    done: set[UUID] = set()
    for start in parent_of:
        path: list[UUID] = []
        seen: set[UUID] = set()
        node: UUID | None = start
        while node is not None and node in parent_of:
            if node in done:
                break
            if node in seen:
                on_cycle.update(path[path.index(node) :])
                break
            seen.add(node)
            path.append(node)
            node = parent_of[node]
        done.update(path)
    return on_cycle


def _duplicates(keys: Iterable[Hashable]) -> set[Hashable]:
    return {k for k, n in Counter(keys).items() if n > 1}


def validate_domain(content: SystemVersionContent) -> ValidationReport:
    """Level 2: references, uniqueness, cycles, structure rules."""
    out = _Collector(ValidationLevel.DOMAIN)
    c = content
    equipment = {e.id: e for e in c.equipment}
    modes = {m.id: m for m in c.failure_modes}
    tasks = {t.id: t for t in c.maintenance_tasks}
    resources = {r.id: r for r in c.resources}
    spares = {s.id: s for s in c.spare_parts}
    structures = {s.id: s for s in c.structures}
    components = {x.id: x for x in c.components}

    # Equipment: unique tags, hierarchy.
    dup_tags = _duplicates(e.tag.casefold() for e in c.equipment)
    for item in c.equipment:
        if item.tag.casefold() in dup_tags:
            out.error(
                "DUPLICATE_TAG",
                f"tag {item.tag!r} is not unique",
                "Equipment",
                item.id,
            )
        if item.parent_id is not None and item.parent_id not in equipment:
            out.error(
                "UNKNOWN_PARENT",
                "parent equipment does not exist",
                "Equipment",
                item.id,
            )
    cyclic = _find_cycle_members({e.id: e.parent_id for e in c.equipment})
    for eq_id in sorted(cyclic, key=str):
        out.error(
            "EQUIPMENT_HIERARCHY_CYCLE",
            "equipment hierarchy contains a cycle",
            "Equipment",
            eq_id,
        )

    for part in c.components:
        if part.equipment_id not in equipment:
            out.error(
                "COMPONENT_UNKNOWN_EQUIPMENT",
                "component refers to unknown equipment",
                "EquipmentComponent",
                part.id,
            )

    seen_links: set[tuple[UUID, UUID, str]] = set()
    for link in c.connections:
        if link.source_id not in equipment or (
            link.target_id not in equipment
        ):
            out.error(
                "CONNECTION_UNKNOWN_ENDPOINT",
                "connection refers to unknown equipment",
                "EquipmentConnection",
                link.id,
            )
        key = (link.source_id, link.target_id, link.connection_type)
        if key in seen_links:
            out.error(
                "DUPLICATE_CONNECTION",
                "duplicate connection of the same type",
                "EquipmentConnection",
                link.id,
            )
        seen_links.add(key)

    # Failure modes and distributions.
    for mode in c.failure_modes:
        if mode.equipment_id not in equipment:
            out.error(
                "FAILURE_MODE_UNKNOWN_EQUIPMENT",
                "failure mode refers to unknown equipment",
                "FailureMode",
                mode.id,
            )
        if mode.component_id is not None:
            owner = components.get(mode.component_id)
            if owner is None or owner.equipment_id != mode.equipment_id:
                out.error(
                    "FAILURE_MODE_UNKNOWN_COMPONENT",
                    "component does not belong to the equipment",
                    "FailureMode",
                    mode.id,
                )
        if mode.is_detectable and mode.pf_interval is None:
            out.error(
                "INVALID_PF_INTERVAL",
                "detectable failure mode requires a PF interval",
                "FailureMode",
                mode.id,
            )
        if not mode.is_detectable and mode.pf_interval is not None:
            out.warning(
                "PF_WITHOUT_DETECTABLE",
                "PF interval is set but the mode is not detectable",
                "FailureMode",
                mode.id,
            )

    dup_dist = _duplicates(d.failure_mode_id for d in c.failure_distributions)
    for fd in c.failure_distributions:
        if fd.failure_mode_id not in modes:
            out.error(
                "DISTRIBUTION_UNKNOWN_FAILURE_MODE",
                "distribution refers to unknown failure mode",
                "FailureDistribution",
                fd.id,
            )
        elif fd.failure_mode_id in dup_dist:
            out.error(
                "DUPLICATE_FAILURE_DISTRIBUTION",
                "failure mode has several distributions",
                "FailureDistribution",
                fd.id,
            )

    _validate_maintenance(c, out, equipment, modes, tasks)
    _validate_requirements(c, out, tasks, resources, spares)

    # Diagnostics.
    for diag in c.diagnostic_tasks:
        target = modes.get(diag.failure_mode_id)
        if diag.equipment_id not in equipment:
            out.error(
                "DIAGNOSTIC_UNKNOWN_EQUIPMENT",
                "diagnostic refers to unknown equipment",
                "DiagnosticTask",
                diag.id,
            )
        if target is None:
            out.error(
                "DIAGNOSTIC_UNKNOWN_FAILURE_MODE",
                "diagnostic refers to unknown failure target",
                "DiagnosticTask",
                diag.id,
            )
            continue
        if target.equipment_id != diag.equipment_id:
            out.error(
                "DIAGNOSTIC_EQUIPMENT_MISMATCH",
                "failure target belongs to other equipment",
                "DiagnosticTask",
                diag.id,
            )
        if not target.is_detectable:
            out.error(
                "DIAGNOSTIC_ON_UNDETECTABLE_MODE",
                "diagnostic targets a non-detectable failure target",
                "DiagnosticTask",
                diag.id,
            )

    # Production.
    if len(c.production_functions) > 1:
        for pf in c.production_functions[1:]:
            out.error(
                "MULTIPLE_PRODUCTION_FUNCTIONS",
                "only one production function per version",
                "ProductionFunction",
                pf.id,
            )
    for impact in c.production_impacts:
        if impact.equipment_id not in equipment:
            out.error(
                "IMPACT_UNKNOWN_EQUIPMENT",
                "impact refers to unknown equipment",
                "ProductionImpact",
                impact.id,
            )
        if (
            impact.failure_mode_id is not None
            and impact.failure_mode_id not in modes
        ):
            out.error(
                "IMPACT_UNKNOWN_FAILURE_MODE",
                "impact refers to unknown failure mode",
                "ProductionImpact",
                impact.id,
            )

    _validate_structures(c, out, equipment, structures)
    return ValidationReport(tuple(out.issues))


def _validate_maintenance(
    c: SystemVersionContent,
    out: _Collector,
    equipment: Mapping[UUID, object],
    modes: Mapping[UUID, object],
    tasks: Mapping[UUID, object],
) -> None:
    mode_owner = {m.id: m.equipment_id for m in c.failure_modes}
    for task in c.maintenance_tasks:
        if task.equipment_id not in equipment:
            out.error(
                "MAINTENANCE_UNKNOWN_EQUIPMENT",
                "task refers to unknown equipment",
                "MaintenanceTask",
                task.id,
            )
        if task.failure_mode_id is not None:
            if task.failure_mode_id not in modes:
                out.error(
                    "MAINTENANCE_UNKNOWN_FAILURE_MODE",
                    "task refers to unknown failure mode",
                    "MaintenanceTask",
                    task.id,
                )
            elif mode_owner[task.failure_mode_id] != task.equipment_id:
                out.error(
                    "MAINTENANCE_EQUIPMENT_MISMATCH",
                    "failure mode belongs to other equipment",
                    "MaintenanceTask",
                    task.id,
                )
    dup = _duplicates(
        d.maintenance_task_id for d in c.maintenance_distributions
    )
    for dist in c.maintenance_distributions:
        if dist.maintenance_task_id not in tasks:
            out.error(
                "DURATION_UNKNOWN_TASK",
                "duration refers to unknown task",
                "MaintenanceDistribution",
                dist.id,
            )
        elif dist.maintenance_task_id in dup:
            out.error(
                "DUPLICATE_MAINTENANCE_DISTRIBUTION",
                "task has several duration distributions",
                "MaintenanceDistribution",
                dist.id,
            )
    for effect in c.maintenance_effects:
        if effect.maintenance_task_id not in tasks:
            out.error(
                "EFFECT_UNKNOWN_TASK",
                "effect refers to unknown task",
                "MaintenanceEffect",
                effect.id,
            )
        if (
            effect.failure_mode_id is not None
            and effect.failure_mode_id not in modes
        ):
            out.error(
                "EFFECT_UNKNOWN_FAILURE_MODE",
                "effect refers to unknown failure mode",
                "MaintenanceEffect",
                effect.id,
            )


def _validate_requirements(
    c: SystemVersionContent,
    out: _Collector,
    tasks: Mapping[UUID, object],
    resources: Mapping[UUID, object],
    spares: Mapping[UUID, object],
) -> None:
    for req in c.resource_requirements:
        if req.maintenance_task_id not in tasks:
            out.error(
                "REQUIREMENT_UNKNOWN_TASK",
                "requirement refers to unknown task",
                "ResourceRequirement",
                req.id,
            )
        if req.resource_id not in resources:
            out.error(
                "REQUIREMENT_UNKNOWN_RESOURCE",
                "requirement refers to unknown resource",
                "ResourceRequirement",
                req.id,
            )
    for spare_req in c.spare_part_requirements:
        if spare_req.maintenance_task_id not in tasks:
            out.error(
                "REQUIREMENT_UNKNOWN_TASK",
                "requirement refers to unknown task",
                "SparePartRequirement",
                spare_req.id,
            )
        if spare_req.spare_part_id not in spares:
            out.error(
                "REQUIREMENT_UNKNOWN_SPARE_PART",
                "requirement refers to unknown spare part",
                "SparePartRequirement",
                spare_req.id,
            )


def _validate_structures(
    c: SystemVersionContent,
    out: _Collector,
    equipment: Mapping[UUID, object],
    structures: Mapping[UUID, object],
) -> None:
    count = Counter(m.structure_id for m in c.structure_members)
    for struct in c.structures:
        if (
            struct.parent_structure_id is not None
            and struct.parent_structure_id not in structures
        ):
            out.error(
                "STRUCTURE_UNKNOWN_PARENT",
                "parent structure does not exist",
                "ReliabilityStructure",
                struct.id,
            )
        n = count[struct.id]
        if n == 0:
            out.error(
                "STRUCTURE_EMPTY",
                "structure has no members",
                "ReliabilityStructure",
                struct.id,
            )
        elif (
            struct.structure_type
            in (StructureType.PARALLEL, StructureType.STANDBY)
            and n < 2
        ):
            out.error(
                "STRUCTURE_TOO_FEW_MEMBERS",
                f"{struct.structure_type} needs at least 2 members",
                "ReliabilityStructure",
                struct.id,
            )
        elif (
            struct.structure_type is StructureType.K_OF_N
            and struct.k is not None
            and struct.k > n
        ):
            out.error(
                "K_OF_N_INVALID",
                f"k={struct.k} exceeds the number of members ({n})",
                "ReliabilityStructure",
                struct.id,
            )
    cyclic = _find_cycle_members(
        {s.id: s.parent_structure_id for s in c.structures}
    )
    for sid in sorted(cyclic, key=str):
        out.error(
            "STRUCTURE_CYCLE",
            "structure hierarchy contains a cycle",
            "ReliabilityStructure",
            sid,
        )
    for member in c.structure_members:
        if member.structure_id not in structures:
            out.error(
                "MEMBER_UNKNOWN_STRUCTURE",
                "member refers to unknown structure",
                "ReliabilityStructureMember",
                member.id,
            )
        if (
            member.equipment_id is not None
            and member.equipment_id not in equipment
        ):
            out.error(
                "MEMBER_UNKNOWN_EQUIPMENT",
                "member refers to unknown equipment",
                "ReliabilityStructureMember",
                member.id,
            )
        if (
            member.child_structure_id is not None
            and member.child_structure_id not in structures
        ):
            out.error(
                "MEMBER_UNKNOWN_CHILD_STRUCTURE",
                "member refers to unknown child structure",
                "ReliabilityStructureMember",
                member.id,
            )


def _warn_synthetic(
    out: _Collector,
    provenance: Provenance | None,
    entity: str,
    entity_id: UUID,
) -> None:
    if provenance is not None and provenance.is_synthetic:
        out.warning(
            "SYNTHETIC_PARAMETER",
            "value is an AI/synthetic estimate, not an engineering fact",
            entity,
            entity_id,
        )


def validate_engineering(
    content: SystemVersionContent,
) -> ValidationReport:
    """Level 3: engineering plausibility of the content."""
    out = _Collector(ValidationLevel.ENGINEERING)
    c = content

    impacted = {i.equipment_id for i in c.production_impacts}
    for item in c.equipment:
        if item.criticality is Criticality.CRITICAL and (
            item.id not in impacted
        ):
            out.error(
                "CRITICAL_WITHOUT_PRODUCTION_IMPACT",
                "critical equipment must have a production impact",
                "Equipment",
                item.id,
            )

    modes = {m.id: m for m in c.failure_modes}
    for fd in c.failure_distributions:
        _warn_synthetic(out, fd.provenance, "FailureDistribution", fd.id)
        mode = modes.get(fd.failure_mode_id)
        if mode is None or mode.pf_interval is None:
            continue
        median = fd.distribution.to_minutes().quantile(0.5)
        if mode.pf_interval.to_minutes() >= median:
            out.warning(
                "PF_EXCEEDS_TYPICAL_LIFE",
                "PF interval is not shorter than the median life",
                "FailureMode",
                mode.id,
            )
    for md in c.maintenance_distributions:
        _warn_synthetic(out, md.provenance, "MaintenanceDistribution", md.id)

    for diag in c.diagnostic_tasks:
        _warn_synthetic(out, diag.provenance, "DiagnosticTask", diag.id)
        mode = modes.get(diag.failure_mode_id)
        if mode is None or mode.pf_interval is None:
            continue
        if diag.interval.to_minutes() >= mode.pf_interval.to_minutes():
            out.warning(
                "DIAGNOSTIC_INTERVAL_EXCEEDS_PF",
                "check interval is not shorter than the PF interval; "
                "detection is not guaranteed",
                "DiagnosticTask",
                diag.id,
            )

    resources = {r.id: r for r in c.resources}
    for req in c.resource_requirements:
        res = resources.get(req.resource_id)
        if res is not None and req.quantity > res.capacity:
            out.error(
                "RESOURCE_REQUIREMENT_EXCEEDS_CAPACITY",
                "task needs more units than the resource capacity",
                "ResourceRequirement",
                req.id,
            )
    spares = {s.id: s for s in c.spare_parts}
    for spare_req in c.spare_part_requirements:
        part = spares.get(spare_req.spare_part_id)
        if part is not None and part.stock == 0 and part.lead_time is None:
            out.warning(
                "SPARE_PART_NO_SUPPLY",
                "spare part has no stock and no lead time",
                "SparePartRequirement",
                spare_req.id,
            )
    return ValidationReport(tuple(out.issues))


def validate_content(content: SystemVersionContent) -> ValidationReport:
    """Run levels 2 and 3 and return the combined report."""
    return validate_domain(content).merge(validate_engineering(content))

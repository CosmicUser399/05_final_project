"""Structural Petri validation (level PETRI, local)."""

from __future__ import annotations

from app.domain.petri.entities import PetriModel
from app.domain.petri.entities import PetriSubnet
from app.domain.validation import Severity
from app.domain.validation import ValidationIssue
from app.domain.validation import ValidationLevel
from app.domain.validation import ValidationReport


def validate_petri_structure(model: PetriModel) -> ValidationReport:
    """Check local structural rules before calling Petri-Pilot."""
    issues: list[ValidationIssue] = []
    if not model.subnets:
        issues.append(
            ValidationIssue(
                code="PETRI_EMPTY_MODEL",
                message="Petri model has no subnets",
                level=ValidationLevel.PETRI,
                severity=Severity.ERROR,
                entity="PetriModel",
            )
        )
        return ValidationReport(tuple(issues))
    for subnet in model.subnets:
        issues.extend(_validate_subnet(subnet))
    return ValidationReport(tuple(issues))


def _validate_subnet(subnet: PetriSubnet) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    entity = "PetriSubnet"
    entity_id = subnet.key
    if not subnet.places:
        issues.append(
            ValidationIssue(
                code="PETRI_EMPTY_SUBNET",
                message=f"subnet {subnet.key!r} has no places",
                level=ValidationLevel.PETRI,
                severity=Severity.ERROR,
                entity=entity,
                entity_id=entity_id,
            )
        )
    if not subnet.transitions:
        issues.append(
            ValidationIssue(
                code="PETRI_NO_TRANSITIONS",
                message=f"subnet {subnet.key!r} has no transitions",
                level=ValidationLevel.PETRI,
                severity=Severity.ERROR,
                entity=entity,
                entity_id=entity_id,
            )
        )
    place_ids = {p.id for p in subnet.places}
    transition_ids = {t.id for t in subnet.transitions}
    known = place_ids | transition_ids
    connected: set[str] = set()
    for arc in subnet.arcs:
        if arc.source not in known:
            issues.append(
                ValidationIssue(
                    code="PETRI_INVALID_ARC_SOURCE",
                    message=f"arc source {arc.source!r} is unknown",
                    level=ValidationLevel.PETRI,
                    severity=Severity.ERROR,
                    entity=entity,
                    entity_id=entity_id,
                )
            )
        if arc.target not in known:
            issues.append(
                ValidationIssue(
                    code="PETRI_INVALID_ARC_TARGET",
                    message=f"arc target {arc.target!r} is unknown",
                    level=ValidationLevel.PETRI,
                    severity=Severity.ERROR,
                    entity=entity,
                    entity_id=entity_id,
                )
            )
        if arc.weight <= 0:
            issues.append(
                ValidationIssue(
                    code="PETRI_INVALID_ARC_WEIGHT",
                    message="arc weight must be positive",
                    level=ValidationLevel.PETRI,
                    severity=Severity.ERROR,
                    entity=entity,
                    entity_id=entity_id,
                )
            )
        src_is_place = arc.source in place_ids
        tgt_is_place = arc.target in place_ids
        src_is_tr = arc.source in transition_ids
        tgt_is_tr = arc.target in transition_ids
        if not ((src_is_place and tgt_is_tr) or (src_is_tr and tgt_is_place)):
            issues.append(
                ValidationIssue(
                    code="PETRI_ARC_KIND_MISMATCH",
                    message=(
                        "arc must connect a place to a transition "
                        "or a transition to a place"
                    ),
                    level=ValidationLevel.PETRI,
                    severity=Severity.ERROR,
                    entity=entity,
                    entity_id=entity_id,
                )
            )
        connected.add(arc.source)
        connected.add(arc.target)
    for place in subnet.places:
        if place.id not in connected:
            issues.append(
                ValidationIssue(
                    code="PETRI_UNCONNECTED_PLACE",
                    message=f"place {place.id!r} has no arcs",
                    level=ValidationLevel.PETRI,
                    severity=Severity.ERROR,
                    entity=entity,
                    entity_id=entity_id,
                )
            )
        if place.initial < 0:
            issues.append(
                ValidationIssue(
                    code="PETRI_NEGATIVE_MARKING",
                    message="initial marking must be non-negative",
                    level=ValidationLevel.PETRI,
                    severity=Severity.ERROR,
                    entity=entity,
                    entity_id=entity_id,
                )
            )
    for transition in subnet.transitions:
        if transition.id not in connected:
            issues.append(
                ValidationIssue(
                    code="PETRI_UNCONNECTED_TRANSITION",
                    message=(f"transition {transition.id!r} has no arcs"),
                    level=ValidationLevel.PETRI,
                    severity=Severity.ERROR,
                    entity=entity,
                    entity_id=entity_id,
                )
            )
    if not any(p.initial > 0 for p in subnet.places):
        issues.append(
            ValidationIssue(
                code="PETRI_NO_INITIAL_TOKEN",
                message=f"subnet {subnet.key!r} has no initial tokens",
                level=ValidationLevel.PETRI,
                severity=Severity.WARNING,
                entity=entity,
                entity_id=entity_id,
            )
        )
    return issues

"""Generate, validate and analyse Petri models."""

# ruff: noqa: D102

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID
from uuid import uuid4

from sqlalchemy import select

from app.application.ports import PetriPilotPort
from app.application.ports import PetriPilotResult
from app.application.ports import PetriPilotStatus
from app.domain.errors import ExternalServiceError
from app.domain.errors import ModelGenerationError
from app.domain.errors import NotFoundError
from app.domain.petri.conformance import conformance_log_json
from app.domain.petri.conformance import events_to_conformance_log
from app.domain.petri.entities import PetriModel
from app.domain.petri.export import to_pilot_json
from app.domain.petri.generator import PetriModelGenerator
from app.domain.petri.validation import validate_petri_structure
from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiler import ReliabilityCompiler
from app.domain.validation import Severity
from app.domain.validation import ValidationIssue
from app.domain.validation import ValidationLevel
from app.domain.validation import ValidationReport
from app.infrastructure.db.models import PetriModelRow
from app.infrastructure.db.models import ReliabilityModelRow
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.mcp.mock_petri_pilot import MockPetriPilotProvider


class PetriService:
    """Application service for the Petri modelling flow."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
        pilot: PetriPilotPort | None = None,
        *,
        generator: PetriModelGenerator | None = None,
        compiler: ReliabilityCompiler | None = None,
        max_states: int = 10_000,
    ) -> None:
        """Store dependencies (default pilot = mock)."""
        self._uow_factory = uow_factory
        self._pilot = pilot or MockPetriPilotProvider()
        self._generator = generator or PetriModelGenerator()
        self._compiler = compiler or ReliabilityCompiler()
        self._max_states = max_states

    def generate(
        self,
        version_id: UUID,
        *,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Compile reliability model if needed and persist Petri model."""
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            content = uow.content.load_content(version_id)
            compiled = self._compiler.compile(version_id, content)
            reliability = uow.session.scalars(
                select(ReliabilityModelRow)
                .where(ReliabilityModelRow.version_id == version_id)
                .order_by(ReliabilityModelRow.generated_at.desc())
            ).first()
            reliability_id = None if reliability is None else reliability.id
            if (
                reliability is not None
                and reliability.model_hash != compiled.model_hash()
            ):
                reliability_id = None
            petri = self._generator.generate(
                compiled,
                reliability_model_id=reliability_id,
            )
            structural = validate_petri_structure(petri)
            if not structural.is_valid:
                raise ModelGenerationError(
                    "Petri model failed structural validation",
                    code="PETRI_STRUCTURAL_INVALID",
                    entity="PetriModel",
                    entity_id=str(version_id),
                )
            row = PetriModelRow(
                id=uuid4(),
                version_id=version_id,
                reliability_model_id=reliability_id,
                reliability_model_hash=compiled.model_hash(),
                definition_json=petri.definition_dict(),
                schema_version=str(petri.schema_version),
                validation_status="PENDING",
                notes=notes,
            )
            uow.session.add(row)
            uow.session.flush()
            uow.session.refresh(row)
            return row.as_dict()

    def get_latest(self, version_id: UUID) -> dict[str, Any] | None:
        """Return the newest Petri model for a version."""
        with self._uow_factory() as uow:
            uow.versions.get(version_id)
            row = uow.session.scalars(
                select(PetriModelRow)
                .where(PetriModelRow.version_id == version_id)
                .order_by(PetriModelRow.generated_at.desc())
            ).first()
            return None if row is None else row.as_dict()

    def get(self, petri_id: UUID) -> dict[str, Any]:
        """Return one Petri model by id."""
        with self._uow_factory() as uow:
            row = self._get_row(uow, petri_id)
            return row.as_dict()

    def validate(self, petri_id: UUID) -> dict[str, Any]:
        """Run local structure checks + Petri-Pilot validate/analyze."""
        with self._uow_factory() as uow:
            row = self._get_row(uow, petri_id)
            model = PetriModel.model_validate(row.definition_json)
            report = validate_petri_structure(model)
            pilot_version: str | None = None
            subnet_results: list[dict[str, Any]] = []
            for subnet in model.subnets:
                model_json = to_pilot_json(subnet)
                validated = self._pilot.validate(model_json)
                self._raise_if_external(validated)
                analyzed = self._pilot.analyze(model_json)
                self._raise_if_external(analyzed)
                if validated.petri_pilot_version:
                    pilot_version = validated.petri_pilot_version
                subnet_results.append(
                    {
                        "subnet_key": subnet.key,
                        "validate": validated.model_dump(mode="json"),
                        "analyze": analyzed.model_dump(mode="json"),
                    }
                )
                report = report.merge(
                    _issues_from_pilot(subnet.key, validated, analyzed)
                )
            status = "VALID" if report.is_valid else "INVALID"
            row.validation_status = status
            row.petri_pilot_version = pilot_version
            uow.session.flush()
            return {
                "petri_model_id": row.id,
                "validation_status": status,
                "report": {
                    "is_valid": report.is_valid,
                    "issues": [
                        {
                            "code": i.code,
                            "message": i.message,
                            "level": str(i.level),
                            "severity": str(i.severity),
                            "entity": i.entity,
                            "entity_id": i.entity_id,
                        }
                        for i in report.issues
                    ],
                },
                "subnets": subnet_results,
                "petri_pilot_version": pilot_version,
            }

    def analyze(
        self,
        petri_id: UUID,
        *,
        full: bool = False,
        subnet_key: str | None = None,
    ) -> dict[str, Any]:
        """Run Petri-Pilot analysis on one or all subnets."""
        with self._uow_factory() as uow:
            row = self._get_row(uow, petri_id)
            model = PetriModel.model_validate(row.definition_json)
            targets = _select_subnets(model, subnet_key)
            results: list[dict[str, Any]] = []
            for subnet in targets:
                outcome = self._pilot.analyze(
                    to_pilot_json(subnet),
                    full=full,
                )
                self._raise_if_external(outcome)
                results.append(
                    {
                        "subnet_key": subnet.key,
                        "result": outcome.model_dump(mode="json"),
                    }
                )
            return {"petri_model_id": row.id, "subnets": results}

    def verify(
        self,
        petri_id: UUID,
        properties: list[str] | None = None,
        *,
        subnet_key: str | None = None,
    ) -> dict[str, Any]:
        """Verify formal properties on selected subnets."""
        props = properties or [
            "deadlock-free",
            "bounded",
            "live",
        ]
        with self._uow_factory() as uow:
            row = self._get_row(uow, petri_id)
            model = PetriModel.model_validate(row.definition_json)
            targets = _select_subnets(model, subnet_key)
            results: list[dict[str, Any]] = []
            for subnet in targets:
                outcome = self._pilot.verify(
                    to_pilot_json(subnet),
                    props,
                    max_states=self._max_states,
                )
                self._raise_if_external(outcome)
                results.append(
                    {
                        "subnet_key": subnet.key,
                        "result": outcome.model_dump(mode="json"),
                    }
                )
            return {
                "petri_model_id": row.id,
                "properties": props,
                "subnets": results,
            }

    def conformance(
        self,
        petri_id: UUID,
        events: list[Any],
        *,
        subnet_key: str | None = None,
    ) -> dict[str, Any]:
        """Cross-check a RAM event log against Petri subnets."""
        with self._uow_factory() as uow:
            row = self._get_row(uow, petri_id)
            model = PetriModel.model_validate(row.definition_json)
            log_events = events_to_conformance_log(model, events)
            by_case: dict[str, list[Any]] = {}
            for item in log_events:
                by_case.setdefault(item.case, []).append(item)
            results: list[dict[str, Any]] = []
            targets = [
                s
                for s in model.subnets
                if s.kind == "failure_mode"
                and (subnet_key is None or s.key == subnet_key)
            ]
            for subnet in targets:
                case_events = by_case.get(subnet.case_id, [])
                log_json = conformance_log_json(case_events)
                outcome = self._pilot.conformance(
                    to_pilot_json(subnet),
                    log_json,
                )
                self._raise_if_external(outcome)
                results.append(
                    {
                        "subnet_key": subnet.key,
                        "event_count": len(case_events),
                        "result": outcome.model_dump(mode="json"),
                    }
                )
            return {
                "petri_model_id": row.id,
                "mapped_events": len(log_events),
                "subnets": results,
            }

    def diff(self, petri_id_a: UUID, petri_id_b: UUID) -> dict[str, Any]:
        """Compare system subnets of two Petri models."""
        with self._uow_factory() as uow:
            row_a = self._get_row(uow, petri_id_a)
            row_b = self._get_row(uow, petri_id_b)
            model_a = PetriModel.model_validate(row_a.definition_json)
            model_b = PetriModel.model_validate(row_b.definition_json)
            net_a = model_a.subnet("system") or model_a.subnets[0]
            net_b = model_b.subnet("system") or model_b.subnets[0]
            outcome = self._pilot.diff(
                to_pilot_json(net_a),
                to_pilot_json(net_b),
            )
            self._raise_if_external(outcome)
            return {
                "petri_model_id_a": row_a.id,
                "petri_model_id_b": row_b.id,
                "result": outcome.model_dump(mode="json"),
            }

    def canonical(
        self,
        petri_id: UUID,
        *,
        subnet_key: str | None = None,
    ) -> dict[str, Any]:
        """Return canonical ids for subnets (template dedup)."""
        with self._uow_factory() as uow:
            row = self._get_row(uow, petri_id)
            model = PetriModel.model_validate(row.definition_json)
            targets = _select_subnets(model, subnet_key)
            results: list[dict[str, Any]] = []
            for subnet in targets:
                outcome = self._pilot.canonical(to_pilot_json(subnet))
                self._raise_if_external(outcome)
                results.append(
                    {
                        "subnet_key": subnet.key,
                        "result": outcome.model_dump(mode="json"),
                    }
                )
            return {"petri_model_id": row.id, "subnets": results}

    def load_compiled_for_tests(self, compiled: CompiledModel) -> PetriModel:
        """Generate without persistence (unit tests)."""
        return self._generator.generate(compiled)

    def _get_row(
        self,
        uow: SqlAlchemyUnitOfWork,
        petri_id: UUID,
    ) -> PetriModelRow:
        row = uow.session.get(PetriModelRow, petri_id)
        if row is None:
            raise NotFoundError(
                "petri model not found",
                entity="PetriModel",
                entity_id=str(petri_id),
            )
        return row

    @staticmethod
    def _raise_if_external(result: PetriPilotResult) -> None:
        if result.status is PetriPilotStatus.TIMEOUT:
            raise ExternalServiceError(
                result.message or "Petri-Pilot timeout",
                code="PETRI_PILOT_TIMEOUT",
                entity="PetriPilot",
            )
        if result.status is PetriPilotStatus.EXTERNAL_ERROR:
            raise ExternalServiceError(
                result.message or "Petri-Pilot unavailable",
                code="PETRI_PILOT_UNAVAILABLE",
                entity="PetriPilot",
            )


def _select_subnets(model: PetriModel, subnet_key: str | None) -> list[Any]:
    if subnet_key is None:
        return list(model.subnets)
    net = model.subnet(subnet_key)
    if net is None:
        raise NotFoundError(
            "petri subnet not found",
            entity="PetriSubnet",
            entity_id=subnet_key,
        )
    return [net]


def _issues_from_pilot(
    subnet_key: str,
    validated: PetriPilotResult,
    analyzed: PetriPilotResult,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    if validated.status is not PetriPilotStatus.SUCCESS:
        issues.append(
            ValidationIssue(
                code="PETRI_PILOT_VALIDATE_FAILED",
                message=validated.message or "validate failed",
                level=ValidationLevel.PETRI,
                severity=Severity.ERROR,
                entity="PetriSubnet",
                entity_id=subnet_key,
            )
        )
    else:
        valid = validated.data.get("valid")
        if valid is False:
            errors = validated.data.get("errors") or []
            message = "Petri-Pilot reported invalid structure"
            if isinstance(errors, list) and errors:
                first = errors[0]
                if isinstance(first, dict):
                    message = str(first.get("message", message))
            issues.append(
                ValidationIssue(
                    code="PETRI_PILOT_INVALID",
                    message=message,
                    level=ValidationLevel.PETRI,
                    severity=Severity.ERROR,
                    entity="PetriSubnet",
                    entity_id=subnet_key,
                )
            )
    if analyzed.status is PetriPilotStatus.SUCCESS:
        analysis = analyzed.data.get("analysis")
        if isinstance(analysis, dict) and analysis.get("has_deadlocks"):
            issues.append(
                ValidationIssue(
                    code="PETRI_DEADLOCK",
                    message="subnet has reachable deadlocks",
                    level=ValidationLevel.PETRI,
                    severity=Severity.ERROR,
                    entity="PetriSubnet",
                    entity_id=subnet_key,
                )
            )
        state_count = None
        if isinstance(analysis, dict):
            state_count = analysis.get("state_count")
        if isinstance(state_count, int) and state_count >= 10_000:
            issues.append(
                ValidationIssue(
                    code="PETRI_STATE_LIMIT",
                    message=(
                        "state space reached Petri-Pilot limit; "
                        "prefer per-subnet analysis"
                    ),
                    level=ValidationLevel.PETRI,
                    severity=Severity.WARNING,
                    entity="PetriSubnet",
                    entity_id=subnet_key,
                )
            )
    elif analyzed.status not in {
        PetriPilotStatus.TIMEOUT,
        PetriPilotStatus.EXTERNAL_ERROR,
    }:
        issues.append(
            ValidationIssue(
                code="PETRI_PILOT_ANALYZE_FAILED",
                message=analyzed.message or "analyze failed",
                level=ValidationLevel.PETRI,
                severity=Severity.WARNING,
                entity="PetriSubnet",
                entity_id=subnet_key,
            )
        )
    return ValidationReport(tuple(issues))

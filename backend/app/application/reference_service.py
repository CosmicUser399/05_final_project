"""Reference data use cases: ingest, search, link, apply."""

# ruff: noqa: D102, D107

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.application.audit import write_audit
from app.domain.errors import NotFoundError
from app.domain.errors import ValidationError
from app.domain.provenance import Provenance
from app.domain.reference.entities import ParameterKind
from app.domain.reference.entities import ReferenceParameter
from app.domain.reliability.distributions import Constant
from app.domain.reliability.distributions import Exponential
from app.domain.reliability.distributions import parse_distribution
from app.domain.reliability.entities import FailureDistribution
from app.domain.units import TimeUnit
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.reference_data.iso14224_repository import (
    ISO14224Repository,
)
from app.infrastructure.reference_data.oreda_repository import OREDARepository

_CLASS_ALIASES: dict[str, str] = {
    "pump": "PUMP.CENT",
    "centrifugal pump": "PUMP.CENT",
    "centrifugal_pump": "PUMP.CENT",
    "compressor": "COMP.REC",
    "reciprocating compressor": "COMP.REC",
    "heat exchanger": "HEX.SHELL",
    "heat_exchanger": "HEX.SHELL",
    "valve": "VALVE.ONOFF",
    "on/off valve": "VALVE.ONOFF",
    "motor": "MOTOR.AC",
    "electric motor": "MOTOR.AC",
    "instrumentation": "INST.TX",
    "transmitter": "INST.TX",
}


class ReferenceDataService:
    """Ingest and query OREDA/ISO reference data; link to equipment."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
    ) -> None:
        self._session_factory = session_factory
        self._uow_factory = uow_factory

    def ingest_demo(self, *, replace: bool = False) -> dict[str, Any]:
        with self._session_factory() as session:
            oreda = OREDARepository(session)
            iso = ISO14224Repository(session)
            oreda_count = oreda.ingest_csv(replace=replace)
            iso_count = iso.ingest_json(replace=replace)
            session.commit()
            return {
                "oreda_parameters": oreda_count,
                "iso_taxonomy_nodes": iso_count,
                "oreda_total": oreda.count_parameters(),
                "iso_total": iso.count_nodes(),
                "available": True,
            }

    def status(self) -> dict[str, Any]:
        with self._session_factory() as session:
            oreda = OREDARepository(session)
            iso = ISO14224Repository(session)
            oreda_total = oreda.count_parameters()
            iso_total = iso.count_nodes()
            return {
                "available": oreda_total > 0 or iso_total > 0,
                "oreda_parameters": oreda_total,
                "iso_taxonomy_nodes": iso_total,
            }

    def search_parameters(
        self,
        *,
        query: str | None = None,
        equipment_class: str | None = None,
        equipment_class_code: str | None = None,
        parameter_kind: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            oreda = OREDARepository(session)
            items = oreda.search(
                query=query,
                equipment_class=equipment_class,
                equipment_class_code=equipment_class_code,
                parameter_kind=parameter_kind,
                limit=limit,
            )
            return {
                "query": query,
                "available": oreda.count_parameters() > 0,
                "count": len(items),
                "limit": limit,
                "items": [item.model_dump(mode="json") for item in items],
            }

    def search_taxonomy(
        self,
        *,
        query: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            iso = ISO14224Repository(session)
            items = iso.search_nodes(query=query, limit=limit)
            return {
                "query": query,
                "available": iso.count_nodes() > 0,
                "count": len(items),
                "limit": limit,
                "items": [item.model_dump(mode="json") for item in items],
            }

    def get_parameter(self, parameter_id: UUID) -> dict[str, Any]:
        with self._session_factory() as session:
            oreda = OREDARepository(session)
            param = oreda.get(parameter_id)
            if param is None:
                raise NotFoundError(
                    "reference parameter not found",
                    entity="ReferenceParameter",
                    entity_id=str(parameter_id),
                )
            return param.model_dump(mode="json")

    def suggest_for_class(
        self,
        equipment_class: str | None,
        *,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Suggest OREDA rows and ISO node for an equipment class label."""
        if not equipment_class or not equipment_class.strip():
            return []
        code = self._resolve_class_code(equipment_class)
        with self._session_factory() as session:
            oreda = OREDARepository(session)
            iso = ISO14224Repository(session)
            params = oreda.search(
                equipment_class_code=code,
                limit=limit,
            )
            if not params:
                params = oreda.search(
                    equipment_class=equipment_class,
                    limit=limit,
                )
            node = iso.find_by_code(code) if code else None
            if node is None:
                nodes = iso.search_nodes(query=equipment_class, limit=1)
                node = nodes[0] if nodes else None
            result: list[dict[str, Any]] = []
            if node is not None:
                result.append(
                    {
                        "kind": "taxonomy_node",
                        "taxonomy_node_id": str(node.id),
                        "code": node.code,
                        "name": node.name,
                        "source_type": "ISO_14224",
                    }
                )
            for param in params:
                result.append(
                    {
                        "kind": "parameter",
                        "parameter_id": str(param.id),
                        "equipment_class": param.equipment_class,
                        "equipment_class_code": param.equipment_class_code,
                        "failure_mode_name": param.failure_mode_name,
                        "parameter_name": param.parameter_name,
                        "parameter_kind": param.parameter_kind.value,
                        "value": param.value,
                        "unit": param.unit,
                        "source_type": param.source_type.value,
                        "source_document": param.source_document,
                        "source_reference": param.source_reference,
                        "confidence": param.confidence.value,
                    }
                )
            return result

    def link_equipment(
        self,
        equipment_id: UUID,
        taxonomy_node_id: UUID,
        *,
        actor_id: UUID | None = None,
        source: str | None = "reference",
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Attach an ISO taxonomy node to equipment (DRAFT only)."""
        with self._session_factory() as session:
            iso = ISO14224Repository(session)
            node = iso.get_node(taxonomy_node_id)
            if node is None:
                raise NotFoundError(
                    "taxonomy node not found",
                    entity="TaxonomyNode",
                    entity_id=str(taxonomy_node_id),
                )
        with self._uow_factory() as uow:
            current = uow.content.get_equipment(equipment_id)
            updated = current.model_copy(
                update={"taxonomy_node_id": taxonomy_node_id}
            )
            uow.content.save_equipment(updated)
            write_audit(
                uow,
                version_id=updated.version_id,
                entity_type="Equipment",
                entity_id=updated.id,
                action="UPDATE",
                actor_id=actor_id,
                old_value=current,
                new_value=updated,
                source=source,
                reason=reason or "link ISO 14224 taxonomy",
            )
            return updated.model_dump(mode="json")

    def auto_link_equipment(
        self,
        equipment_id: UUID,
        *,
        actor_id: UUID | None = None,
    ) -> dict[str, Any] | None:
        """Link equipment to ISO node by class/code when a match exists."""
        with self._uow_factory() as uow:
            equipment = uow.content.get_equipment(equipment_id)
            class_label = equipment.equipment_class or equipment.category
        suggestions = self.suggest_for_class(class_label, limit=5)
        for item in suggestions:
            if item.get("kind") == "taxonomy_node":
                return self.link_equipment(
                    equipment_id,
                    UUID(str(item["taxonomy_node_id"])),
                    actor_id=actor_id,
                    source="reference_auto",
                    reason="auto-map equipment class to ISO 14224",
                )
        return None

    def apply_to_failure_mode(
        self,
        parameter_id: UUID,
        failure_mode_id: UUID,
        *,
        actor_id: UUID | None = None,
        source: str | None = "reference",
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Apply an OREDA parameter as FailureDistribution with provenance."""
        with self._session_factory() as session:
            oreda = OREDARepository(session)
            param = oreda.get(parameter_id)
            if param is None:
                raise NotFoundError(
                    "reference parameter not found",
                    entity="ReferenceParameter",
                    entity_id=str(parameter_id),
                )
        distribution = _distribution_from_parameter(param)
        provenance = Provenance.oreda(
            param.source_reference,
            confidence=param.confidence,
        )
        with self._uow_factory() as uow:
            mode = uow.content.get_failure_mode(failure_mode_id)
            existing = [
                d
                for d in uow.content.list_failure_distributions(
                    mode.version_id
                )
                if d.failure_mode_id == failure_mode_id
            ]
            if existing:
                current = existing[0]
                updated = current.model_copy(
                    update={
                        "distribution": distribution,
                        "provenance": provenance,
                    }
                )
                uow.content.save_failure_distribution(updated)
                write_audit(
                    uow,
                    version_id=updated.version_id,
                    entity_type="FailureDistribution",
                    entity_id=updated.id,
                    action="UPDATE",
                    actor_id=actor_id,
                    old_value=current,
                    new_value=updated,
                    source=source,
                    reason=reason or f"apply OREDA {param.source_reference}",
                )
                return updated.model_dump(mode="json")

            created = FailureDistribution(
                version_id=mode.version_id,
                failure_mode_id=failure_mode_id,
                distribution=distribution,
                provenance=provenance,
            )
            uow.content.save_failure_distribution(created)
            write_audit(
                uow,
                version_id=created.version_id,
                entity_type="FailureDistribution",
                entity_id=created.id,
                action="CREATE",
                actor_id=actor_id,
                new_value=created,
                source=source,
                reason=reason or f"apply OREDA {param.source_reference}",
            )
            return created.model_dump(mode="json")

    def _resolve_class_code(self, equipment_class: str) -> str | None:
        label = equipment_class.strip().lower()
        if "." in equipment_class:
            return equipment_class.strip().upper()
        return _CLASS_ALIASES.get(label)


def _distribution_from_parameter(param: ReferenceParameter) -> Any:
    """Build a domain distribution from a reference parameter row."""
    if param.distribution_params_json and param.distribution_type:
        payload: dict[str, Any] = {
            "type": param.distribution_type.upper(),
            **param.distribution_params_json,
        }
        unit = _unit_from_string(param.unit)
        payload.setdefault("unit", unit.value)
        return parse_distribution(payload)

    kind = param.parameter_kind
    if kind is ParameterKind.FAILURE_RATE:
        return Exponential(
            lambda_=float(param.value),
            unit=TimeUnit.HOURS,
        )
    if kind in {
        ParameterKind.MTTR,
        ParameterKind.REPAIR_TIME,
        ParameterKind.MTTF,
    }:
        return Constant(
            value=float(param.value),
            unit=_unit_from_string(param.unit),
        )
    raise ValidationError(
        "cannot map reference parameter to a distribution",
        code="REFERENCE_NOT_APPLICABLE",
        entity="ReferenceParameter",
        entity_id=str(param.id),
    )


def _unit_from_string(unit: str) -> TimeUnit:
    normalized = unit.strip().lower().replace(" ", "")
    mapping = {
        "hour": TimeUnit.HOURS,
        "hours": TimeUnit.HOURS,
        "h": TimeUnit.HOURS,
        "1/hour": TimeUnit.HOURS,
        "1/h": TimeUnit.HOURS,
        "perhour": TimeUnit.HOURS,
        "minute": TimeUnit.MINUTES,
        "minutes": TimeUnit.MINUTES,
        "day": TimeUnit.DAYS,
        "days": TimeUnit.DAYS,
    }
    return mapping.get(normalized, TimeUnit.HOURS)

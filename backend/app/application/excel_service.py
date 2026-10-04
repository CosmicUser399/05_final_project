"""Excel export / import use cases for a system version."""

# ruff: noqa: D102, D107

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.application.audit import write_audit
from app.domain.diagnostics.entities import DiagnosticTask
from app.domain.equipment.entities import Equipment
from app.domain.equipment.entities import EquipmentComponent
from app.domain.equipment.entities import EquipmentConnection
from app.domain.errors import ValidationError
from app.domain.maintenance.entities import MaintenanceDistribution
from app.domain.maintenance.entities import MaintenanceEffect
from app.domain.maintenance.entities import MaintenanceTask
from app.domain.production.entities import ProductionFunction
from app.domain.production.entities import ProductionImpact
from app.domain.provenance import Confidence
from app.domain.provenance import Provenance
from app.domain.provenance import SourceType
from app.domain.reliability.distributions import parse_distribution
from app.domain.reliability.entities import FailureDistribution
from app.domain.reliability.entities import FailureMode
from app.domain.reliability.pf import PFInterval
from app.domain.resources.entities import Resource
from app.domain.resources.entities import SparePart
from app.domain.units import MassRate
from app.domain.units import TimeValue
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.excel.exporter import export_version_workbook
from app.infrastructure.excel.importer import ImportPreview
from app.infrastructure.excel.importer import parse_workbook


class ExcelService:
    """Boundary adapter use cases for Excel exchange."""

    def __init__(
        self,
        uow_factory: Callable[[], SqlAlchemyUnitOfWork],
    ) -> None:
        self._uow_factory = uow_factory

    def export_version(
        self,
        version_id: UUID,
        *,
        dataset_label: str | None = None,
    ) -> bytes:
        with self._uow_factory() as uow:
            version = uow.versions.get(version_id)
            system = uow.systems.get(version.system_id)
            content = uow.content.load_content(version_id)
            return export_version_workbook(
                system,
                version,
                content,
                dataset_label=dataset_label,
            )

    def preview_import(self, data: bytes) -> ImportPreview:
        return parse_workbook(data)

    def commit_import(
        self,
        version_id: UUID,
        data: bytes,
        *,
        actor_id: UUID | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        preview = parse_workbook(data)
        if not preview.is_valid:
            raise ValidationError(
                "Excel import has validation errors",
                code="EXCEL_IMPORT_INVALID",
                entity="ExcelWorkbook",
            )
        if not preview.equipment:
            raise ValidationError(
                "Excel workbook has no equipment rows",
                code="EXCEL_EMPTY",
                entity="ExcelWorkbook",
            )

        with self._uow_factory() as uow:
            version = uow.versions.get(version_id)
            version.ensure_editable()
            existing = uow.content.list_equipment(version_id)
            if existing:
                raise ValidationError(
                    "target version is not empty; use a fresh DRAFT",
                    code="EXCEL_TARGET_NOT_EMPTY",
                    entity="SystemVersion",
                    entity_id=str(version_id),
                )
            summary = self.apply_preview(
                uow,
                version_id,
                preview,
                actor_id=actor_id,
                reason=reason,
                source="excel_import",
            )
            return summary

    def apply_preview(
        self,
        uow: SqlAlchemyUnitOfWork,
        version_id: UUID,
        preview: ImportPreview,
        *,
        actor_id: UUID | None = None,
        reason: str | None = None,
        source: str = "excel_import",
    ) -> dict[str, Any]:
        """Persist a validated preview into an empty DRAFT version."""
        tag_to_id: dict[str, UUID] = {}
        # Parents first (no parent_tag), then children.
        pending = list(preview.equipment)
        guard = 0
        while pending and guard < len(preview.equipment) + 2:
            guard += 1
            next_pending: list[Any] = []
            for eq_row in pending:
                if eq_row.parent_tag and eq_row.parent_tag not in tag_to_id:
                    next_pending.append(eq_row)
                    continue
                equipment = Equipment(
                    version_id=version_id,
                    tag=eq_row.tag,
                    name=eq_row.name,
                    description=eq_row.description,
                    parent_id=(
                        tag_to_id[eq_row.parent_tag]
                        if eq_row.parent_tag
                        else None
                    ),
                    category=eq_row.category,
                    equipment_class=eq_row.equipment_class,
                    equipment_type=eq_row.equipment_type,
                    location=eq_row.location,
                    quantity=eq_row.quantity,
                    criticality=eq_row.criticality,
                    operating_mode=eq_row.operating_mode,
                    standby_mode=eq_row.standby_mode,
                    is_repairable=eq_row.is_repairable,
                )
                uow.content.save_equipment(equipment)
                write_audit(
                    uow,
                    version_id=version_id,
                    entity_type="Equipment",
                    entity_id=equipment.id,
                    action="CREATE",
                    actor_id=actor_id,
                    new_value=equipment,
                    source=source,
                    reason=reason,
                )
                tag_to_id[eq_row.tag] = equipment.id
            pending = next_pending
        if pending:
            raise ValidationError(
                "equipment parent cycle or missing parent",
                code="EXCEL_PARENT_CYCLE",
                entity="Equipment",
            )

        for comp_row in preview.components:
            component = EquipmentComponent(
                version_id=version_id,
                equipment_id=tag_to_id[comp_row.equipment_tag],
                name=comp_row.name,
                description=comp_row.description,
                quantity=comp_row.quantity,
            )
            uow.content.save_component(component)

        for conn_row in preview.connections:
            connection = EquipmentConnection(
                version_id=version_id,
                source_id=tag_to_id[conn_row.from_tag],
                target_id=tag_to_id[conn_row.to_tag],
                connection_type=conn_row.connection_type,
                description=conn_row.description,
            )
            uow.content.save_connection(connection)

        fm_key_to_id: dict[tuple[str, str], UUID] = {}
        for fm_row in preview.failure_modes:
            pf = None
            if fm_row.pf_value is not None and fm_row.pf_unit is not None:
                pf = PFInterval(value=fm_row.pf_value, unit=fm_row.pf_unit)
            mode = FailureMode(
                version_id=version_id,
                equipment_id=tag_to_id[fm_row.equipment_tag],
                name=fm_row.name,
                description=fm_row.description,
                is_detectable=fm_row.is_detectable,
                pf_interval=pf,
            )
            uow.content.save_failure_mode(mode)
            fm_key_to_id[(fm_row.equipment_tag, fm_row.name)] = mode.id

        for dist_row in preview.failure_distributions:
            key = (dist_row.equipment_tag, dist_row.failure_mode_name)
            fm_id = fm_key_to_id.get(key)
            if fm_id is None:
                continue
            dist = FailureDistribution(
                version_id=version_id,
                failure_mode_id=fm_id,
                distribution=parse_distribution(dist_row.distribution),
                provenance=Provenance(
                    source_type=dist_row.source_type,
                    confidence=dist_row.confidence,
                    source_reference=dist_row.source_reference,
                    generated_by=dist_row.generated_by,
                ),
            )
            uow.content.save_failure_distribution(dist)

        maint_key_to_id: dict[tuple[str, str], UUID] = {}
        for maint_row in preview.maintenance:
            interval = None
            if (
                maint_row.interval_value is not None
                and maint_row.interval_unit is not None
            ):
                interval = TimeValue(
                    value=maint_row.interval_value,
                    unit=maint_row.interval_unit,
                )
            fm_id = None
            if maint_row.failure_mode_name:
                fm_id = fm_key_to_id.get(
                    (maint_row.equipment_tag, maint_row.failure_mode_name)
                )
            task = MaintenanceTask(
                version_id=version_id,
                equipment_id=tag_to_id[maint_row.equipment_tag],
                failure_mode_id=fm_id,
                name=maint_row.name,
                task_type=maint_row.task_type,
                trigger=maint_row.trigger,
                interval=interval,
                cost=maint_row.cost,
            )
            uow.content.save_maintenance_task(task)
            maint_key_to_id[(maint_row.equipment_tag, maint_row.name)] = (
                task.id
            )
            if maint_row.duration_distribution is not None:
                duration = MaintenanceDistribution(
                    version_id=version_id,
                    maintenance_task_id=task.id,
                    distribution=parse_distribution(
                        maint_row.duration_distribution
                    ),
                    provenance=Provenance(
                        source_type=maint_row.duration_source_type
                        or SourceType.USER_DEFINED,
                        confidence=maint_row.duration_confidence
                        or Confidence.MEDIUM,
                    ),
                )
                uow.content.save_maintenance_distribution(duration)

        for effect_row in preview.maintenance_effects:
            task_id = maint_key_to_id.get(
                (effect_row.equipment_tag, effect_row.maintenance_name)
            )
            if task_id is None:
                continue
            fm_id = None
            if effect_row.failure_mode_name:
                fm_id = fm_key_to_id.get(
                    (effect_row.equipment_tag, effect_row.failure_mode_name)
                )
            effect = MaintenanceEffect(
                version_id=version_id,
                maintenance_task_id=task_id,
                effect_type=effect_row.effect_type,
                failure_mode_id=fm_id,
                parameter=effect_row.parameter,
            )
            uow.content.save_maintenance_effect(effect)

        for diag_row in preview.diagnostics:
            fm_id = fm_key_to_id.get(
                (diag_row.equipment_tag, diag_row.failure_mode_name)
            )
            if fm_id is None:
                continue
            diag = DiagnosticTask(
                version_id=version_id,
                equipment_id=tag_to_id[diag_row.equipment_tag],
                failure_mode_id=fm_id,
                name=diag_row.name,
                method=diag_row.method,
                interval=TimeValue(
                    value=diag_row.interval_value,
                    unit=diag_row.interval_unit,
                ),
                detection_probability=diag_row.detection_probability,
                false_positive_probability=(
                    diag_row.false_positive_probability
                ),
            )
            uow.content.save_diagnostic_task(diag)

        for res_row in preview.resources:
            resource = Resource(
                version_id=version_id,
                name=res_row.name,
                resource_type=res_row.resource_type,
                capacity=res_row.capacity,
                cost_per_hour=res_row.cost_per_hour,
            )
            uow.content.save_resource(resource)

        for spare_row in preview.spare_parts:
            lead = None
            if (
                spare_row.lead_time_value is not None
                and spare_row.lead_time_unit is not None
            ):
                lead = TimeValue(
                    value=spare_row.lead_time_value,
                    unit=spare_row.lead_time_unit,
                )
            spare = SparePart(
                version_id=version_id,
                name=spare_row.name,
                stock=spare_row.stock,
                lead_time=lead,
                unit_cost=spare_row.unit_cost,
            )
            uow.content.save_spare_part(spare)

        for prod_row in preview.production:
            if prod_row.kind == "function":
                if (
                    prod_row.product is None
                    or prod_row.nominal_rate_value is None
                    or prod_row.mass_unit is None
                    or prod_row.time_unit is None
                ):
                    continue
                function = ProductionFunction(
                    version_id=version_id,
                    product=prod_row.product,
                    nominal_rate=MassRate(
                        value=prod_row.nominal_rate_value,
                        mass_unit=prod_row.mass_unit,
                        time_unit=prod_row.time_unit,
                    ),
                )
                uow.content.save_production_function(function)
            elif prod_row.kind == "impact" and prod_row.equipment_tag:
                fm_id = None
                if prod_row.failure_mode_name:
                    fm_id = fm_key_to_id.get(
                        (
                            prod_row.equipment_tag,
                            prod_row.failure_mode_name,
                        )
                    )
                impact = ProductionImpact(
                    version_id=version_id,
                    equipment_id=tag_to_id[prod_row.equipment_tag],
                    failure_mode_id=fm_id,
                    loss_fraction=prod_row.loss_fraction or 0.0,
                )
                uow.content.save_production_impact(impact)

        return {
            "version_id": str(version_id),
            "imported": preview.summary()["counts"],
            "dataset_label": preview.dataset_label,
            "for_software_testing": preview.for_software_testing,
        }

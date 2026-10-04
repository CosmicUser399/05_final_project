"""УПП-100 demo plant builder (software testing only).

Package §67 mini types are expanded to ~50–60 tagged units. P-101
carries the PF-demo from Technical Spec §86.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.domain.equipment.entities import ConnectionType
from app.domain.equipment.entities import Criticality
from app.domain.equipment.entities import OperatingMode
from app.domain.maintenance.entities import MaintenanceEffectType
from app.domain.maintenance.entities import MaintenanceTaskType
from app.domain.maintenance.entities import MaintenanceTrigger
from app.domain.provenance import Confidence
from app.domain.provenance import SourceType
from app.domain.units import MassUnit
from app.domain.units import TimeUnit
from app.infrastructure.excel.importer import ComponentImportRow
from app.infrastructure.excel.importer import ConnectionImportRow
from app.infrastructure.excel.importer import DiagnosticImportRow
from app.infrastructure.excel.importer import EquipmentImportRow
from app.infrastructure.excel.importer import FailureDistributionImportRow
from app.infrastructure.excel.importer import FailureModeImportRow
from app.infrastructure.excel.importer import ImportPreview
from app.infrastructure.excel.importer import MaintenanceEffectImportRow
from app.infrastructure.excel.importer import MaintenanceImportRow
from app.infrastructure.excel.importer import ProductionImportRow
from app.infrastructure.excel.importer import ResourceImportRow
from app.infrastructure.excel.importer import SparePartImportRow

# Project root: backend/app/infrastructure/demo -> ../../../..
_SEED_DIR = Path(__file__).resolve().parents[4] / "scripts" / "seed" / "upp100"

DATASET_LABEL = "upp100-v1"
SYSTEM_NAME = "Установка производства полистирола - 100"
SYSTEM_DESCRIPTION = (
    "Типовая установка производства полистирола из стирола, "
    "мощность 100 тыс. тонн в год. Датасет для тестирования ПО, "
    "не для инженерной сертификации."
)

# Package §67 base types + plant expansion.
_TYPE_SPECS: list[dict[str, Any]] = [
    {
        "prefix": "P",
        "name": "Feed pump",
        "category": "Pump",
        "equipment_class": "centrifugal_pump",
        "count": 6,
        "criticality": Criticality.CRITICAL,
        "start": 101,
    },
    {
        "prefix": "R",
        "name": "Reactor",
        "category": "Reactor",
        "equipment_class": "reactor",
        "count": 4,
        "criticality": Criticality.CRITICAL,
        "start": 201,
    },
    {
        "prefix": "AG",
        "name": "Agitator",
        "category": "Agitator",
        "equipment_class": "agitator",
        "count": 4,
        "criticality": Criticality.HIGH,
        "start": 211,
    },
    {
        "prefix": "E",
        "name": "Heat exchanger",
        "category": "HeatExchanger",
        "equipment_class": "heat_exchanger",
        "count": 8,
        "criticality": Criticality.HIGH,
        "start": 301,
    },
    {
        "prefix": "C",
        "name": "Compressor",
        "category": "Compressor",
        "equipment_class": "compressor",
        "count": 4,
        "criticality": Criticality.CRITICAL,
        "start": 401,
    },
    {
        "prefix": "CW",
        "name": "Cooling system",
        "category": "Cooling",
        "equipment_class": "cooling_system",
        "count": 3,
        "criticality": Criticality.HIGH,
        "start": 501,
    },
    {
        "prefix": "FV",
        "name": "Control valve",
        "category": "Valve",
        "equipment_class": "control_valve",
        "count": 10,
        "criticality": Criticality.MEDIUM,
        "start": 601,
    },
    {
        "prefix": "T",
        "name": "Storage tank",
        "category": "Tank",
        "equipment_class": "storage_tank",
        "count": 6,
        "criticality": Criticality.MEDIUM,
        "start": 701,
    },
    {
        "prefix": "M",
        "name": "Electrical motor",
        "category": "Motor",
        "equipment_class": "electric_motor",
        "count": 8,
        "criticality": Criticality.HIGH,
        "start": 801,
    },
    {
        "prefix": "I",
        "name": "Instrumentation",
        "category": "Instrumentation",
        "equipment_class": "instrumentation",
        "count": 8,
        "criticality": Criticality.MEDIUM,
        "start": 901,
    },
]


def _weibull_json(shape: float, scale: float, unit: str) -> dict[str, Any]:
    return {
        "type": "WEIBULL",
        "shape": shape,
        "scale": scale,
        "unit": unit,
    }


def _constant_hours(hours: float) -> dict[str, Any]:
    return {"type": "CONSTANT", "value": hours, "unit": "HOURS"}


def build_upp100_preview() -> ImportPreview:
    """Build the in-memory УПП-100 import preview (~50+ units)."""
    preview = ImportPreview(
        system_name=SYSTEM_NAME,
        system_description=SYSTEM_DESCRIPTION,
        dataset_label=DATASET_LABEL,
        for_software_testing=True,
    )
    tags: list[str] = []

    for spec in _TYPE_SPECS:
        for offset in range(spec["count"]):
            number = spec["start"] + offset
            tag = f"{spec['prefix']}-{number}"
            tags.append(tag)
            preview.equipment.append(
                EquipmentImportRow(
                    tag=tag,
                    name=f"{spec['name']} {tag}",
                    description=(
                        f"Demo {spec['name'].lower()} for software testing"
                    ),
                    category=spec["category"],
                    equipment_class=spec["equipment_class"],
                    equipment_type=spec["name"],
                    location="УПП-100",
                    quantity=1,
                    criticality=spec["criticality"],
                    operating_mode=OperatingMode.CONTINUOUS,
                    is_repairable=True,
                )
            )

    # Spanning tree so model validation sees a connected topology.
    # Root = P-101; remaining units hang as DEPENDENCY children.
    root = "P-101"
    for tag in tags:
        if tag == root:
            continue
        preview.connections.append(
            ConnectionImportRow(
                from_tag=root,
                to_tag=tag,
                connection_type=ConnectionType.DEPENDENCY,
                description="demo spanning link",
            )
        )
    # A few typed process/utility links for graph realism.
    typed_links = [
        ("P-101", "R-201", ConnectionType.PROCESS),
        ("P-102", "R-201", ConnectionType.PROCESS),
        ("R-201", "E-301", ConnectionType.PROCESS),
        ("E-301", "T-701", ConnectionType.PROCESS),
        ("C-401", "R-201", ConnectionType.UTILITY),
        ("CW-501", "E-301", ConnectionType.UTILITY),
        ("M-801", "P-101", ConnectionType.ELECTRICAL),
        ("I-901", "P-101", ConnectionType.SIGNAL),
        ("FV-601", "P-101", ConnectionType.CONTROL),
        ("AG-211", "R-201", ConnectionType.DEPENDENCY),
    ]
    existing = {(c.from_tag, c.to_tag) for c in preview.connections}
    for from_tag, to_tag, ctype in typed_links:
        if (from_tag, to_tag) in existing:
            continue
        if from_tag in tags and to_tag in tags:
            preview.connections.append(
                ConnectionImportRow(
                    from_tag=from_tag,
                    to_tag=to_tag,
                    connection_type=ctype,
                    description="demo typed link",
                )
            )

    preview.components.append(
        ComponentImportRow(
            equipment_tag="P-101",
            name="Mechanical seal",
            description="PF-demo seal assembly",
            quantity=1,
        )
    )

    # Generic failure modes for all equipment.
    for tag in tags:
        fm_name = "Generic wear"
        preview.failure_modes.append(
            FailureModeImportRow(
                equipment_tag=tag,
                name=fm_name,
                description="Demo wear-out mode",
                is_detectable=False,
            )
        )
        preview.failure_distributions.append(
            FailureDistributionImportRow(
                equipment_tag=tag,
                failure_mode_name=fm_name,
                distribution=_weibull_json(1.5, 8000.0, "HOURS"),
                source_type=SourceType.ENGINEERING_ASSUMPTION,
                confidence=Confidence.LOW,
                source_reference=DATASET_LABEL,
                generated_by="upp100-seed",
            )
        )
        preview.maintenance.append(
            MaintenanceImportRow(
                equipment_tag=tag,
                name="Corrective repair",
                task_type=MaintenanceTaskType.CORRECTIVE,
                trigger=MaintenanceTrigger.ON_FAILURE,
                failure_mode_name=fm_name,
                duration_distribution=_constant_hours(4.0),
                duration_source_type=SourceType.ENGINEERING_ASSUMPTION,
                duration_confidence=Confidence.LOW,
            )
        )
        preview.maintenance_effects.append(
            MaintenanceEffectImportRow(
                equipment_tag=tag,
                maintenance_name="Corrective repair",
                effect_type=MaintenanceEffectType.RESTORE_AS_NEW,
                failure_mode_name=fm_name,
            )
        )
        preview.production.append(
            ProductionImportRow(
                kind="impact",
                equipment_tag=tag,
                failure_mode_name=fm_name,
                loss_fraction=0.05 if tag != "P-101" else 0.25,
            )
        )

    # --- PF-demo P-101 (Technical Spec §86) ---
    pf_name = "Mechanical seal degradation"
    preview.failure_modes.append(
        FailureModeImportRow(
            equipment_tag="P-101",
            name=pf_name,
            description="PF-demo: seal degradation with vibro monitoring",
            is_detectable=True,
            component_name="Mechanical seal",
            pf_value=14.0,
            pf_unit=TimeUnit.DAYS,
        )
    )
    preview.failure_distributions.append(
        FailureDistributionImportRow(
            equipment_tag="P-101",
            failure_mode_name=pf_name,
            distribution=_weibull_json(2.0, 2000.0, "HOURS"),
            source_type=SourceType.ENGINEERING_ASSUMPTION,
            confidence=Confidence.MEDIUM,
            source_reference="PF-demo P-101",
            generated_by="upp100-seed",
        )
    )
    preview.diagnostics.append(
        DiagnosticImportRow(
            equipment_tag="P-101",
            failure_mode_name=pf_name,
            name="Vibration/condition monitoring",
            method="vibration",
            interval_value=7.0,
            interval_unit=TimeUnit.DAYS,
            detection_probability=0.85,
            false_positive_probability=0.02,
        )
    )
    preview.maintenance.append(
        MaintenanceImportRow(
            equipment_tag="P-101",
            name="Seal replacement",
            task_type=MaintenanceTaskType.PREVENTIVE,
            trigger=MaintenanceTrigger.CONDITION_BASED,
            failure_mode_name=pf_name,
            duration_distribution=_constant_hours(1.0),
            duration_source_type=SourceType.ENGINEERING_ASSUMPTION,
            duration_confidence=Confidence.MEDIUM,
        )
    )
    preview.maintenance_effects.append(
        MaintenanceEffectImportRow(
            equipment_tag="P-101",
            maintenance_name="Seal replacement",
            effect_type=MaintenanceEffectType.RESTORE_AS_NEW,
            failure_mode_name=pf_name,
        )
    )
    preview.production.append(
        ProductionImportRow(
            kind="impact",
            equipment_tag="P-101",
            failure_mode_name=pf_name,
            loss_fraction=0.4,
        )
    )

    preview.resources.append(
        ResourceImportRow(
            name="Mechanical crew",
            resource_type="crew",
            capacity=2,
            cost_per_hour=80.0,
        )
    )
    preview.spare_parts.append(
        SparePartImportRow(
            name="Mechanical seal kit",
            stock=4,
            lead_time_value=14.0,
            lead_time_unit=TimeUnit.DAYS,
            unit_cost=1200.0,
        )
    )
    preview.production.insert(
        0,
        ProductionImportRow(
            kind="function",
            product="Polystyrene",
            nominal_rate_value=11.4,
            mass_unit=MassUnit.TONNES,
            time_unit=TimeUnit.HOURS,
        ),
    )
    return preview


def preview_to_seed_dict(preview: ImportPreview) -> dict[str, Any]:
    """Serialize preview to a versioned seed JSON structure."""
    return {
        "dataset_label": preview.dataset_label,
        "for_software_testing": True,
        "system": {
            "name": preview.system_name,
            "description": preview.system_description,
        },
        "equipment": [
            row.model_dump(mode="json") for row in preview.equipment
        ],
        "components": [
            row.model_dump(mode="json") for row in preview.components
        ],
        "connections": [
            row.model_dump(mode="json") for row in preview.connections
        ],
        "failure_modes": [
            row.model_dump(mode="json") for row in preview.failure_modes
        ],
        "failure_distributions": [
            row.model_dump(mode="json")
            for row in preview.failure_distributions
        ],
        "maintenance": [
            row.model_dump(mode="json") for row in preview.maintenance
        ],
        "maintenance_effects": [
            row.model_dump(mode="json") for row in preview.maintenance_effects
        ],
        "diagnostics": [
            row.model_dump(mode="json") for row in preview.diagnostics
        ],
        "resources": [
            row.model_dump(mode="json") for row in preview.resources
        ],
        "spare_parts": [
            row.model_dump(mode="json") for row in preview.spare_parts
        ],
        "production": [
            row.model_dump(mode="json") for row in preview.production
        ],
    }


def write_upp100_seed_file(path: Path | None = None) -> Path:
    """Write ``scripts/seed/upp100/manifest.json`` from the builder."""
    target = path or (_SEED_DIR / "manifest.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    preview = build_upp100_preview()
    payload = preview_to_seed_dict(preview)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    readme = target.parent / "README.md"
    readme.write_text(
        "# UPP-100 demo seed\n\n"
        "Synthetic polystyrene plant dataset for software testing.\n"
        "Not for engineering certification.\n\n"
        f"- Label: `{DATASET_LABEL}`\n"
        f"- Equipment count: {len(preview.equipment)}\n"
        "- PF-demo equipment: `P-101`\n"
        "  (Mechanical seal degradation, PF 14 d, vibro 7 d,\n"
        "  p=0.85, seal replacement 1 h)\n\n"
        "Load via `POST /api/v1/demo/upp100` or regenerate with\n"
        "`make seed-upp100`.\n",
        encoding="utf-8",
    )
    return target


def load_upp100_seed_file(path: Path | None = None) -> ImportPreview:
    """Load seed JSON if present; otherwise build in memory."""
    target = path or (_SEED_DIR / "manifest.json")
    if not target.is_file():
        return build_upp100_preview()
    data = json.loads(target.read_text(encoding="utf-8"))
    preview = ImportPreview(
        system_name=data["system"]["name"],
        system_description=data["system"].get("description"),
        dataset_label=data.get("dataset_label", DATASET_LABEL),
        for_software_testing=bool(data.get("for_software_testing", True)),
        equipment=[
            EquipmentImportRow.model_validate(row)
            for row in data.get("equipment", [])
        ],
        components=[
            ComponentImportRow.model_validate(row)
            for row in data.get("components", [])
        ],
        connections=[
            ConnectionImportRow.model_validate(row)
            for row in data.get("connections", [])
        ],
        failure_modes=[
            FailureModeImportRow.model_validate(row)
            for row in data.get("failure_modes", [])
        ],
        failure_distributions=[
            FailureDistributionImportRow.model_validate(row)
            for row in data.get("failure_distributions", [])
        ],
        maintenance=[
            MaintenanceImportRow.model_validate(row)
            for row in data.get("maintenance", [])
        ],
        maintenance_effects=[
            MaintenanceEffectImportRow.model_validate(row)
            for row in data.get("maintenance_effects", [])
        ],
        diagnostics=[
            DiagnosticImportRow.model_validate(row)
            for row in data.get("diagnostics", [])
        ],
        resources=[
            ResourceImportRow.model_validate(row)
            for row in data.get("resources", [])
        ],
        spare_parts=[
            SparePartImportRow.model_validate(row)
            for row in data.get("spare_parts", [])
        ],
        production=[
            ProductionImportRow.model_validate(row)
            for row in data.get("production", [])
        ],
    )
    return preview

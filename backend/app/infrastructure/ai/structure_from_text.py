"""Heuristic plant structure from free-text (mock / offline path)."""

from __future__ import annotations

import re
from typing import Any

# (kind, tag_prefix, name, category, equipment_class, criticality)
_KIND_SPECS: dict[str, tuple[str, str, str, str, str]] = {
    "pump": ("P", "Pump", "ROTATING", "Pump", "CRITICAL"),
    "motor": ("M", "Electric motor", "ELECTRICAL", "Motor", "HIGH"),
    "pipeline": ("PL", "Pipeline", "STATIC", "Pipeline", "HIGH"),
    "cable": ("CBL", "Cable", "ELECTRICAL", "Cable", "MEDIUM"),
    "tank": ("T", "Tank", "STATIC", "Vessel", "CRITICAL"),
    "compressor": ("C", "Compressor", "ROTATING", "Compressor", "HIGH"),
    "reactor": ("R", "Reactor", "STATIC", "Vessel", "CRITICAL"),
}

_TOKEN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "pipeline",
        re.compile(
            r"трубопровод(?:а|у|ом|е)?(?:-|\s*)?(\d+)?|"
            r"pipeline(?:-|\s*)?(\d+)?|"
            r"\bpipe(?:-|\s*)?(\d+)?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "tank",
        re.compile(
            r"емкост(?:ь|и|ей|ям|ями|ях)(?:-|\s*)?(\d+)?|"
            r"tank(?:-|\s*)?(\d+)?|"
            r"vessel(?:-|\s*)?(\d+)?",
            re.IGNORECASE,
        ),
    ),
    (
        "motor",
        re.compile(
            r"электродвигател(?:ь|я|ю|ем|е)|"
            r"электромотор(?:а|у|ом|е)?|"
            r"electric\s+motor|\bmotor\b",
            re.IGNORECASE,
        ),
    ),
    (
        "pump",
        re.compile(r"насос(?:а|у|ом|е)?|\bpump\b", re.IGNORECASE),
    ),
    (
        "cable",
        re.compile(r"кабел(?:ь|я|ю|ем|е|ей)|\bcable\b", re.IGNORECASE),
    ),
    (
        "compressor",
        re.compile(
            r"компрессор(?:а|у|ом|е)?|\bcompressor\b",
            re.IGNORECASE,
        ),
    ),
    (
        "reactor",
        re.compile(r"реактор(?:а|у|ом|е)?|\breactor\b", re.IGNORECASE),
    ),
]


def build_proposal_from_description(description: str) -> dict[str, Any]:
    """Return an EquipmentProposalPayload-shaped dict from free text."""
    text = description.strip() or "Unknown plant"
    brief = parse_brief(text)
    if "полистирол" in text.lower() or "polystyrene" in text.lower():
        return _polystyrene_template(brief)
    units = _extract_units(text)
    if not units:
        return _polystyrene_template(brief)
    return _proposal_from_units(brief, units)


def parse_brief(description: str) -> dict[str, Any]:
    """Extract a lightweight plant brief from free text."""
    text = description.strip() or "Unknown plant"
    capacity_value: float | None = None
    capacity_unit: str | None = None
    capacity_match = re.search(
        r"(\d+(?:[.,]\d+)?)\s*(тыс(?:яч)?\.?\s*)?"
        r"(тонн|t\b|kt\b)",
        text,
        flags=re.IGNORECASE,
    )
    if capacity_match:
        raw = capacity_match.group(1).replace(",", ".")
        capacity_value = float(raw)
        if capacity_match.group(2):
            capacity_value *= 1000.0
        lowered = text.lower()
        if re.search(r"\b(день|сутки|day|d)\b", lowered):
            capacity_unit = "t/day"
        elif re.search(r"\b(час|hour|h)\b", lowered):
            capacity_unit = "t/hour"
        else:
            capacity_unit = "t/year"
    plant_type = "process_plant"
    lowered = text.lower()
    if "полистирол" in lowered or "polystyrene" in lowered:
        plant_type = "polystyrene_plant"
    elif "перекач" in lowered or "pump" in lowered or "бензин" in lowered:
        plant_type = "pumping_system"
    return {
        "plant_type": plant_type,
        "capacity_value": capacity_value,
        "capacity_unit": capacity_unit,
        "summary": text[:2000],
        "assumptions": [
            "Synthetic structure for review only",
            "Reliability parameters remain UNKNOWN",
        ],
    }


def _extract_units(text: str) -> list[dict[str, Any]]:
    found: list[tuple[int, str, str | None]] = []
    for kind, pattern in _TOKEN_PATTERNS:
        for match in pattern.finditer(text):
            suffix: str | None = None
            for group in match.groups():
                if group:
                    suffix = group
                    break
            found.append((match.start(), kind, suffix))
    found.sort(key=lambda row: row[0])
    units: list[dict[str, Any]] = []
    seen: set[str] = set()
    counters: dict[str, int] = {}
    for _, kind, suffix in found:
        dedupe_key = f"{kind}:{suffix}" if suffix else f"{kind}:bare"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        counters[kind] = counters.get(kind, 0) + 1
        prefix, base_name, category, eq_class, crit = _KIND_SPECS[kind]
        index = int(suffix) if suffix else counters[kind]
        if kind in {"pipeline", "tank"}:
            tag = f"{prefix}-{index}"
            name = f"{base_name}-{index}"
        else:
            tag = f"{prefix}-{100 + index}"
            name = base_name
        units.append(
            {
                "kind": kind,
                "tag": tag,
                "name": name,
                "category": category,
                "equipment_class": eq_class,
                "criticality": crit,
            }
        )
    return units


def _proposal_from_units(
    brief: dict[str, Any],
    units: list[dict[str, Any]],
) -> dict[str, Any]:
    root = {
        "tag": "SYS-01",
        "name": "System root",
        "category": "PROCESS",
        "criticality": "CRITICAL",
        "quantity": 1,
        "is_repairable": False,
    }
    equipment = [root]
    for unit in units:
        equipment.append(
            {
                "tag": unit["tag"],
                "name": unit["name"],
                "parent_tag": "SYS-01",
                "category": unit["category"],
                "equipment_class": unit["equipment_class"],
                "criticality": unit["criticality"],
                "quantity": 1,
                "is_repairable": True,
            }
        )
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for unit in units:
        by_kind.setdefault(unit["kind"], []).append(unit)

    connections = _process_connections(by_kind, units)
    components: list[dict[str, Any]] = []
    for pump in by_kind.get("pump", []):
        components.append(
            {
                "equipment_tag": pump["tag"],
                "name": "Seal",
                "quantity": 1,
            }
        )
    failure_modes: list[dict[str, Any]] = []
    maintenance_tasks: list[dict[str, Any]] = []
    for unit in units:
        failure_modes.append(
            {
                "equipment_tag": unit["tag"],
                "name": f"Generic failure ({unit['name']})",
                "is_detectable": True,
                "value_status": "UNKNOWN",
            }
        )
        maintenance_tasks.append(
            {
                "equipment_tag": unit["tag"],
                "name": f"Corrective repair ({unit['name']})",
                "task_type": "CORRECTIVE",
                "value_status": "UNKNOWN",
            }
        )
    return {
        "brief": brief,
        "equipment": equipment,
        "components": components,
        "connections": connections,
        "failure_modes": failure_modes,
        "maintenance_tasks": maintenance_tasks,
    }


def _process_connections(
    by_kind: dict[str, list[dict[str, Any]]],
    units: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    connections: list[dict[str, Any]] = []
    tanks = sorted(
        by_kind.get("tank", []),
        key=lambda row: row["tag"],
    )
    pipes = sorted(
        by_kind.get("pipeline", []),
        key=lambda row: row["tag"],
    )
    pumps = by_kind.get("pump", [])
    motors = by_kind.get("motor", [])
    cables = by_kind.get("cable", [])

    if tanks and pipes and pumps:
        pump_tag = pumps[0]["tag"]
        # Tank-1 -> Pipe-1 -> Pump -> Pipe-2 -> Tank-2 (when present).
        if pipes:
            connections.append(
                {
                    "from_tag": tanks[0]["tag"],
                    "to_tag": pipes[0]["tag"],
                    "connection_type": "PROCESS",
                }
            )
            connections.append(
                {
                    "from_tag": pipes[0]["tag"],
                    "to_tag": pump_tag,
                    "connection_type": "PROCESS",
                }
            )
        if len(pipes) >= 2:
            connections.append(
                {
                    "from_tag": pump_tag,
                    "to_tag": pipes[1]["tag"],
                    "connection_type": "PROCESS",
                }
            )
            if len(tanks) >= 2:
                connections.append(
                    {
                        "from_tag": pipes[1]["tag"],
                        "to_tag": tanks[1]["tag"],
                        "connection_type": "PROCESS",
                    }
                )
        elif len(tanks) >= 2:
            connections.append(
                {
                    "from_tag": pump_tag,
                    "to_tag": tanks[1]["tag"],
                    "connection_type": "PROCESS",
                }
            )
    else:
        # Fallback: chain units in mention order.
        tags = [unit["tag"] for unit in units]
        for left, right in zip(tags, tags[1:], strict=False):
            connections.append(
                {
                    "from_tag": left,
                    "to_tag": right,
                    "connection_type": "PROCESS",
                }
            )

    if motors and pumps:
        connections.append(
            {
                "from_tag": motors[0]["tag"],
                "to_tag": pumps[0]["tag"],
                "connection_type": "ENERGY",
            }
        )
    if cables and motors:
        connections.append(
            {
                "from_tag": cables[0]["tag"],
                "to_tag": motors[0]["tag"],
                "connection_type": "ELECTRICAL",
            }
        )
    elif cables and pumps:
        connections.append(
            {
                "from_tag": cables[0]["tag"],
                "to_tag": pumps[0]["tag"],
                "connection_type": "ELECTRICAL",
            }
        )
    return connections


def _polystyrene_template(brief: dict[str, Any]) -> dict[str, Any]:
    """Keep the classic demo layout used by integration tests."""
    return {
        "brief": brief,
        "equipment": [
            {
                "tag": "SYS-01",
                "name": "Plant root",
                "category": "PROCESS",
                "criticality": "CRITICAL",
                "quantity": 1,
            },
            {
                "tag": "P-101",
                "name": "Feed pump",
                "parent_tag": "SYS-01",
                "category": "ROTATING",
                "equipment_class": "Pump",
                "equipment_type": "Centrifugal",
                "criticality": "HIGH",
                "quantity": 1,
            },
            {
                "tag": "E-201",
                "name": "Reactor",
                "parent_tag": "SYS-01",
                "category": "STATIC",
                "equipment_class": "Vessel",
                "criticality": "CRITICAL",
                "quantity": 1,
            },
            {
                "tag": "C-301",
                "name": "Compressor",
                "parent_tag": "SYS-01",
                "category": "ROTATING",
                "equipment_class": "Compressor",
                "criticality": "HIGH",
                "quantity": 1,
            },
        ],
        "components": [
            {
                "equipment_tag": "P-101",
                "name": "Seal",
                "quantity": 1,
            }
        ],
        "connections": [
            {
                "from_tag": "P-101",
                "to_tag": "E-201",
                "connection_type": "PROCESS",
            },
            {
                "from_tag": "E-201",
                "to_tag": "C-301",
                "connection_type": "PROCESS",
            },
        ],
        "failure_modes": [
            {
                "equipment_tag": "P-101",
                "name": "Seal leakage",
                "is_detectable": True,
                "value_status": "UNKNOWN",
            },
            {
                "equipment_tag": "E-201",
                "name": "Generic failure (Reactor)",
                "is_detectable": True,
                "value_status": "UNKNOWN",
            },
            {
                "equipment_tag": "C-301",
                "name": "Generic failure (Compressor)",
                "is_detectable": True,
                "value_status": "UNKNOWN",
            },
            {
                "equipment_tag": "SYS-01",
                "name": "Generic failure (Plant root)",
                "is_detectable": True,
                "value_status": "UNKNOWN",
            },
        ],
        "maintenance_tasks": [
            {
                "equipment_tag": "P-101",
                "name": "Corrective repair (Feed pump)",
                "task_type": "CORRECTIVE",
                "value_status": "UNKNOWN",
            },
            {
                "equipment_tag": "E-201",
                "name": "Corrective repair (Reactor)",
                "task_type": "CORRECTIVE",
                "value_status": "UNKNOWN",
            },
            {
                "equipment_tag": "C-301",
                "name": "Corrective repair (Compressor)",
                "task_type": "CORRECTIVE",
                "value_status": "UNKNOWN",
            },
            {
                "equipment_tag": "SYS-01",
                "name": "Corrective repair (Plant root)",
                "task_type": "CORRECTIVE",
                "value_status": "UNKNOWN",
            },
        ],
    }

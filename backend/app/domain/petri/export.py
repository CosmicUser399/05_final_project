"""Export Petri subnets to Petri-Pilot JSON (opaque ids only)."""

from __future__ import annotations

import json
from typing import Any

from app.domain.petri.entities import PetriSubnet


def subnet_to_pilot_dict(subnet: PetriSubnet) -> dict[str, Any]:
    """Return a Pilot-ready dict without source metadata."""
    places: list[dict[str, Any]] = []
    for place in subnet.places:
        row: dict[str, Any] = {"id": place.id}
        if place.initial:
            row["initial"] = place.initial
        if place.capacity is not None:
            row["capacity"] = place.capacity
        places.append(row)
    transitions = [{"id": t.id, "name": t.id} for t in subnet.transitions]
    arcs: list[dict[str, Any]] = []
    for arc in subnet.arcs:
        row = {
            "from": arc.source,
            "to": arc.target,
            "weight": arc.weight,
        }
        if arc.arc_type:
            row["type"] = arc.arc_type
        arcs.append(row)
    return {
        "name": subnet.name,
        "places": places,
        "transitions": transitions,
        "arcs": arcs,
    }


def to_pilot_json(subnet: PetriSubnet) -> str:
    """Serialize a subnet as a JSON string for Petri-Pilot tools."""
    return json.dumps(
        subnet_to_pilot_dict(subnet),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

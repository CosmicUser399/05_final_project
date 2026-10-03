"""Domain types for derived Petri models.

Elements carry ``source_entity_*`` metadata locally. Opaque ids are
what leave the process toward Petri-Pilot.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class PetriElementKind(StrEnum):
    """Kind of Petri net element."""

    PLACE = "place"
    TRANSITION = "transition"
    ARC = "arc"


class PlaceRole(StrEnum):
    """Semantic role of a place in a reliability subnet."""

    UP = "UP"
    POTENTIAL_FAILURE = "POTENTIAL_FAILURE"
    FAILED = "FAILED"
    MAINTENANCE = "MAINTENANCE"
    EQUIPMENT_UP = "EQUIPMENT_UP"
    EQUIPMENT_DOWN = "EQUIPMENT_DOWN"


class TransitionRole(StrEnum):
    """Semantic role of a transition (used for RAM conformance)."""

    TO_PF = "TO_PF"
    DETECT = "DETECT"
    MISS = "MISS"
    FAIL = "FAIL"
    CM_START = "CM_START"
    CM_DONE = "CM_DONE"
    PM_START = "PM_START"
    PM_DONE = "PM_DONE"
    EQ_FAIL = "EQ_FAIL"
    EQ_REPAIR = "EQ_REPAIR"


class SourceMapping(BaseModel):
    """Local map entry: opaque id -> domain source."""

    model_config = ConfigDict(frozen=True)

    kind: PetriElementKind
    role: str
    source_entity_type: str | None = None
    source_entity_id: str | None = None
    equipment_id: str | None = None
    failure_mode_id: str | None = None
    subnet_key: str | None = None


class PetriPlace(BaseModel):
    """One place with opaque id and optional source link."""

    model_config = ConfigDict(frozen=True)

    id: str
    role: PlaceRole
    initial: int = 0
    capacity: int | None = None
    source_entity_type: str | None = None
    source_entity_id: str | None = None


class PetriTransition(BaseModel):
    """One transition with opaque id and optional source link."""

    model_config = ConfigDict(frozen=True)

    id: str
    role: TransitionRole
    source_entity_type: str | None = None
    source_entity_id: str | None = None


class PetriArc(BaseModel):
    """Directed arc between place and transition (or reverse)."""

    model_config = ConfigDict(frozen=True)

    id: str
    source: str
    target: str
    weight: int = 1
    arc_type: str | None = None


class PetriSubnet(BaseModel):
    """One analysable subnet (per failure mode or system)."""

    model_config = ConfigDict(frozen=True)

    key: str
    name: str
    case_id: str
    kind: str
    places: tuple[PetriPlace, ...] = ()
    transitions: tuple[PetriTransition, ...] = ()
    arcs: tuple[PetriArc, ...] = ()


class PetriModel(BaseModel):
    """Derived Petri model for a compiled reliability snapshot."""

    model_config = ConfigDict(frozen=True)

    version_id: UUID
    reliability_model_id: UUID | None = None
    reliability_model_hash: str
    schema_version: int = 1
    subnets: tuple[PetriSubnet, ...] = ()
    id_map: dict[str, SourceMapping] = Field(default_factory=dict)

    def subnet(self, key: str) -> PetriSubnet | None:
        """Return a subnet by key, or None."""
        for item in self.subnets:
            if item.key == key:
                return item
        return None

    def transition_by_role(
        self,
        subnet_key: str,
        role: TransitionRole,
    ) -> PetriTransition | None:
        """Return the transition with the given role in a subnet."""
        net = self.subnet(subnet_key)
        if net is None:
            return None
        for item in net.transitions:
            if item.role is role:
                return item
        return None

    def definition_dict(self) -> dict[str, Any]:
        """Serialize for persistence (includes local id_map)."""
        return self.model_dump(mode="json")

"""Equipment, components, connections and taxonomies."""

from enum import StrEnum
from uuid import UUID

from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from app.domain.base import Entity
from app.domain.base import VersionedEntity


class TaxonomyKind(StrEnum):
    """Classification tree family."""

    BUSINESS = "BUSINESS"
    ISO_14224 = "ISO_14224"


class OperatingMode(StrEnum):
    """How the equipment is used in the process."""

    CONTINUOUS = "CONTINUOUS"
    INTERMITTENT = "INTERMITTENT"
    STANDBY = "STANDBY"


class StandbyMode(StrEnum):
    """Redundancy standby type."""

    NONE = "NONE"
    COLD = "COLD"
    WARM = "WARM"
    HOT = "HOT"


class Criticality(StrEnum):
    """Criticality class of equipment."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ConnectionType(StrEnum):
    """Kind of link between two pieces of equipment."""

    PROCESS = "PROCESS"
    MATERIAL = "MATERIAL"
    ENERGY = "ENERGY"
    ELECTRICAL = "ELECTRICAL"
    CONTROL = "CONTROL"
    SIGNAL = "SIGNAL"
    UTILITY = "UTILITY"
    DEPENDENCY = "DEPENDENCY"


def _strip_required(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


class Taxonomy(Entity):
    """A classification tree (business or ISO 14224)."""

    name: str = Field(min_length=1, max_length=200)
    kind: TaxonomyKind
    version_label: str | None = Field(default=None, max_length=100)


class TaxonomyNode(Entity):
    """A node of a taxonomy; ``code`` comes from the source."""

    taxonomy_id: UUID
    parent_id: UUID | None = None
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def _no_self_parent(self) -> "TaxonomyNode":
        if self.parent_id == self.id:
            raise ValueError("node cannot be its own parent")
        return self


class Equipment(VersionedEntity):
    """A piece of equipment of a system version."""

    tag: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    parent_id: UUID | None = None
    taxonomy_node_id: UUID | None = None
    category: str | None = Field(default=None, max_length=100)
    equipment_class: str | None = Field(default=None, max_length=100)
    equipment_type: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    quantity: int = Field(default=1, ge=1, le=10_000)
    criticality: Criticality = Criticality.MEDIUM
    operating_mode: OperatingMode = OperatingMode.CONTINUOUS
    standby_mode: StandbyMode = StandbyMode.NONE
    is_repairable: bool = True

    @field_validator("tag", "name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        return _strip_required(value)

    @model_validator(mode="after")
    def _check_references(self) -> "Equipment":
        if self.parent_id == self.id:
            raise ValueError("equipment cannot be its own parent")
        return self


class EquipmentComponent(VersionedEntity):
    """A component (part) of a piece of equipment."""

    equipment_id: UUID
    tag: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    quantity: int = Field(default=1, ge=1, le=10_000)

    @field_validator("name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        return _strip_required(value)


class EquipmentConnection(VersionedEntity):
    """A directed link ``source -> target`` between equipment."""

    source_id: UUID
    target_id: UUID
    connection_type: ConnectionType = ConnectionType.PROCESS
    description: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def _no_self_loop(self) -> "EquipmentConnection":
        if self.source_id == self.target_id:
            raise ValueError("connection must link different equipment")
        return self

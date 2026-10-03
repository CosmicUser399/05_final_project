"""Failure modes, failure distributions and reliability structures."""

from enum import StrEnum
from uuid import UUID

from pydantic import Field
from pydantic import model_validator

from app.domain.base import VersionedEntity
from app.domain.provenance import Provenance
from app.domain.reliability.distributions import DistributionSpec
from app.domain.reliability.pf import PFInterval


class FailureMode(VersionedEntity):
    """A way a piece of equipment (or component) can fail.

    The PF interval is an embedded value object. It is required for a
    detectable mode; this is checked by domain validation, so that a
    DRAFT can be edited step by step.
    """

    equipment_id: UUID
    component_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    is_detectable: bool = False
    pf_interval: PFInterval | None = None


class FailureDistribution(VersionedEntity):
    """Time-to-failure law of a failure mode, with provenance."""

    failure_mode_id: UUID
    distribution: DistributionSpec
    provenance: Provenance


class StructureType(StrEnum):
    """Reliability block structure type."""

    SERIES = "SERIES"
    PARALLEL = "PARALLEL"
    K_OF_N = "K_OF_N"
    STANDBY = "STANDBY"


class ReliabilityStructure(VersionedEntity):
    """A node of the redundancy tree (``Member`` rows are its leaves).

    ``k`` is the number of members that must work for ``K_OF_N``.
    """

    name: str = Field(min_length=1, max_length=200)
    structure_type: StructureType
    k: int | None = Field(default=None, ge=1)
    parent_structure_id: UUID | None = None

    @model_validator(mode="after")
    def _check_k(self) -> "ReliabilityStructure":
        if self.structure_type is StructureType.K_OF_N:
            if self.k is None:
                raise ValueError("k is required for K_OF_N")
        elif self.k is not None:
            raise ValueError("k is only allowed for K_OF_N")
        if self.parent_structure_id == self.id:
            raise ValueError("structure cannot be its own parent")
        return self


class ReliabilityStructureMember(VersionedEntity):
    """A member: either equipment or a nested structure.

    ``position`` orders members; for ``STANDBY`` position 0 is the
    primary unit.
    """

    structure_id: UUID
    equipment_id: UUID | None = None
    child_structure_id: UUID | None = None
    position: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _exactly_one_target(self) -> "ReliabilityStructureMember":
        if (self.equipment_id is None) == (self.child_structure_id is None):
            raise ValueError(
                "exactly one of equipment_id and child_structure_id "
                "must be set"
            )
        if self.child_structure_id == self.structure_id:
            raise ValueError("structure cannot contain itself")
        return self

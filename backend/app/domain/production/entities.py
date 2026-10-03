"""Production function and production impact of failures."""

from uuid import UUID

from pydantic import Field

from app.domain.base import VersionedEntity
from app.domain.units import MassRate


class ProductionFunction(VersionedEntity):
    """Nominal output of the system version."""

    product: str = Field(min_length=1, max_length=200)
    nominal_rate: MassRate


class ProductionImpact(VersionedEntity):
    """Share of nominal output lost while equipment is unavailable.

    ``loss_fraction`` is in [0, 1]; 1 means complete production stop.
    ``failure_mode_id`` narrows the impact to one failure mode.
    """

    equipment_id: UUID
    failure_mode_id: UUID | None = None
    loss_fraction: float = Field(ge=0.0, le=1.0)

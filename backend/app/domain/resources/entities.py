"""Maintenance resources and spare parts."""

from uuid import UUID

from pydantic import Field

from app.domain.base import VersionedEntity
from app.domain.units import TimeValue


class Resource(VersionedEntity):
    """A crew, tool or other limited maintenance resource."""

    name: str = Field(min_length=1, max_length=200)
    resource_type: str | None = Field(default=None, max_length=100)
    capacity: int = Field(default=1, ge=1, le=10_000)
    cost_per_hour: float | None = Field(
        default=None, ge=0, allow_inf_nan=False
    )


class SparePart(VersionedEntity):
    """A spare part with stock and replenishment lead time."""

    name: str = Field(min_length=1, max_length=200)
    stock: int = Field(default=0, ge=0)
    lead_time: TimeValue | None = None
    unit_cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class ResourceRequirement(VersionedEntity):
    """Resource units needed by a maintenance task."""

    maintenance_task_id: UUID
    resource_id: UUID
    quantity: int = Field(default=1, ge=1)


class SparePartRequirement(VersionedEntity):
    """Spare part units consumed by a maintenance task."""

    maintenance_task_id: UUID
    spare_part_id: UUID
    quantity: int = Field(default=1, ge=1)

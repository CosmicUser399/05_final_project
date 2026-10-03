"""Simulation configuration value object."""

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

from app.domain.units import TimeUnit
from app.domain.units import UnitConverter


class SimulationConfiguration(BaseModel):
    """Parameters of a RAM simulation request.

    Times may be given in any supported unit; the engine converts them
    to minutes via :meth:`horizon_minutes` / :meth:`warmup_minutes`.
    """

    model_config = ConfigDict(frozen=True)

    horizon: float = Field(gt=0, allow_inf_nan=False)
    horizon_unit: TimeUnit = TimeUnit.HOURS
    number_of_runs: int = Field(default=1, ge=1)
    random_seed: int = 42
    warmup_period: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    warmup_unit: TimeUnit = TimeUnit.HOURS
    confidence_level: float = Field(default=0.95, gt=0, lt=1)
    collect_event_log: bool = True
    collect_equipment_metrics: bool = True
    collect_resource_consumption: bool = True
    collect_production_loss: bool = True
    parallel_runs: int = Field(default=1, ge=1)
    event_log_limit: int | None = Field(default=None, ge=1)
    run_id: int = Field(default=0, ge=0)

    @field_validator("horizon")
    @classmethod
    def _finite_horizon(cls, value: float) -> float:
        if value != value:  # NaN
            raise ValueError("horizon must be finite")
        return value

    def horizon_minutes(self) -> float:
        """Return the simulation horizon in minutes."""
        return UnitConverter.to_minutes(self.horizon, self.horizon_unit)

    def warmup_minutes(self) -> float:
        """Return the warm-up period in minutes."""
        return UnitConverter.to_minutes(self.warmup_period, self.warmup_unit)

    def configuration_hash_payload(self) -> dict[str, object]:
        """Return a stable dict for hashing (P5 fingerprint)."""
        return self.model_dump(mode="json")

"""P-F interval value object and the ``T_pf = T_f - PF`` rule.

PF is the lead time between a detectable potential failure and the
functional failure.
"""

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.domain.units import TimeUnit
from app.domain.units import TimeValue
from app.domain.units import UnitConverter


class PFInterval(BaseModel):
    """PF interval stored as ``(value, unit)``; the value is > 0."""

    model_config = ConfigDict(frozen=True)

    value: float = Field(gt=0, allow_inf_nan=False)
    unit: TimeUnit

    def to_minutes(self) -> float:
        """Return the interval in canonical minutes."""
        return UnitConverter.to_minutes(self.value, self.unit)

    def as_time_value(self) -> TimeValue:
        """Return the interval as a ``TimeValue``."""
        return TimeValue(value=self.value, unit=self.unit)


def potential_failure_time(
    failure_time: float, pf_interval: float
) -> float | None:
    """Return ``T_pf = T_f - PF`` or ``None`` if it is negative.

    Both arguments must be in the same unit. A negative ``T_pf`` means
    the potential failure would have started before the time origin,
    so it is not modelled.
    """
    onset = failure_time - pf_interval
    if onset < 0:
        return None
    return onset

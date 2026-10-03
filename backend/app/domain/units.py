"""Units of measurement and the single ``UnitConverter``.

Canonical units: time - minutes, mass - kg, energy - MJ, power - kW.
Calendar conventions: month = 30.4375 days, year = 365.25 days
(see ``docs/domain/units.md``).
"""

import math
from enum import StrEnum
from typing import Final

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.domain.errors import UnitError

MINUTES_PER_HOUR: Final[float] = 60.0
HOURS_PER_DAY: Final[float] = 24.0
DAYS_PER_MONTH: Final[float] = 30.4375
DAYS_PER_YEAR: Final[float] = 365.25
MINUTES_PER_DAY: Final[float] = MINUTES_PER_HOUR * HOURS_PER_DAY
MINUTES_PER_MONTH: Final[float] = MINUTES_PER_DAY * DAYS_PER_MONTH
MINUTES_PER_YEAR: Final[float] = MINUTES_PER_DAY * DAYS_PER_YEAR


class TimeUnit(StrEnum):
    """Supported time units."""

    MINUTES = "MINUTES"
    HOURS = "HOURS"
    DAYS = "DAYS"
    MONTHS = "MONTHS"
    YEARS = "YEARS"


class MassUnit(StrEnum):
    """Supported mass units."""

    KG = "KG"
    TONNES = "TONNES"


class EnergyUnit(StrEnum):
    """Supported energy units."""

    MJ = "MJ"
    GJ = "GJ"
    KWH = "KWH"


class PowerUnit(StrEnum):
    """Supported power units."""

    KW = "KW"
    MW = "MW"


_TIME_TO_MINUTES: Final[dict[TimeUnit, float]] = {
    TimeUnit.MINUTES: 1.0,
    TimeUnit.HOURS: MINUTES_PER_HOUR,
    TimeUnit.DAYS: MINUTES_PER_DAY,
    TimeUnit.MONTHS: MINUTES_PER_MONTH,
    TimeUnit.YEARS: MINUTES_PER_YEAR,
}
_MASS_TO_KG: Final[dict[MassUnit, float]] = {
    MassUnit.KG: 1.0,
    MassUnit.TONNES: 1000.0,
}
_ENERGY_TO_MJ: Final[dict[EnergyUnit, float]] = {
    EnergyUnit.MJ: 1.0,
    EnergyUnit.GJ: 1000.0,
    EnergyUnit.KWH: 3.6,
}
_POWER_TO_KW: Final[dict[PowerUnit, float]] = {
    PowerUnit.KW: 1.0,
    PowerUnit.MW: 1000.0,
}


def _check_value(value: float, *, name: str = "value") -> float:
    """Reject NaN, infinity and negative numbers."""
    if not math.isfinite(value):
        raise UnitError(f"{name} must be finite, got {value!r}")
    if value < 0:
        raise UnitError(f"{name} must be >= 0, got {value!r}")
    return value


class UnitConverter:
    """The only place where unit conversion is performed."""

    @staticmethod
    def minutes_per(unit: TimeUnit) -> float:
        """Return the number of minutes in one ``unit``."""
        return _TIME_TO_MINUTES[unit]

    @staticmethod
    def convert_time(
        value: float, source: TimeUnit, target: TimeUnit
    ) -> float:
        """Convert a time value between time units."""
        _check_value(value)
        if source is target:
            return value
        return value * _TIME_TO_MINUTES[source] / _TIME_TO_MINUTES[target]

    @classmethod
    def to_minutes(cls, value: float, unit: TimeUnit) -> float:
        """Convert a time value to canonical minutes."""
        return cls.convert_time(value, unit, TimeUnit.MINUTES)

    @classmethod
    def from_minutes(cls, minutes: float, unit: TimeUnit) -> float:
        """Convert canonical minutes to ``unit``."""
        return cls.convert_time(minutes, TimeUnit.MINUTES, unit)

    @staticmethod
    def convert_mass(
        value: float, source: MassUnit, target: MassUnit
    ) -> float:
        """Convert a mass value between mass units."""
        _check_value(value)
        return value * _MASS_TO_KG[source] / _MASS_TO_KG[target]

    @staticmethod
    def convert_energy(
        value: float, source: EnergyUnit, target: EnergyUnit
    ) -> float:
        """Convert an energy value between energy units."""
        _check_value(value)
        return value * _ENERGY_TO_MJ[source] / _ENERGY_TO_MJ[target]

    @staticmethod
    def convert_power(
        value: float, source: PowerUnit, target: PowerUnit
    ) -> float:
        """Convert a power value between power units."""
        _check_value(value)
        return value * _POWER_TO_KW[source] / _POWER_TO_KW[target]


class TimeValue(BaseModel):
    """A non-negative duration stored as ``(value, unit)``."""

    model_config = ConfigDict(frozen=True)

    value: float = Field(ge=0, allow_inf_nan=False)
    unit: TimeUnit

    def to_minutes(self) -> float:
        """Return the duration in canonical minutes."""
        return UnitConverter.to_minutes(self.value, self.unit)

    def to_unit(self, unit: TimeUnit) -> "TimeValue":
        """Return an equivalent value expressed in ``unit``."""
        return TimeValue(
            value=UnitConverter.convert_time(self.value, self.unit, unit),
            unit=unit,
        )


class MassRate(BaseModel):
    """Mass flow ``value`` ``mass_unit`` per ``time_unit``."""

    model_config = ConfigDict(frozen=True)

    value: float = Field(ge=0, allow_inf_nan=False)
    mass_unit: MassUnit
    time_unit: TimeUnit

    def to_kg_per_minute(self) -> float:
        """Return the rate in canonical kg per minute."""
        kg = UnitConverter.convert_mass(
            self.value, self.mass_unit, MassUnit.KG
        )
        return kg / UnitConverter.minutes_per(self.time_unit)

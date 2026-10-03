"""Tests for units, TimeValue and UnitConverter."""

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError as PydanticValidationError

from app.domain.errors import UnitError
from app.domain.units import DAYS_PER_MONTH
from app.domain.units import DAYS_PER_YEAR
from app.domain.units import EnergyUnit
from app.domain.units import MassRate
from app.domain.units import MassUnit
from app.domain.units import PowerUnit
from app.domain.units import TimeUnit
from app.domain.units import TimeValue
from app.domain.units import UnitConverter


def test_canonical_time_factors() -> None:
    assert UnitConverter.minutes_per(TimeUnit.MINUTES) == 1.0
    assert UnitConverter.minutes_per(TimeUnit.HOURS) == 60.0
    assert UnitConverter.minutes_per(TimeUnit.DAYS) == 1440.0
    assert UnitConverter.minutes_per(TimeUnit.MONTHS) == pytest.approx(
        30.4375 * 1440
    )
    assert UnitConverter.minutes_per(TimeUnit.YEARS) == pytest.approx(
        365.25 * 1440
    )


def test_calendar_conventions() -> None:
    assert DAYS_PER_MONTH == 30.4375
    assert DAYS_PER_YEAR == 365.25
    assert UnitConverter.convert_time(
        1, TimeUnit.YEARS, TimeUnit.DAYS
    ) == pytest.approx(365.25)
    assert UnitConverter.convert_time(
        12, TimeUnit.MONTHS, TimeUnit.DAYS
    ) == pytest.approx(365.25)


@pytest.mark.parametrize(
    ("value", "unit", "minutes"),
    [
        (90, TimeUnit.MINUTES, 90),
        (1.5, TimeUnit.HOURS, 90),
        (14, TimeUnit.DAYS, 14 * 1440),
        (1000, TimeUnit.HOURS, 60_000),
    ],
)
def test_to_and_from_minutes(
    value: float, unit: TimeUnit, minutes: float
) -> None:
    assert UnitConverter.to_minutes(value, unit) == pytest.approx(minutes)
    assert UnitConverter.from_minutes(minutes, unit) == pytest.approx(value)


@given(
    value=st.floats(min_value=0, max_value=1e9),
    source=st.sampled_from(list(TimeUnit)),
    target=st.sampled_from(list(TimeUnit)),
)
def test_time_conversion_round_trip(
    value: float, source: TimeUnit, target: TimeUnit
) -> None:
    there = UnitConverter.convert_time(value, source, target)
    back = UnitConverter.convert_time(there, target, source)
    assert back == pytest.approx(value, rel=1e-9, abs=1e-12)


@pytest.mark.parametrize("bad", [-1.0, math.nan, math.inf])
def test_converter_rejects_invalid_values(bad: float) -> None:
    with pytest.raises(UnitError):
        UnitConverter.to_minutes(bad, TimeUnit.HOURS)


def test_time_value_basics() -> None:
    tv = TimeValue(value=30, unit=TimeUnit.DAYS)
    assert tv.to_minutes() == 30 * 1440
    in_hours = tv.to_unit(TimeUnit.HOURS)
    assert in_hours.value == pytest.approx(720)
    assert in_hours.unit is TimeUnit.HOURS
    assert tv.to_unit(TimeUnit.DAYS) == tv


@pytest.mark.parametrize("bad", [-0.1, math.nan, math.inf])
def test_time_value_rejects_invalid(bad: float) -> None:
    with pytest.raises(PydanticValidationError):
        TimeValue(value=bad, unit=TimeUnit.HOURS)


def test_time_value_is_frozen() -> None:
    tv = TimeValue(value=1, unit=TimeUnit.HOURS)
    with pytest.raises(PydanticValidationError):
        tv.value = 2  # type: ignore[misc]


def test_mass_energy_power_conversion() -> None:
    assert UnitConverter.convert_mass(
        2, MassUnit.TONNES, MassUnit.KG
    ) == pytest.approx(2000)
    assert UnitConverter.convert_energy(
        1, EnergyUnit.KWH, EnergyUnit.MJ
    ) == pytest.approx(3.6)
    assert UnitConverter.convert_energy(
        2000, EnergyUnit.MJ, EnergyUnit.GJ
    ) == pytest.approx(2)
    assert UnitConverter.convert_power(
        1.5, PowerUnit.MW, PowerUnit.KW
    ) == pytest.approx(1500)


def test_mass_rate_to_kg_per_minute() -> None:
    rate = MassRate(
        value=100_000, mass_unit=MassUnit.TONNES, time_unit=TimeUnit.YEARS
    )
    expected = 100_000 * 1000 / (365.25 * 1440)
    assert rate.to_kg_per_minute() == pytest.approx(expected)


def test_mass_rate_rejects_negative() -> None:
    with pytest.raises(PydanticValidationError):
        MassRate(value=-1, mass_unit=MassUnit.KG, time_unit=TimeUnit.HOURS)

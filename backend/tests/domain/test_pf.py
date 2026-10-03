"""Tests for the PF interval and the T_pf = T_f - PF rule."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError as PydanticValidationError

from app.domain.reliability.pf import PFInterval
from app.domain.reliability.pf import potential_failure_time
from app.domain.units import TimeUnit


def test_pf_interval_keeps_value_and_unit() -> None:
    pf = PFInterval(value=14, unit=TimeUnit.DAYS)
    assert pf.value == 14
    assert pf.unit is TimeUnit.DAYS
    assert pf.to_minutes() == 14 * 1440
    tv = pf.as_time_value()
    assert tv.value == 14
    assert tv.unit is TimeUnit.DAYS


@pytest.mark.parametrize("bad", [0, -1, float("nan"), float("inf")])
def test_pf_interval_must_be_positive_and_finite(bad: float) -> None:
    with pytest.raises(PydanticValidationError):
        PFInterval(value=bad, unit=TimeUnit.HOURS)


def test_golden_pf_onset() -> None:
    # T_f = 1000 h, PF = 100 h -> T_pf = 900 h; a check at 950 h with
    # p = 1 falls inside [T_pf, T_f), so the failure is detected.
    onset = potential_failure_time(1000.0, 100.0)
    assert onset == 900.0
    assert onset <= 950.0 < 1000.0


def test_negative_onset_is_not_modelled() -> None:
    assert potential_failure_time(50.0, 100.0) is None


def test_onset_exactly_at_zero_is_modelled() -> None:
    assert potential_failure_time(100.0, 100.0) == 0.0


@given(
    t_f=st.floats(min_value=0, max_value=1e7),
    pf=st.floats(min_value=1e-6, max_value=1e7),
)
def test_onset_formula_invariant(t_f: float, pf: float) -> None:
    onset = potential_failure_time(t_f, pf)
    if t_f - pf < 0:
        assert onset is None
    else:
        assert onset == t_f - pf
        assert onset < t_f

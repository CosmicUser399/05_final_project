"""Mathematical tests of distribution value objects."""

import math
from typing import Any

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError as PydanticValidationError

from app.domain.errors import UnsupportedOperationError
from app.domain.errors import ValidationError
from app.domain.reliability.distributions import Constant
from app.domain.reliability.distributions import Distribution
from app.domain.reliability.distributions import DistributionType
from app.domain.reliability.distributions import Empirical
from app.domain.reliability.distributions import Exponential
from app.domain.reliability.distributions import Gamma
from app.domain.reliability.distributions import LogLogistic
from app.domain.reliability.distributions import Lognormal
from app.domain.reliability.distributions import Normal
from app.domain.reliability.distributions import Triangular
from app.domain.reliability.distributions import Uniform
from app.domain.reliability.distributions import Weibull
from app.domain.reliability.distributions import parse_distribution
from app.domain.units import TimeUnit

H = TimeUnit.HOURS

CONTINUOUS: list[Distribution] = [
    Exponential(lambda_=0.002, unit=H),
    Weibull(shape=2.5, scale=1000.0, unit=H),
    Weibull(shape=0.8, scale=500.0, unit=H),
    Lognormal(mu=6.0, sigma=0.5, unit=H),
    Normal(mu=100.0, sigma=20.0, unit=H),
    Normal(mu=10.0, sigma=20.0, unit=H),
    Gamma(shape=3.0, scale=50.0, unit=H),
    Gamma(shape=0.7, scale=40.0, unit=H),
    LogLogistic(shape=5.0, scale=300.0, unit=H),
    Uniform(low=10.0, high=50.0, unit=H),
    Triangular(low=5.0, mode=10.0, high=30.0, unit=H),
]


def _ids(dists: list[Distribution]) -> list[str]:
    return [f"{d.type}-{i}" for i, d in enumerate(dists)]


# -- exponential -----------------------------------------------------


def test_exponential_reliability_is_exp_minus_lambda_t() -> None:
    dist = Exponential(lambda_=1e-3, unit=H)
    for t in (0.0, 10.0, 1000.0, 5000.0):
        assert dist.survival(t) == pytest.approx(math.exp(-1e-3 * t))
        assert dist.cdf(t) == pytest.approx(1 - math.exp(-1e-3 * t))
    assert dist.mean() == pytest.approx(1000.0)
    assert dist.variance() == pytest.approx(1e6)


def test_exponential_has_constant_hazard() -> None:
    dist = Exponential(lambda_=0.01, unit=H)
    for t in (0.0, 1.0, 50.0, 400.0):
        assert dist.hazard(t) == pytest.approx(0.01)


def test_exponential_memoryless_quantile() -> None:
    dist = Exponential(lambda_=0.5, unit=H)
    assert dist.quantile(0.5) == pytest.approx(math.log(2) / 0.5)
    assert dist.quantile(0.0) == 0.0
    assert dist.quantile(1.0) == math.inf


# -- weibull ---------------------------------------------------------


def test_weibull_formulas() -> None:
    dist = Weibull(shape=2.0, scale=1000.0, unit=H)
    t = 800.0
    expected_r = math.exp(-((t / 1000.0) ** 2))
    assert dist.survival(t) == pytest.approx(expected_r)
    assert dist.mean() == pytest.approx(1000.0 * math.sqrt(math.pi) / 2)
    assert dist.hazard(t) == pytest.approx(2.0 / 1000.0 * (t / 1000.0))
    assert dist.quantile(1.0) == math.inf
    assert dist.quantile(0.0) == 0.0
    # Weibull(shape=2) variance = scale^2 (1 - pi / 4)
    assert dist.variance() == pytest.approx(1e6 * (1 - math.pi / 4))


def test_weibull_shape_one_is_exponential() -> None:
    weibull = Weibull(shape=1.0, scale=500.0, unit=H)
    expo = Exponential(lambda_=1 / 500.0, unit=H)
    for t in (0.0, 10.0, 500.0, 2000.0):
        assert weibull.cdf(t) == pytest.approx(expo.cdf(t))
        assert weibull.pdf(t) == pytest.approx(expo.pdf(t))


def test_weibull_pdf_at_zero_depends_on_shape() -> None:
    assert Weibull(shape=0.5, scale=1.0, unit=H).pdf(0.0) == math.inf
    assert Weibull(shape=1.0, scale=4.0, unit=H).pdf(0.0) == 0.25
    assert Weibull(shape=2.0, scale=1.0, unit=H).pdf(0.0) == 0.0


def test_weibull_wearout_hazard_increases() -> None:
    dist = Weibull(shape=3.0, scale=1000.0, unit=H)
    hazards = [dist.hazard(t) for t in (100.0, 300.0, 600.0, 900.0)]
    assert hazards == sorted(hazards)


def test_weibull_overflow_is_handled() -> None:
    dist = Weibull(shape=50.0, scale=1.0, unit=H)
    assert dist.survival(1e100) == 0.0
    assert dist.cdf(1e100) == 1.0
    assert dist.pdf(1e100) == 0.0


@given(
    shape=st.floats(min_value=0.3, max_value=6.0),
    scale=st.floats(min_value=1.0, max_value=1e5),
    t1=st.floats(min_value=0.0, max_value=1e5),
    dt=st.floats(min_value=0.0, max_value=1e5),
)
def test_weibull_reliability_is_monotone(
    shape: float, scale: float, t1: float, dt: float
) -> None:
    dist = Weibull(shape=shape, scale=scale, unit=H)
    assert dist.survival(t1 + dt) <= dist.survival(t1) + 1e-12
    assert 0.0 <= dist.survival(t1) <= 1.0


# -- generic contract ------------------------------------------------


@pytest.mark.parametrize("dist", CONTINUOUS, ids=_ids(CONTINUOUS))
def test_cdf_and_quantile_are_inverse(dist: Distribution) -> None:
    for p in (0.01, 0.1, 0.5, 0.9, 0.99):
        x = dist.quantile(p)
        assert dist.cdf(x) == pytest.approx(p, abs=1e-9)
        assert dist.quantile(dist.cdf(x)) == pytest.approx(x, rel=1e-6)


@pytest.mark.parametrize("dist", CONTINUOUS, ids=_ids(CONTINUOUS))
def test_cdf_is_monotone_and_bounded(dist: Distribution) -> None:
    xs = np.linspace(0.0, dist.quantile(0.999), 200)
    values = [dist.cdf(float(x)) for x in xs]
    assert values == sorted(values)
    assert all(0.0 <= v <= 1.0 for v in values)
    assert dist.cdf(-1.0) == 0.0
    assert dist.survival(0.0) == pytest.approx(1.0)


@pytest.mark.parametrize("dist", CONTINUOUS, ids=_ids(CONTINUOUS))
def test_pdf_is_derivative_of_cdf(dist: Distribution) -> None:
    for p in (0.2, 0.5, 0.8):
        x = dist.quantile(p)
        h = 1e-5 * x
        numeric = (dist.cdf(x + h) - dist.cdf(x - h)) / (2 * h)
        assert dist.pdf(x) == pytest.approx(numeric, rel=1e-4)
    assert dist.pdf(-1.0) == 0.0


@pytest.mark.parametrize("dist", CONTINUOUS, ids=_ids(CONTINUOUS))
def test_sample_moments_match_theory(dist: Distribution) -> None:
    n = 200_000
    rng = np.random.default_rng(20260101)
    data = dist.sample_many(rng, n)
    assert data.shape == (n,)
    assert (data >= 0).all()
    std_err = math.sqrt(dist.variance() / n)
    assert float(data.mean()) == pytest.approx(dist.mean(), abs=5 * std_err)
    assert float(data.var()) == pytest.approx(dist.variance(), rel=0.06)


@pytest.mark.parametrize("dist", CONTINUOUS, ids=_ids(CONTINUOUS))
def test_sample_quantiles_match_cdf(dist: Distribution) -> None:
    rng = np.random.default_rng(7)
    data = dist.sample_many(rng, 100_000)
    for p in (0.1, 0.5, 0.9):
        empirical = float((data <= dist.quantile(p)).mean())
        assert empirical == pytest.approx(p, abs=0.01)


@pytest.mark.parametrize("dist", CONTINUOUS, ids=_ids(CONTINUOUS))
def test_sampling_is_reproducible(dist: Distribution) -> None:
    a = dist.sample_many(np.random.default_rng(42), 50)
    b = dist.sample_many(np.random.default_rng(42), 50)
    c = dist.sample_many(np.random.default_rng(43), 50)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)
    assert dist.sample(np.random.default_rng(1)) == dist.sample(
        np.random.default_rng(1)
    )


@pytest.mark.parametrize("dist", CONTINUOUS, ids=_ids(CONTINUOUS))
def test_to_minutes_scales_the_law(dist: Distribution) -> None:
    in_min = dist.to_minutes()
    assert in_min.unit is TimeUnit.MINUTES
    for p in (0.1, 0.5, 0.9):
        assert in_min.quantile(p) == pytest.approx(
            60.0 * dist.quantile(p), rel=1e-9
        )
    assert in_min.mean() == pytest.approx(60.0 * dist.mean(), rel=1e-9)
    assert in_min.cdf(60.0 * 80.0) == pytest.approx(dist.cdf(80.0))
    assert dist.to_unit(dist.unit) is dist


@pytest.mark.parametrize("dist", CONTINUOUS, ids=_ids(CONTINUOUS))
def test_json_round_trip(dist: Distribution) -> None:
    payload = dist.model_dump(mode="json", by_alias=True)
    assert payload["type"] == dist.type
    assert parse_distribution(payload) == dist


def test_quantile_rejects_probability_outside_unit_interval() -> None:
    dist = Weibull(shape=2.0, scale=10.0, unit=H)
    for bad in (-0.1, 1.1):
        with pytest.raises(ValidationError):
            dist.quantile(bad)


def test_hazard_is_infinite_when_reliability_is_zero() -> None:
    assert Uniform(low=1.0, high=2.0, unit=H).hazard(5.0) == math.inf


# -- specific laws ---------------------------------------------------


def test_lognormal_formulas() -> None:
    dist = Lognormal(mu=1.0, sigma=0.5, unit=H)
    assert dist.mean() == pytest.approx(math.exp(1.0 + 0.125))
    assert dist.quantile(0.5) == pytest.approx(math.e)
    assert dist.cdf(0.0) == 0.0
    assert dist.pdf(0.0) == 0.0
    assert dist.quantile(0.0) == 0.0
    assert dist.quantile(1.0) == math.inf


def test_gamma_with_shape_one_is_exponential() -> None:
    gamma = Gamma(shape=1.0, scale=200.0, unit=H)
    expo = Exponential(lambda_=1 / 200.0, unit=H)
    for t in (1.0, 100.0, 700.0):
        assert gamma.cdf(t) == pytest.approx(expo.cdf(t))
        assert gamma.pdf(t) == pytest.approx(expo.pdf(t))
    assert gamma.pdf(0.0) == pytest.approx(1 / 200.0)
    assert Gamma(shape=0.5, scale=1.0, unit=H).pdf(0.0) == math.inf
    assert Gamma(shape=2.0, scale=1.0, unit=H).pdf(0.0) == 0.0
    assert gamma.quantile(1.0) == math.inf


def test_loglogistic_formulas() -> None:
    dist = LogLogistic(shape=4.0, scale=100.0, unit=H)
    assert dist.cdf(100.0) == pytest.approx(0.5)
    assert dist.quantile(0.5) == pytest.approx(100.0)
    b = math.pi / 4.0
    assert dist.mean() == pytest.approx(100.0 * b / math.sin(b))
    assert LogLogistic(shape=1.0, scale=1.0, unit=H).mean() == math.inf
    assert LogLogistic(shape=2.0, scale=1.0, unit=H).variance() == math.inf
    assert LogLogistic(shape=0.5, scale=1.0, unit=H).pdf(0.0) == math.inf
    assert LogLogistic(shape=1.0, scale=2.0, unit=H).pdf(0.0) == 0.5
    assert LogLogistic(shape=2.0, scale=2.0, unit=H).pdf(0.0) == 0.0
    assert dist.quantile(0.0) == 0.0
    assert dist.quantile(1.0) == math.inf
    assert dist.pdf(1e200) == 0.0
    assert dist.cdf(0.0) == 0.0
    assert dist.survival(0.0) == 1.0


def test_normal_is_truncated_at_zero() -> None:
    wide = Normal(mu=10.0, sigma=20.0, unit=H)
    assert wide.cdf(0.0) == 0.0
    assert wide.mean() > 10.0  # truncation shifts the mean up
    data = wide.sample_many(np.random.default_rng(3), 10_000)
    assert (data >= 0).all()
    tight = Normal(mu=1000.0, sigma=10.0, unit=H)
    assert tight.mean() == pytest.approx(1000.0)
    assert tight.variance() == pytest.approx(100.0)
    assert tight.quantile(0.5) == pytest.approx(1000.0)
    assert tight.quantile(1.0) == math.inf
    assert tight.pdf(-1.0) == 0.0


def test_uniform_and_triangular_edges() -> None:
    uni = Uniform(low=10.0, high=20.0, unit=H)
    assert uni.cdf(5.0) == 0.0
    assert uni.cdf(25.0) == 1.0
    assert uni.pdf(15.0) == pytest.approx(0.1)
    assert uni.pdf(25.0) == 0.0
    assert uni.mean() == 15.0
    assert uni.variance() == pytest.approx(100 / 12)
    tri = Triangular(low=0.0, mode=10.0, high=20.0, unit=H)
    assert tri.mean() == pytest.approx(10.0)
    assert tri.cdf(10.0) == pytest.approx(0.5)
    assert tri.cdf(25.0) == 1.0
    assert tri.pdf(10.0) == pytest.approx(0.1)
    assert tri.pdf(-1.0) == 0.0
    assert tri.pdf(25.0) == 0.0
    assert tri.quantile(0.5) == pytest.approx(10.0)
    right = Triangular(low=0.0, mode=20.0, high=20.0, unit=H)
    assert right.cdf(10.0) == pytest.approx(0.25)
    assert right.pdf(10.0) == pytest.approx(0.05)


def test_constant_distribution() -> None:
    dist = Constant(value=2.0, unit=H)
    assert dist.cdf(1.99) == 0.0
    assert dist.cdf(2.0) == 1.0
    assert dist.survival(3.0) == 0.0
    assert dist.pdf(2.0) == math.inf
    assert dist.pdf(1.0) == 0.0
    assert dist.mean() == 2.0
    assert dist.variance() == 0.0
    assert dist.quantile(0.3) == 2.0
    data = dist.sample_many(np.random.default_rng(0), 5)
    assert data.tolist() == [2.0] * 5
    assert dist.to_minutes() == Constant(value=120.0, unit=TimeUnit.MINUTES)


def test_empirical_distribution() -> None:
    dist = Empirical(samples=(40.0, 10.0, 30.0, 20.0), unit=H)
    assert dist.samples == (10.0, 20.0, 30.0, 40.0)
    assert dist.mean() == 25.0
    assert dist.variance() == pytest.approx(125.0)
    assert dist.cdf(5.0) == 0.0
    assert dist.cdf(20.0) == 0.5
    assert dist.cdf(100.0) == 1.0
    assert dist.quantile(0.0) == 10.0
    assert dist.quantile(0.5) == 20.0
    assert dist.quantile(1.0) == 40.0
    data = dist.sample_many(np.random.default_rng(5), 1000)
    assert set(data.tolist()) <= {10.0, 20.0, 30.0, 40.0}
    with pytest.raises(UnsupportedOperationError):
        dist.pdf(10.0)
    scaled = dist.to_minutes()
    assert scaled.mean() == pytest.approx(25.0 * 60.0)
    assert Empirical(samples=(1.0, 2.0), unit=H).samples == (1.0, 2.0)


# -- validation ------------------------------------------------------


@pytest.mark.parametrize(
    "factory",
    [
        lambda: Exponential(lambda_=0.0, unit=H),
        lambda: Exponential(lambda_=-1.0, unit=H),
        lambda: Weibull(shape=0.0, scale=1.0, unit=H),
        lambda: Weibull(shape=1.0, scale=-1.0, unit=H),
        lambda: Weibull(shape=math.nan, scale=1.0, unit=H),
        lambda: Weibull(shape=1.0, scale=math.inf, unit=H),
        lambda: Lognormal(mu=0.0, sigma=0.0, unit=H),
        lambda: Lognormal(mu=math.inf, sigma=1.0, unit=H),
        lambda: Normal(mu=-1.0, sigma=1.0, unit=H),
        lambda: Normal(mu=1.0, sigma=0.0, unit=H),
        lambda: Gamma(shape=-1.0, scale=1.0, unit=H),
        lambda: LogLogistic(shape=1.0, scale=0.0, unit=H),
        lambda: Uniform(low=5.0, high=5.0, unit=H),
        lambda: Uniform(low=-1.0, high=5.0, unit=H),
        lambda: Triangular(low=0.0, mode=30.0, high=20.0, unit=H),
        lambda: Triangular(low=5.0, mode=5.0, high=5.0, unit=H),
        lambda: Constant(value=0.0, unit=H),
        lambda: Empirical(samples=(), unit=H),
        lambda: Empirical(samples=(-1.0, 2.0), unit=H),
        lambda: Empirical(samples=(0.0, 0.0), unit=H),
    ],
)
def test_invalid_parameters_are_rejected(factory: Any) -> None:
    with pytest.raises(PydanticValidationError):
        factory()


def test_distribution_is_frozen() -> None:
    dist = Weibull(shape=2.0, scale=10.0, unit=H)
    with pytest.raises(PydanticValidationError):
        dist.shape = 3.0  # type: ignore[misc]


def test_lambda_alias_and_field_name() -> None:
    by_alias = parse_distribution(
        {"type": "EXPONENTIAL", "lambda": 0.5, "unit": "HOURS"}
    )
    assert isinstance(by_alias, Exponential)
    assert by_alias.lambda_ == 0.5
    assert Exponential(lambda_=0.5, unit=H) == by_alias
    assert Exponential(**{"lambda": 0.5}, unit=H) == by_alias


def test_parse_distribution_selects_family_by_type() -> None:
    parsed = parse_distribution(
        {"type": "WEIBULL", "shape": 1.5, "scale": 100, "unit": "DAYS"}
    )
    assert isinstance(parsed, Weibull)
    assert parsed.type is DistributionType.WEIBULL
    with pytest.raises(PydanticValidationError):
        parse_distribution({"type": "UNKNOWN", "unit": "DAYS"})
    with pytest.raises(PydanticValidationError):
        parse_distribution({"type": "WEIBULL", "unit": "DAYS"})


def test_all_distribution_families_are_declared() -> None:
    assert {d.value for d in DistributionType} == {
        "EXPONENTIAL",
        "WEIBULL",
        "LOGNORMAL",
        "NORMAL",
        "GAMMA",
        "LOGLOGISTIC",
        "UNIFORM",
        "TRIANGULAR",
        "CONSTANT",
        "EMPIRICAL",
    }

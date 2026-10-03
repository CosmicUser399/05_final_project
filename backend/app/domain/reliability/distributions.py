"""Life-time and duration distributions (value objects).

Every distribution is immutable, has named parameters and an explicit
time ``unit`` for its time-scaled parameters. The engine works in
minutes: use ``to_minutes()`` before sampling.

Interface: ``sample`` / ``sample_many``, ``cdf``, ``pdf``, ``survival``,
``hazard``, ``quantile``, ``mean``, ``variance``.

Conventions
-----------
* ``Exponential(lambda_)`` - failure rate per ``unit``.
* ``Weibull`` / ``Gamma`` / ``LogLogistic`` - ``shape`` and ``scale``.
* ``Lognormal(mu, sigma)`` - parameters of ``ln(T)``, ``T`` in ``unit``.
* ``Normal(mu, sigma)`` - parent normal law truncated at zero (a
  duration is never negative); ``mean`` is the truncated mean.
"""

import math
from abc import ABC
from abc import abstractmethod
from bisect import bisect_right
from enum import StrEnum
from typing import Annotated
from typing import Final
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import TypeAdapter
from pydantic import model_validator
from scipy import special

from app.domain.errors import UnsupportedOperationError
from app.domain.errors import ValidationError
from app.domain.units import TimeUnit
from app.domain.units import UnitConverter

MAX_EMPIRICAL_SAMPLES: Final[int] = 100_000
_SQRT2: Final[float] = math.sqrt(2.0)
_SQRT_2PI: Final[float] = math.sqrt(2.0 * math.pi)

Floats = NDArray[np.float64]
Positive = Annotated[float, Field(gt=0, allow_inf_nan=False)]
NonNegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]
Finite = Annotated[float, Field(allow_inf_nan=False)]


class DistributionType(StrEnum):
    """Supported distribution families."""

    EXPONENTIAL = "EXPONENTIAL"
    WEIBULL = "WEIBULL"
    LOGNORMAL = "LOGNORMAL"
    NORMAL = "NORMAL"
    GAMMA = "GAMMA"
    LOGLOGISTIC = "LOGLOGISTIC"
    UNIFORM = "UNIFORM"
    TRIANGULAR = "TRIANGULAR"
    CONSTANT = "CONSTANT"
    EMPIRICAL = "EMPIRICAL"


def _phi(z: float) -> float:
    """Return the standard normal density."""
    return math.exp(-0.5 * z * z) / _SQRT_2PI


def _big_phi(z: float) -> float:
    """Return the standard normal CDF."""
    return 0.5 * math.erfc(-z / _SQRT2)


def _pow(base: float, exponent: float) -> float:
    """Power that returns ``inf`` instead of raising on overflow."""
    try:
        return math.pow(base, exponent)
    except OverflowError:
        return math.inf


def _check_probability(p: float) -> float:
    if not 0.0 <= p <= 1.0:
        raise ValidationError(
            f"probability must be in [0, 1], got {p!r}",
            code="INVALID_PROBABILITY",
        )
    return p


class Distribution(BaseModel, ABC):
    """Base class of all distributions."""

    model_config = ConfigDict(
        frozen=True,
        validate_by_name=True,
        validate_by_alias=True,
    )

    type: DistributionType
    unit: TimeUnit

    @abstractmethod
    def cdf(self, t: float) -> float:
        """Return ``P(T <= t)``."""

    @abstractmethod
    def pdf(self, t: float) -> float:
        """Return the probability density at ``t``."""

    @abstractmethod
    def quantile(self, p: float) -> float:
        """Return the ``p``-quantile (inverse CDF)."""

    @abstractmethod
    def mean(self) -> float:
        """Return the expected value (``inf`` if it does not exist)."""

    @abstractmethod
    def variance(self) -> float:
        """Return the variance (``inf`` if it does not exist)."""

    @abstractmethod
    def sample_many(self, rng: np.random.Generator, size: int) -> Floats:
        """Draw ``size`` independent samples."""

    @abstractmethod
    def _rescaled(self, factor: float, unit: TimeUnit) -> "Distribution":
        """Return the law of ``factor * T`` expressed in ``unit``."""

    def survival(self, t: float) -> float:
        """Return the reliability function ``R(t) = P(T > t)``."""
        return 1.0 - self.cdf(t)

    def hazard(self, t: float) -> float:
        """Return the hazard rate ``pdf(t) / R(t)``."""
        reliability = self.survival(t)
        if reliability <= 0.0:
            return math.inf
        return self.pdf(t) / reliability

    def sample(self, rng: np.random.Generator) -> float:
        """Draw one sample."""
        return float(self.sample_many(rng, 1)[0])

    def to_unit(self, unit: TimeUnit) -> "Distribution":
        """Return the same law expressed in another time unit."""
        if unit is self.unit:
            return self
        factor = UnitConverter.minutes_per(
            self.unit
        ) / UnitConverter.minutes_per(unit)
        return self._rescaled(factor, unit)

    def to_minutes(self) -> "Distribution":
        """Return the same law expressed in canonical minutes."""
        return self.to_unit(TimeUnit.MINUTES)


class Exponential(Distribution):
    """Exponential law, constant hazard ``lambda_``."""

    type: Literal[DistributionType.EXPONENTIAL] = DistributionType.EXPONENTIAL
    lambda_: Positive = Field(alias="lambda")

    def cdf(self, t: float) -> float:
        """Return ``1 - exp(-lambda * t)``."""
        if t <= 0:
            return 0.0
        return -math.expm1(-self.lambda_ * t)

    def survival(self, t: float) -> float:
        """Return ``exp(-lambda * t)``."""
        if t <= 0:
            return 1.0
        return math.exp(-self.lambda_ * t)

    def pdf(self, t: float) -> float:
        """Return ``lambda * exp(-lambda * t)``."""
        if t < 0:
            return 0.0
        return self.lambda_ * math.exp(-self.lambda_ * t)

    def quantile(self, p: float) -> float:
        """Return ``-ln(1 - p) / lambda``."""
        _check_probability(p)
        if p == 1.0:
            return math.inf
        return -math.log1p(-p) / self.lambda_

    def mean(self) -> float:
        """Return ``1 / lambda``."""
        return 1.0 / self.lambda_

    def variance(self) -> float:
        """Return ``1 / lambda^2``."""
        return 1.0 / self.lambda_**2

    def sample_many(self, rng: np.random.Generator, size: int) -> Floats:
        """Draw exponential samples."""
        return rng.exponential(1.0 / self.lambda_, size)

    def _rescaled(self, factor: float, unit: TimeUnit) -> "Exponential":
        return Exponential(lambda_=self.lambda_ / factor, unit=unit)


class Weibull(Distribution):
    """Two-parameter Weibull law."""

    type: Literal[DistributionType.WEIBULL] = DistributionType.WEIBULL
    shape: Positive
    scale: Positive

    def cdf(self, t: float) -> float:
        """Return ``1 - exp(-(t / scale)^shape)``."""
        if t <= 0:
            return 0.0
        return -math.expm1(-_pow(t / self.scale, self.shape))

    def survival(self, t: float) -> float:
        """Return ``exp(-(t / scale)^shape)``."""
        if t <= 0:
            return 1.0
        return math.exp(-_pow(t / self.scale, self.shape))

    def pdf(self, t: float) -> float:
        """Return the Weibull density."""
        if t < 0:
            return 0.0
        if t == 0:
            if self.shape < 1:
                return math.inf
            return 1.0 / self.scale if self.shape == 1 else 0.0
        x = t / self.scale
        xb = _pow(x, self.shape)
        if math.isinf(xb):
            return 0.0
        return (
            self.shape / self.scale * _pow(x, self.shape - 1.0) * math.exp(-xb)
        )

    def quantile(self, p: float) -> float:
        """Return ``scale * (-ln(1 - p))^(1 / shape)``."""
        _check_probability(p)
        if p == 1.0:
            return math.inf
        return self.scale * math.pow(-math.log1p(-p), 1.0 / self.shape)

    def mean(self) -> float:
        """Return ``scale * Gamma(1 + 1 / shape)``."""
        return self.scale * math.gamma(1.0 + 1.0 / self.shape)

    def variance(self) -> float:
        """Return the Weibull variance."""
        g1 = math.gamma(1.0 + 1.0 / self.shape)
        g2 = math.gamma(1.0 + 2.0 / self.shape)
        return self.scale**2 * (g2 - g1**2)

    def sample_many(self, rng: np.random.Generator, size: int) -> Floats:
        """Draw Weibull samples."""
        return self.scale * rng.weibull(self.shape, size)

    def _rescaled(self, factor: float, unit: TimeUnit) -> "Weibull":
        return Weibull(shape=self.shape, scale=self.scale * factor, unit=unit)


class Lognormal(Distribution):
    """Lognormal law; ``mu`` and ``sigma`` describe ``ln(T)``."""

    type: Literal[DistributionType.LOGNORMAL] = DistributionType.LOGNORMAL
    mu: Finite
    sigma: Positive

    def cdf(self, t: float) -> float:
        """Return ``Phi((ln t - mu) / sigma)``."""
        if t <= 0:
            return 0.0
        return _big_phi((math.log(t) - self.mu) / self.sigma)

    def pdf(self, t: float) -> float:
        """Return the lognormal density."""
        if t <= 0:
            return 0.0
        z = (math.log(t) - self.mu) / self.sigma
        return _phi(z) / (t * self.sigma)

    def quantile(self, p: float) -> float:
        """Return ``exp(mu + sigma * Phi^-1(p))``."""
        _check_probability(p)
        if p == 0.0:
            return 0.0
        if p == 1.0:
            return math.inf
        return math.exp(self.mu + self.sigma * float(special.ndtri(p)))

    def mean(self) -> float:
        """Return ``exp(mu + sigma^2 / 2)``."""
        return math.exp(self.mu + self.sigma**2 / 2.0)

    def variance(self) -> float:
        """Return the lognormal variance."""
        s2 = self.sigma**2
        return math.expm1(s2) * math.exp(2.0 * self.mu + s2)

    def sample_many(self, rng: np.random.Generator, size: int) -> Floats:
        """Draw lognormal samples."""
        return rng.lognormal(self.mu, self.sigma, size)

    def _rescaled(self, factor: float, unit: TimeUnit) -> "Lognormal":
        return Lognormal(
            mu=self.mu + math.log(factor), sigma=self.sigma, unit=unit
        )


class Normal(Distribution):
    """Normal law truncated at zero (``mu > 0``)."""

    type: Literal[DistributionType.NORMAL] = DistributionType.NORMAL
    mu: Positive
    sigma: Positive

    @property
    def _alpha(self) -> float:
        return -self.mu / self.sigma

    @property
    def _norm(self) -> float:
        """Mass of the parent law on ``[0, inf)``."""
        return 1.0 - _big_phi(self._alpha)

    def cdf(self, t: float) -> float:
        """Return the truncated normal CDF."""
        if t <= 0:
            return 0.0
        z = (t - self.mu) / self.sigma
        return (_big_phi(z) - _big_phi(self._alpha)) / self._norm

    def pdf(self, t: float) -> float:
        """Return the truncated normal density."""
        if t < 0:
            return 0.0
        z = (t - self.mu) / self.sigma
        return _phi(z) / (self.sigma * self._norm)

    def quantile(self, p: float) -> float:
        """Return the truncated normal quantile."""
        _check_probability(p)
        if p == 1.0:
            return math.inf
        base = _big_phi(self._alpha)
        value = float(special.ndtri(base + p * self._norm))
        return max(0.0, self.mu + self.sigma * value)

    def _hazard_ratio(self) -> float:
        return _phi(self._alpha) / self._norm

    def mean(self) -> float:
        """Return the mean of the truncated law."""
        return self.mu + self.sigma * self._hazard_ratio()

    def variance(self) -> float:
        """Return the variance of the truncated law."""
        lam = self._hazard_ratio()
        a = self._alpha
        return self.sigma**2 * (1.0 + a * lam - lam**2)

    def sample_many(self, rng: np.random.Generator, size: int) -> Floats:
        """Draw samples by inverse-transform sampling."""
        base = _big_phi(self._alpha)
        u = rng.random(size)
        z = special.ndtri(base + u * self._norm)
        return np.maximum(0.0, self.mu + self.sigma * z)

    def _rescaled(self, factor: float, unit: TimeUnit) -> "Normal":
        return Normal(
            mu=self.mu * factor, sigma=self.sigma * factor, unit=unit
        )


class Gamma(Distribution):
    """Gamma law with ``shape`` (k) and ``scale`` (theta)."""

    type: Literal[DistributionType.GAMMA] = DistributionType.GAMMA
    shape: Positive
    scale: Positive

    def cdf(self, t: float) -> float:
        """Return the regularised incomplete gamma function."""
        if t <= 0:
            return 0.0
        return float(special.gammainc(self.shape, t / self.scale))

    def pdf(self, t: float) -> float:
        """Return the gamma density."""
        if t < 0:
            return 0.0
        if t == 0:
            if self.shape < 1:
                return math.inf
            return 1.0 / self.scale if self.shape == 1 else 0.0
        x = t / self.scale
        log_pdf = (
            (self.shape - 1.0) * math.log(x) - x - math.lgamma(self.shape)
        )
        return math.exp(log_pdf) / self.scale

    def quantile(self, p: float) -> float:
        """Return the gamma quantile."""
        _check_probability(p)
        if p == 1.0:
            return math.inf
        return self.scale * float(special.gammaincinv(self.shape, p))

    def mean(self) -> float:
        """Return ``shape * scale``."""
        return self.shape * self.scale

    def variance(self) -> float:
        """Return ``shape * scale^2``."""
        return self.shape * self.scale**2

    def sample_many(self, rng: np.random.Generator, size: int) -> Floats:
        """Draw gamma samples."""
        return rng.gamma(self.shape, self.scale, size)

    def _rescaled(self, factor: float, unit: TimeUnit) -> "Gamma":
        return Gamma(shape=self.shape, scale=self.scale * factor, unit=unit)


class LogLogistic(Distribution):
    """Log-logistic law with ``shape`` (beta) and ``scale`` (alpha)."""

    type: Literal[DistributionType.LOGLOGISTIC] = DistributionType.LOGLOGISTIC
    shape: Positive
    scale: Positive

    def cdf(self, t: float) -> float:
        """Return ``1 / (1 + (t / scale)^-shape)``."""
        if t <= 0:
            return 0.0
        return 1.0 - self.survival(t)

    def survival(self, t: float) -> float:
        """Return ``1 / (1 + (t / scale)^shape)``."""
        if t <= 0:
            return 1.0
        return 1.0 / (1.0 + _pow(t / self.scale, self.shape))

    def pdf(self, t: float) -> float:
        """Return the log-logistic density."""
        if t < 0:
            return 0.0
        if t == 0:
            if self.shape < 1:
                return math.inf
            return 1.0 / self.scale if self.shape == 1 else 0.0
        x = t / self.scale
        xb = _pow(x, self.shape)
        if math.isinf(xb):
            return 0.0
        return self.shape / self.scale * xb / x / (1.0 + xb) ** 2

    def quantile(self, p: float) -> float:
        """Return ``scale * (p / (1 - p))^(1 / shape)``."""
        _check_probability(p)
        if p == 0.0:
            return 0.0
        if p == 1.0:
            return math.inf
        return self.scale * math.pow(p / (1.0 - p), 1.0 / self.shape)

    def mean(self) -> float:
        """Return the mean (``inf`` for ``shape <= 1``)."""
        if self.shape <= 1.0:
            return math.inf
        b = math.pi / self.shape
        return self.scale * b / math.sin(b)

    def variance(self) -> float:
        """Return the variance (``inf`` for ``shape <= 2``)."""
        if self.shape <= 2.0:
            return math.inf
        b = math.pi / self.shape
        return self.scale**2 * (
            2.0 * b / math.sin(2.0 * b) - (b / math.sin(b)) ** 2
        )

    def sample_many(self, rng: np.random.Generator, size: int) -> Floats:
        """Draw samples by inverse-transform sampling."""
        u = rng.random(size)
        return self.scale * (u / (1.0 - u)) ** (1.0 / self.shape)

    def _rescaled(self, factor: float, unit: TimeUnit) -> "LogLogistic":
        return LogLogistic(
            shape=self.shape, scale=self.scale * factor, unit=unit
        )


class Uniform(Distribution):
    """Continuous uniform law on ``[low, high]``."""

    type: Literal[DistributionType.UNIFORM] = DistributionType.UNIFORM
    low: NonNegative
    high: Positive

    @model_validator(mode="after")
    def _check_bounds(self) -> "Uniform":
        if self.high <= self.low:
            raise ValueError("high must be greater than low")
        return self

    def cdf(self, t: float) -> float:
        """Return the uniform CDF."""
        if t <= self.low:
            return 0.0
        if t >= self.high:
            return 1.0
        return (t - self.low) / (self.high - self.low)

    def pdf(self, t: float) -> float:
        """Return ``1 / (high - low)`` inside the support."""
        if self.low <= t <= self.high:
            return 1.0 / (self.high - self.low)
        return 0.0

    def quantile(self, p: float) -> float:
        """Return ``low + p * (high - low)``."""
        _check_probability(p)
        return self.low + p * (self.high - self.low)

    def mean(self) -> float:
        """Return ``(low + high) / 2``."""
        return (self.low + self.high) / 2.0

    def variance(self) -> float:
        """Return ``(high - low)^2 / 12``."""
        return (self.high - self.low) ** 2 / 12.0

    def sample_many(self, rng: np.random.Generator, size: int) -> Floats:
        """Draw uniform samples."""
        return rng.uniform(self.low, self.high, size)

    def _rescaled(self, factor: float, unit: TimeUnit) -> "Uniform":
        return Uniform(
            low=self.low * factor, high=self.high * factor, unit=unit
        )


class Triangular(Distribution):
    """Triangular law with ``low <= mode <= high``."""

    type: Literal[DistributionType.TRIANGULAR] = DistributionType.TRIANGULAR
    low: NonNegative
    mode: NonNegative
    high: Positive

    @model_validator(mode="after")
    def _check_bounds(self) -> "Triangular":
        if not self.low <= self.mode <= self.high:
            raise ValueError("require low <= mode <= high")
        if self.high <= self.low:
            raise ValueError("high must be greater than low")
        return self

    def cdf(self, t: float) -> float:
        """Return the triangular CDF."""
        a, c, b = self.low, self.mode, self.high
        if t <= a:
            return 0.0
        if t >= b:
            return 1.0
        if t <= c:
            return (t - a) ** 2 / ((b - a) * (c - a))
        return 1.0 - (b - t) ** 2 / ((b - a) * (b - c))

    def pdf(self, t: float) -> float:
        """Return the triangular density."""
        a, c, b = self.low, self.mode, self.high
        if t < a or t > b:
            return 0.0
        if t < c:
            return 2.0 * (t - a) / ((b - a) * (c - a))
        if t > c:
            return 2.0 * (b - t) / ((b - a) * (b - c))
        return 2.0 / (b - a)

    def quantile(self, p: float) -> float:
        """Return the triangular quantile."""
        _check_probability(p)
        a, c, b = self.low, self.mode, self.high
        split = (c - a) / (b - a)
        if p < split:
            return a + math.sqrt(p * (b - a) * (c - a))
        return b - math.sqrt((1.0 - p) * (b - a) * (b - c))

    def mean(self) -> float:
        """Return ``(low + mode + high) / 3``."""
        return (self.low + self.mode + self.high) / 3.0

    def variance(self) -> float:
        """Return the triangular variance."""
        a, c, b = self.low, self.mode, self.high
        return (a * a + b * b + c * c - a * b - a * c - b * c) / 18.0

    def sample_many(self, rng: np.random.Generator, size: int) -> Floats:
        """Draw triangular samples."""
        return rng.triangular(self.low, self.mode, self.high, size)

    def _rescaled(self, factor: float, unit: TimeUnit) -> "Triangular":
        return Triangular(
            low=self.low * factor,
            mode=self.mode * factor,
            high=self.high * factor,
            unit=unit,
        )


class Constant(Distribution):
    """Degenerate law: always ``value``."""

    type: Literal[DistributionType.CONSTANT] = DistributionType.CONSTANT
    value: Positive

    def cdf(self, t: float) -> float:
        """Return a step function at ``value``."""
        return 1.0 if t >= self.value else 0.0

    def pdf(self, t: float) -> float:
        """Return ``inf`` at ``value`` (Dirac delta), else 0."""
        return math.inf if t == self.value else 0.0

    def quantile(self, p: float) -> float:
        """Return ``value``."""
        _check_probability(p)
        return self.value

    def mean(self) -> float:
        """Return ``value``."""
        return self.value

    def variance(self) -> float:
        """Return zero."""
        return 0.0

    def sample_many(self, rng: np.random.Generator, size: int) -> Floats:
        """Return ``size`` copies of ``value`` (``rng`` is unused)."""
        return np.full(size, self.value, dtype=np.float64)

    def _rescaled(self, factor: float, unit: TimeUnit) -> "Constant":
        return Constant(value=self.value * factor, unit=unit)


class Empirical(Distribution):
    """Empirical law defined by observed values (bootstrap)."""

    type: Literal[DistributionType.EMPIRICAL] = DistributionType.EMPIRICAL
    samples: tuple[NonNegative, ...] = Field(
        min_length=1, max_length=MAX_EMPIRICAL_SAMPLES
    )

    @model_validator(mode="after")
    def _check_samples(self) -> "Empirical":
        if max(self.samples) <= 0:
            raise ValueError("at least one sample must be > 0")
        if list(self.samples) != sorted(self.samples):
            object.__setattr__(self, "samples", tuple(sorted(self.samples)))
        return self

    def cdf(self, t: float) -> float:
        """Return the empirical CDF."""
        return bisect_right(self.samples, t) / len(self.samples)

    def pdf(self, t: float) -> float:
        """Not defined for a discrete empirical law."""
        raise UnsupportedOperationError(
            "pdf is not defined for EMPIRICAL distribution"
        )

    def quantile(self, p: float) -> float:
        """Return the inverse empirical CDF."""
        _check_probability(p)
        n = len(self.samples)
        index = min(max(math.ceil(p * n) - 1, 0), n - 1)
        return self.samples[index]

    def mean(self) -> float:
        """Return the sample mean."""
        return math.fsum(self.samples) / len(self.samples)

    def variance(self) -> float:
        """Return the (population) sample variance."""
        m = self.mean()
        return math.fsum((x - m) ** 2 for x in self.samples) / len(
            self.samples
        )

    def sample_many(self, rng: np.random.Generator, size: int) -> Floats:
        """Resample the observed values with replacement."""
        data = np.asarray(self.samples, dtype=np.float64)
        return rng.choice(data, size=size, replace=True)

    def _rescaled(self, factor: float, unit: TimeUnit) -> "Empirical":
        return Empirical(
            samples=tuple(x * factor for x in self.samples), unit=unit
        )


DistributionSpec = Annotated[
    Exponential
    | Weibull
    | Lognormal
    | Normal
    | Gamma
    | LogLogistic
    | Uniform
    | Triangular
    | Constant
    | Empirical,
    Field(discriminator="type"),
]

_ADAPTER: TypeAdapter[DistributionSpec] = TypeAdapter(DistributionSpec)


def parse_distribution(data: object) -> Distribution:
    """Build a distribution from a ``dict`` with a ``type`` key."""
    return _ADAPTER.validate_python(data)

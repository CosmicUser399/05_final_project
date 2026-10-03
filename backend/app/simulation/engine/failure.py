"""Failure time generation and competing-risk selection."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import numpy as np

from app.domain.reliability.compiled import CompiledFailureMode
from app.domain.reliability.distributions import Distribution
from app.domain.reliability.distributions import Exponential


@dataclass(frozen=True, slots=True)
class SampledFailure:
    """One sampled failure occurrence for a failure mode."""

    failure_mode_id: UUID
    equipment_id: UUID
    delay_minutes: float
    absolute_time: float


class FailureGenerator:
    """Sample time-to-failure for a single failure mode.

    ``virtual_age`` supports ABAO / partial renewal: the drawn lifetime
    is conditioned to exceed the current age (rejection sampling).
    ``rate_multiplier`` scales Exponential ``lambda`` (and, for other
    laws, shortens the sample by dividing by the multiplier).
    """

    STREAM_BASE = 1000

    def sample_delay(
        self,
        mode: CompiledFailureMode,
        rng: np.random.Generator,
        *,
        virtual_age: float = 0.0,
        rate_multiplier: float = 1.0,
    ) -> float:
        """Return delay from now until failure (minutes)."""
        dist = mode.distribution.to_minutes()
        multiplier = max(rate_multiplier, 1e-12)
        if isinstance(dist, Exponential):
            scaled = Exponential(
                lambda_=dist.lambda_ * multiplier,
                unit=dist.unit,
            )
            return float(scaled.sample(rng))
        lifetime = self._sample_lifetime(dist, rng, virtual_age)
        delay = (lifetime - virtual_age) / multiplier
        return max(delay, 0.0)

    def _sample_lifetime(
        self,
        dist: Distribution,
        rng: np.random.Generator,
        virtual_age: float,
    ) -> float:
        """Sample a lifetime strictly greater than ``virtual_age``."""
        if virtual_age <= 0.0:
            return float(dist.sample(rng))
        # Rejection sampling; exponential path is handled separately.
        for _ in range(10_000):
            sample = float(dist.sample(rng))
            if sample > virtual_age:
                return sample
        # Fallback: force a tiny residual life.
        return virtual_age + 1e-6


class CompetingRiskModel:
    """Select the earliest failure among active modes of one asset."""

    def __init__(self, generator: FailureGenerator | None = None) -> None:
        """Create a competing-risk selector."""
        self._generator = generator or FailureGenerator()

    def next_failure(
        self,
        modes: list[CompiledFailureMode],
        now: float,
        rngs: dict[UUID, np.random.Generator],
        *,
        virtual_age: float = 0.0,
        rate_multiplier: float = 1.0,
        eliminated: set[UUID] | None = None,
    ) -> SampledFailure | None:
        """Return the earliest competing failure, or ``None``."""
        skipped = eliminated or set()
        best: SampledFailure | None = None
        # Stable order by failure-mode id for determinism.
        ordered = sorted(modes, key=lambda m: str(m.id))
        for mode in ordered:
            if mode.id in skipped:
                continue
            rng = rngs[mode.id]
            delay = self._generator.sample_delay(
                mode,
                rng,
                virtual_age=virtual_age,
                rate_multiplier=rate_multiplier,
            )
            absolute = now + delay
            candidate = SampledFailure(
                failure_mode_id=mode.id,
                equipment_id=mode.equipment_id,
                delay_minutes=delay,
                absolute_time=absolute,
            )
            if best is None or (
                candidate.absolute_time,
                str(candidate.failure_mode_id),
            ) < (best.absolute_time, str(best.failure_mode_id)):
                best = candidate
        return best

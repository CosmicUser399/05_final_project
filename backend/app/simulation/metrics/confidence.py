"""Confidence intervals for Monte Carlo aggregates."""

from __future__ import annotations

import math

import numpy as np
from scipy import stats

from app.domain.simulation.aggregates import MetricSummary
from app.domain.simulation.aggregates import ProportionSummary


def wilson_interval(
    successes: int,
    trials: int,
    confidence: float = 0.95,
) -> ProportionSummary:
    """Wilson score interval for a binomial proportion."""
    if trials <= 0:
        return ProportionSummary(
            value=None,
            successes=0,
            trials=0,
            method="wilson",
        )
    z = float(stats.norm.ppf(1.0 - (1.0 - confidence) / 2.0))
    phat = successes / trials
    denom = 1.0 + z * z / trials
    centre = (phat + z * z / (2.0 * trials)) / denom
    margin = (
        z
        * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * trials)) / trials)
        / denom
    )
    return ProportionSummary(
        value=phat,
        successes=successes,
        trials=trials,
        ci_low=max(0.0, centre - margin),
        ci_high=min(1.0, centre + margin),
        method="wilson",
    )


def clopper_pearson_interval(
    successes: int,
    trials: int,
    confidence: float = 0.95,
) -> ProportionSummary:
    """Exact Clopper-Pearson interval (fallback for tiny N)."""
    if trials <= 0:
        return ProportionSummary(
            value=None,
            successes=0,
            trials=0,
            method="clopper_pearson",
        )
    alpha = 1.0 - confidence
    phat = successes / trials
    if successes == 0:
        low = 0.0
    else:
        low = float(
            stats.beta.ppf(alpha / 2.0, successes, trials - successes + 1)
        )
    if successes == trials:
        high = 1.0
    else:
        high = float(
            stats.beta.ppf(
                1.0 - alpha / 2.0,
                successes + 1,
                trials - successes,
            )
        )
    return ProportionSummary(
        value=phat,
        successes=successes,
        trials=trials,
        ci_low=low,
        ci_high=high,
        method="clopper_pearson",
    )


def proportion_interval(
    successes: int,
    trials: int,
    confidence: float = 0.95,
    *,
    exact_below: int = 40,
) -> ProportionSummary:
    """Wilson for larger N; Clopper-Pearson for small samples."""
    if trials < exact_below:
        return clopper_pearson_interval(successes, trials, confidence)
    return wilson_interval(successes, trials, confidence)


def summarize_numeric(
    values: list[float],
    confidence: float = 0.95,
) -> MetricSummary:
    """Mean/median/percentiles and a Student-t CI for the mean."""
    if not values:
        return MetricSummary(sample_size=0)
    arr = np.asarray(values, dtype=np.float64)
    n = int(arr.size)
    mean = float(np.mean(arr))
    median = float(np.median(arr))
    p5, p50, p95 = (float(x) for x in np.percentile(arr, [5, 50, 95]))
    ci_low: float | None = None
    ci_high: float | None = None
    if n >= 2:
        sem = float(stats.sem(arr))
        if sem > 0 and math.isfinite(sem):
            half = float(
                sem * stats.t.ppf(1.0 - (1.0 - confidence) / 2.0, df=n - 1)
            )
            ci_low = mean - half
            ci_high = mean + half
        else:
            ci_low = mean
            ci_high = mean
    elif n == 1:
        ci_low = mean
        ci_high = mean
    return MetricSummary(
        mean=mean,
        median=median,
        p5=p5,
        p50=p50,
        p95=p95,
        ci_low=ci_low,
        ci_high=ci_high,
        sample_size=n,
    )


def percentile(values: list[float], q: float) -> float | None:
    """Return the ``q`` percentile in [0, 100], or None if empty."""
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=np.float64), q))

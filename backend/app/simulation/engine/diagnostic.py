"""Lazy diagnostic detection inside a PF window."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import numpy as np

from app.domain.reliability.compiled import CompiledDiagnosticTask
from app.simulation.engine.pf_scheduler import PFWindow


@dataclass(frozen=True, slots=True)
class DetectionResult:
    """Outcome of lazy checks inside ``[T_pf, T_f)``."""

    detected: bool
    detection_time: float | None
    checks_in_window: int
    detecting_task_id: UUID | None


class DiagnosticEngine:
    """Evaluate detection without enqueueing periodic checks.

    For each diagnostic task linked to the failure mode, the check
    grid ``k * interval`` (``k = 1, 2, ...``) that falls inside
    ``[T_pf, T_f)`` is tested with Bernoulli(``p_detect``). The
    earliest successful check wins.
    """

    def evaluate_detection(
        self,
        window: PFWindow,
        tasks: list[CompiledDiagnosticTask],
        rng: np.random.Generator,
    ) -> DetectionResult:
        """Return whether the pending failure is detected in time."""
        if window.t_potential is None:
            return DetectionResult(
                detected=False,
                detection_time=None,
                checks_in_window=0,
                detecting_task_id=None,
            )
        t_pf = window.t_potential
        t_f = window.t_failure
        relevant = [
            task
            for task in tasks
            if task.failure_mode_id == window.failure_mode_id
        ]
        relevant.sort(key=lambda t: str(t.id))
        best_time: float | None = None
        best_task: UUID | None = None
        checks = 0
        for task in relevant:
            interval = task.interval_minutes
            if interval <= 0:
                continue
            # First grid point strictly after 0 that is >= t_pf.
            k_start = int(t_pf // interval)
            if k_start * interval < t_pf:
                k_start += 1
            if k_start <= 0:
                k_start = 1
            k = k_start
            while True:
                check_time = k * interval
                if check_time >= t_f:
                    break
                if check_time >= t_pf:
                    checks += 1
                    if rng.random() < task.detection_probability:
                        if best_time is None or check_time < best_time:
                            best_time = check_time
                            best_task = task.id
                        break
                k += 1
        return DetectionResult(
            detected=best_time is not None,
            detection_time=best_time,
            checks_in_window=checks,
            detecting_task_id=best_task,
        )

    def count_false_positives(
        self,
        tasks: list[CompiledDiagnosticTask],
        horizon: float,
        rng: np.random.Generator,
        *,
        excluded_windows: list[tuple[float, float]] | None = None,
    ) -> int:
        """Count FP checks on the grid outside PF windows.

        ``excluded_windows`` are half-open ``[start, end)`` intervals
        already covered by real PF detection logic.
        """
        blocked = excluded_windows or []
        total = 0
        ordered = sorted(tasks, key=lambda t: str(t.id))
        for task in ordered:
            p_fp = task.false_positive_probability
            if p_fp <= 0.0 or task.interval_minutes <= 0:
                continue
            interval = task.interval_minutes
            k = 1
            while True:
                check_time = k * interval
                if check_time >= horizon:
                    break
                in_pf = any(
                    start <= check_time < end for start, end in blocked
                )
                if not in_pf and rng.random() < p_fp:
                    total += 1
                k += 1
        return total

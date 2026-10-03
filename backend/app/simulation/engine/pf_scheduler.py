"""PF-interval scheduling: ``T_pf = T_f - PF``."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.reliability.compiled import CompiledFailureMode
from app.domain.reliability.pf import potential_failure_time


@dataclass(frozen=True, slots=True)
class PFWindow:
    """Potential-failure window for one sampled failure."""

    failure_mode_id: UUID
    equipment_id: UUID
    t_failure: float
    t_potential: float | None
    pf_minutes: float | None


class PFIntervalScheduler:
    """Compute PF onset for a sampled functional failure time."""

    def window(
        self,
        mode: CompiledFailureMode,
        t_failure: float,
    ) -> PFWindow:
        """Return the PF window for ``mode`` failing at ``t_failure``."""
        pf = mode.pf_interval_minutes
        if not mode.is_detectable or pf is None or pf <= 0.0:
            return PFWindow(
                failure_mode_id=mode.id,
                equipment_id=mode.equipment_id,
                t_failure=t_failure,
                t_potential=None,
                pf_minutes=None,
            )
        onset = potential_failure_time(t_failure, pf)
        return PFWindow(
            failure_mode_id=mode.id,
            equipment_id=mode.equipment_id,
            t_failure=t_failure,
            t_potential=onset,
            pf_minutes=pf,
        )

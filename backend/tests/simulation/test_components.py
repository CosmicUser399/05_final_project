"""Unit tests for failure, PF, diagnostic and state-machine pieces."""

import numpy as np

from app.domain.simulation.states import EquipmentState
from app.simulation.engine import CompetingRiskModel
from app.simulation.engine import DiagnosticEngine
from app.simulation.engine import EquipmentStateMachine
from app.simulation.engine import FailureGenerator
from app.simulation.engine import PFIntervalScheduler
from app.simulation.engine.pf_scheduler import PFWindow
from tests.simulation.factories import EQ_ID
from tests.simulation.factories import FM_ID
from tests.simulation.factories import competing_risks_model
from tests.simulation.factories import pf_detection_model


def test_pf_scheduler_golden_window() -> None:
    model = pf_detection_model()
    mode = model.failure_modes[0]
    window = PFIntervalScheduler().window(mode, t_failure=1000.0 * 60.0)
    assert window.t_potential == 900.0 * 60.0
    assert window.pf_minutes == 100.0 * 60.0


def test_pf_negative_onset_not_modelled() -> None:
    model = pf_detection_model(t_f_hours=50.0, pf_hours=100.0)
    mode = model.failure_modes[0]
    window = PFIntervalScheduler().window(mode, t_failure=50.0 * 60.0)
    assert window.t_potential is None


def test_lazy_detection_at_950h_with_p1() -> None:
    model = pf_detection_model(
        t_f_hours=1000.0,
        pf_hours=100.0,
        diag_interval_hours=50.0,
        p_detect=1.0,
    )
    mode = model.failure_modes[0]
    window = PFIntervalScheduler().window(mode, 1000.0 * 60.0)
    result = DiagnosticEngine().evaluate_detection(
        window,
        list(model.diagnostic_tasks),
        np.random.default_rng(0),
    )
    assert result.detected is True
    # Interval 50 h: first grid point in [900, 1000) is 900 h.
    assert result.detection_time == 900.0 * 60.0


def test_missed_detection_with_p0() -> None:
    model = pf_detection_model(p_detect=0.0)
    mode = model.failure_modes[0]
    window = PFIntervalScheduler().window(mode, 1000.0 * 60.0)
    result = DiagnosticEngine().evaluate_detection(
        window,
        list(model.diagnostic_tasks),
        np.random.default_rng(0),
    )
    assert result.detected is False
    assert result.checks_in_window > 0


def test_competing_risks_picks_earliest() -> None:
    model = competing_risks_model()
    rngs = {
        mode.id: np.random.default_rng(i)
        for i, mode in enumerate(model.failure_modes)
    }
    sample = CompetingRiskModel(FailureGenerator()).next_failure(
        list(model.failure_modes),
        now=0.0,
        rngs=rngs,
    )
    assert sample is not None
    assert sample.failure_mode_id == FM_ID
    assert sample.absolute_time == 100.0 * 60.0


def test_state_machine_allows_cm_path() -> None:
    machine = EquipmentStateMachine(EQ_ID)
    machine.transition(EquipmentState.FAILED)
    machine.transition(EquipmentState.DIAGNOSIS)
    machine.transition(EquipmentState.WAITING_FOR_RESOURCE)
    machine.transition(EquipmentState.WAITING_FOR_SPARE)
    machine.transition(EquipmentState.MAINTENANCE)
    machine.transition(EquipmentState.RESTORING)
    machine.transition(EquipmentState.UP)
    assert machine.state is EquipmentState.UP


def test_detection_result_without_pf_window() -> None:
    window = PFWindow(
        failure_mode_id=FM_ID,
        equipment_id=EQ_ID,
        t_failure=100.0,
        t_potential=None,
        pf_minutes=None,
    )
    result = DiagnosticEngine().evaluate_detection(
        window, [], np.random.default_rng(0)
    )
    assert result.detected is False

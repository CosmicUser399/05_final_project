"""Picklable single-trial helper for process pools."""

from __future__ import annotations

from typing import Any

from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiled import ScenarioOverlay
from app.domain.simulation.config import SimulationConfiguration
from app.simulation.engine.simulation import SimulationEngine


def run_trial_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Deserialize inputs, run one trial, return JSON-ready result.

    Must stay a top-level function so ``ProcessPoolExecutor`` can
    pickle it on Windows (spawn).
    """
    model = CompiledModel.model_validate(payload["model"])
    scenario_raw = payload.get("scenario")
    scenario = (
        None
        if scenario_raw is None
        else ScenarioOverlay.model_validate(scenario_raw)
    )
    configuration = SimulationConfiguration.model_validate(
        payload["configuration"]
    )
    seed = int(payload["seed"])
    result = SimulationEngine().run(
        model,
        scenario,
        configuration,
        seed=seed,
    )
    return result.model_dump(mode="json")

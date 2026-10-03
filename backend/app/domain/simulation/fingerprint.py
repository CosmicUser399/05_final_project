"""Deterministic hashes for simulation traceability."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.domain.simulation.config import SimulationConfiguration


def _stable_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def configuration_hash(configuration: SimulationConfiguration) -> str:
    """SHA-256 of configuration excluding per-trial ``run_id``."""
    payload = configuration.configuration_hash_payload()
    payload.pop("run_id", None)
    digest = hashlib.sha256(_stable_json(payload).encode("utf-8"))
    return digest.hexdigest()


def simulation_fingerprint(
    *,
    model_hash: str,
    scenario_hash: str,
    configuration_hash_value: str,
    seed: int,
    software_version: str,
) -> str:
    """SHA-256 of model/scenario/config/seed/software_version."""
    payload = {
        "model_hash": model_hash,
        "scenario_hash": scenario_hash,
        "configuration_hash": configuration_hash_value,
        "seed": seed,
        "software_version": software_version,
    }
    digest = hashlib.sha256(_stable_json(payload).encode("utf-8"))
    return digest.hexdigest()

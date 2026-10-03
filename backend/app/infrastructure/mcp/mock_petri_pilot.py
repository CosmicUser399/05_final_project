"""In-process mock of Petri-Pilot for tests (no network)."""

from __future__ import annotations

import json
from typing import Any

from app.application.ports import PetriPilotResult
from app.application.ports import PetriPilotStatus
from app.infrastructure.mcp.whitelist import PETRI_PILOT_WHITELIST


class MockPetriPilotProvider:
    """Deterministic PetriPilotPort implementation for unit tests."""

    def __init__(self, *, version: str = "mock-1.0") -> None:
        """Store mock metadata."""
        self._version = version
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def validate(self, model_json: str) -> PetriPilotResult:
        """Return success when the model parses and has elements."""
        return self._run("petri_validate", {"model": model_json})

    def analyze(
        self,
        model_json: str,
        *,
        full: bool = False,
    ) -> PetriPilotResult:
        """Return a bounded/live analysis payload."""
        return self._run(
            "petri_analyze",
            {"model": model_json, "full": full},
        )

    def verify(
        self,
        model_json: str,
        properties: list[str],
        *,
        max_states: int | None = None,
    ) -> PetriPilotResult:
        """Return proved verdicts for requested properties."""
        args: dict[str, Any] = {
            "model": model_json,
            "properties": json.dumps(properties),
        }
        if max_states is not None:
            args["max_states"] = str(max_states)
        return self._run("petri_verify", args)

    def invariants(self, model_json: str) -> PetriPilotResult:
        """Return a trivial conservation law."""
        return self._run("petri_invariants", {"model": model_json})

    def simulate(
        self,
        model_json: str,
        *,
        transitions: list[str] | None = None,
    ) -> PetriPilotResult:
        """Echo the requested firing sequence."""
        args: dict[str, Any] = {"model": model_json}
        if transitions is not None:
            args["transitions"] = json.dumps(transitions)
        return self._run("petri_simulate", args)

    def conformance(
        self,
        model_json: str,
        log_json: str,
        *,
        include_traces: bool = True,
    ) -> PetriPilotResult:
        """Return perfect fitness when the log is non-empty."""
        return self._run(
            "petri_conformance",
            {
                "model": model_json,
                "log": log_json,
                "include_traces": include_traces,
            },
        )

    def diff(self, model_a_json: str, model_b_json: str) -> PetriPilotResult:
        """Return a no-change diff for identical payloads."""
        return self._run(
            "petri_diff",
            {"model_a": model_a_json, "model_b": model_b_json},
        )

    def canonical(self, model_json: str) -> PetriPilotResult:
        """Return a stable mock canonical id."""
        return self._run("petri_canonical", {"model": model_json})

    def _run(self, tool: str, args: dict[str, Any]) -> PetriPilotResult:
        self.calls.append((tool, args))
        if tool not in PETRI_PILOT_WHITELIST:
            return PetriPilotResult(
                status=PetriPilotStatus.FAILURE,
                tool=tool,
                message=f"tool {tool!r} is not whitelisted",
            )
        model = args.get("model") or args.get("model_a")
        try:
            parsed = json.loads(str(model))
        except (TypeError, json.JSONDecodeError):
            return PetriPilotResult(
                status=PetriPilotStatus.VALIDATION_ERROR,
                tool=tool,
                message="model is not valid JSON",
            )
        if not isinstance(parsed, dict):
            return PetriPilotResult(
                status=PetriPilotStatus.VALIDATION_ERROR,
                tool=tool,
                message="model JSON must be an object",
            )
        places = parsed.get("places") or []
        transitions = parsed.get("transitions") or []
        arcs = parsed.get("arcs") or []
        if tool == "petri_validate":
            valid = bool(places) and bool(transitions) and bool(arcs)
            return PetriPilotResult(
                status=PetriPilotStatus.SUCCESS,
                tool=tool,
                petri_pilot_version=self._version,
                data={
                    "valid": valid,
                    "analysis": {
                        "bounded": True,
                        "live": True,
                        "has_deadlocks": False,
                        "state_count": max(1, len(places)),
                    },
                    "p_invariants": [],
                    "t_invariants": [],
                },
            )
        if tool == "petri_analyze":
            return PetriPilotResult(
                status=PetriPilotStatus.SUCCESS,
                tool=tool,
                petri_pilot_version=self._version,
                data={
                    "valid": True,
                    "analysis": {
                        "bounded": True,
                        "live": True,
                        "has_deadlocks": False,
                        "state_count": max(1, len(places)),
                    },
                },
            )
        if tool == "petri_verify":
            props = json.loads(str(args.get("properties", "[]")))
            verdicts = [
                {
                    "property": {"kind": p, "name": p},
                    "status": "proved",
                    "method": "mock",
                }
                for p in props
            ]
            return PetriPilotResult(
                status=PetriPilotStatus.SUCCESS,
                tool=tool,
                petri_pilot_version=self._version,
                data={
                    "verdicts": verdicts,
                    "proved": len(verdicts),
                    "refuted": 0,
                    "unknown": 0,
                    "ok": True,
                },
            )
        if tool == "petri_invariants":
            return PetriPilotResult(
                status=PetriPilotStatus.SUCCESS,
                tool=tool,
                petri_pilot_version=self._version,
                data={"laws": [], "tInvariants": [], "siphons": {}},
            )
        if tool == "petri_simulate":
            fired = json.loads(str(args.get("transitions", "[]")))
            return PetriPilotResult(
                status=PetriPilotStatus.SUCCESS,
                tool=tool,
                petri_pilot_version=self._version,
                data={"success": True, "fired": fired},
            )
        if tool == "petri_conformance":
            log = json.loads(str(args.get("log", "[]")))
            cases = {row.get("case") for row in log if isinstance(row, dict)}
            return PetriPilotResult(
                status=PetriPilotStatus.SUCCESS,
                tool=tool,
                petri_pilot_version=self._version,
                data={
                    "fitness": 1.0 if log else 0.0,
                    "precision": 1.0,
                    "f_score": 1.0 if log else 0.0,
                    "cases": len(cases),
                    "fitting_traces": len(cases),
                },
            )
        if tool == "petri_diff":
            same = args.get("model_a") == args.get("model_b")
            return PetriPilotResult(
                status=PetriPilotStatus.SUCCESS,
                tool=tool,
                petri_pilot_version=self._version,
                data={"has_changes": not same},
            )
        digest = f"mock-canonical-{len(str(model))}"
        return PetriPilotResult(
            status=PetriPilotStatus.SUCCESS,
            tool=tool,
            petri_pilot_version=self._version,
            data={"canonical_id": digest},
        )

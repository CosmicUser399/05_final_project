"""Application ports (interfaces) for external adapters."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class SimulationJobRunner(Protocol):
    """Claim, execute and finalize queued simulation jobs."""

    def reclaim_stale(self) -> int:
        """Return stuck active jobs to ``QUEUED``; return count."""

    def claim_next(self) -> UUID | None:
        """Atomically claim one ``QUEUED`` job id, or return None."""

    def heartbeat(self, run_id: UUID) -> None:
        """Refresh heartbeat for an in-flight job."""

    def execute(self, run_id: UUID) -> None:
        """Validate, run Monte Carlo, persist results for one job."""

    def process_once(self) -> bool:
        """Reclaim, claim and execute one job. Return True if worked."""


class PetriPilotStatus(StrEnum):
    """Typed outcome of a Petri-Pilot call."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"
    EXTERNAL_ERROR = "external_error"


class PetriPilotResult(BaseModel):
    """Normalized adapter response (no secrets)."""

    model_config = ConfigDict(frozen=True)

    status: PetriPilotStatus
    tool: str
    data: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None
    petri_pilot_version: str | None = None


class PetriPilotPort(Protocol):
    """Port for formal Petri-Pilot operations (whitelist only)."""

    def validate(self, model_json: str) -> PetriPilotResult:
        """Structural validate via ``petri_validate``."""

    def analyze(
        self,
        model_json: str,
        *,
        full: bool = False,
    ) -> PetriPilotResult:
        """Behavioral analysis via ``petri_analyze``."""

    def verify(
        self,
        model_json: str,
        properties: list[str],
        *,
        max_states: int | None = None,
    ) -> PetriPilotResult:
        """Property check via ``petri_verify``."""

    def invariants(self, model_json: str) -> PetriPilotResult:
        """P/T-invariants and siphons via ``petri_invariants``."""

    def simulate(
        self,
        model_json: str,
        *,
        transitions: list[str] | None = None,
    ) -> PetriPilotResult:
        """Step simulation via ``petri_simulate``."""

    def conformance(
        self,
        model_json: str,
        log_json: str,
        *,
        include_traces: bool = True,
    ) -> PetriPilotResult:
        """Replay log fitness/precision via ``petri_conformance``."""

    def diff(self, model_a_json: str, model_b_json: str) -> PetriPilotResult:
        """Structural diff via ``petri_diff``."""

    def canonical(self, model_json: str) -> PetriPilotResult:
        """Isomorphism-invariant id via ``petri_canonical``."""

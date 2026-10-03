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


class ExternalCallStatus(StrEnum):
    """Typed outcome of AI / Fabricate adapter calls."""

    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"
    EXTERNAL_ERROR = "external_error"


class AiCompletionResult(BaseModel):
    """Normalized OpenAI/structured-output response (no secrets)."""

    model_config = ConfigDict(frozen=True)

    status: ExternalCallStatus
    model: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class AIProvider(Protocol):
    """Port for structured LLM completions."""

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> AiCompletionResult:
        """Return a JSON object matching the named schema contract."""

    def interpret_plant_description(
        self,
        description: str,
    ) -> AiCompletionResult:
        """Extract plant type, capacity and a generation brief."""


class FabricateCallResult(BaseModel):
    """Normalized Fabricate adapter response (no secrets)."""

    model_config = ConfigDict(frozen=True)

    status: ExternalCallStatus
    tool: str
    data: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None


class FabricateProvider(Protocol):
    """Port for Fabricate MCP whitelist operations."""

    def list_conversation_options(self) -> FabricateCallResult:
        """List models / effort / validators before start."""

    def create_upload(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str = "application/json",
    ) -> FabricateCallResult:
        """Upload a schema/spec file; returns upload_id."""

    def start_conversation(
        self,
        *,
        message: str,
        upload_ids: list[str],
        model: str | None = None,
        mode: str = "autonomous",
        approach: str = "dataset",
    ) -> FabricateCallResult:
        """Start async generation; returns conversation_id."""

    def get_conversation_status(
        self,
        conversation_id: str,
    ) -> FabricateCallResult:
        """Poll conversation status (includes poll_after_ms)."""

    def get_conversation_result(
        self,
        conversation_id: str,
    ) -> FabricateCallResult:
        """Fetch final artifacts / download links."""

    def download_conversation_file(
        self,
        *,
        conversation_id: str,
        file_id: str,
    ) -> FabricateCallResult:
        """Download an artifact; data.bytes holds content."""

    def send_message(
        self,
        conversation_id: str,
        message: str,
        *,
        upload_ids: list[str] | None = None,
    ) -> FabricateCallResult:
        """Refine an existing conversation."""

    def stop_conversation(self, conversation_id: str) -> FabricateCallResult:
        """Cancel a running conversation."""

    def retry_conversation(self, conversation_id: str) -> FabricateCallResult:
        """Retry a failed turn in place."""


class EquipmentProposalResult(BaseModel):
    """Result of an equipment proposal provider."""

    model_config = ConfigDict(frozen=True)

    status: ExternalCallStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    message: str | None = None
    conversation_id: str | None = None
    ai_model: str | None = None
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EquipmentProposalProvider(Protocol):
    """Unified port: description -> proposed equipment structure."""

    def generate_proposal(
        self,
        description: str,
        *,
        schema_version: str = "1",
    ) -> EquipmentProposalResult:
        """Generate a proposal payload (structure, not Domain DB)."""

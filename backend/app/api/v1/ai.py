"""REST + SSE routes for AI/Fabricate generation and proposals."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pydantic import Field

from app.api.deps import AiAnalystServiceDep
from app.api.deps import AiGenerationServiceDep
from app.api.deps import SettingsDep
from app.application.analyst.context import AnalystChatContext
from app.application.analyst.context import AnalystChatRequest
from app.application.analyst.context import AnalystChatTurn
from app.domain.ai.status import TERMINAL_GENERATION_STATUSES

router = APIRouter(prefix="/ai", tags=["ai"])


class GenerateSystemRequest(BaseModel):
    """Start equipment database generation."""

    description: str = Field(min_length=1, max_length=5000)
    provider: str = Field(default="openai", max_length=32)
    system_id: UUID | None = None
    version_id: UUID | None = None
    process_inline: bool = False


class RefineJobRequest(BaseModel):
    """Refine a Fabricate conversation."""

    message: str = Field(min_length=1, max_length=5000)


class ProposalItemDecisionRequest(BaseModel):
    """Accept / edit / reject one proposal row."""

    decision: str = Field(min_length=1, max_length=32)
    edited_payload: dict[str, Any] | None = None


class ProposalCommitRequest(BaseModel):
    """Commit accepted proposal items into Domain DB."""

    system_name: str | None = Field(default=None, max_length=200)
    create_system: bool = True


class AnalystContextBody(BaseModel):
    """Optional ids scoping analyst tool calls."""

    system_id: UUID | None = None
    version_id: UUID | None = None
    scenario_id: UUID | None = None
    simulation_run_id: UUID | None = None
    equipment_id: UUID | None = None


class AnalystChatTurnBody(BaseModel):
    """Prior dialog turn sent by the UI."""

    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=8000)


class AnalystChatBody(BaseModel):
    """User question for AI Analyst."""

    message: str = Field(min_length=1, max_length=4000)
    context: AnalystContextBody = Field(
        default_factory=AnalystContextBody,
    )
    history: list[AnalystChatTurnBody] = Field(
        default_factory=list,
        max_length=40,
    )


@router.post("/generate-system", status_code=status.HTTP_202_ACCEPTED)
def generate_system(
    body: GenerateSystemRequest,
    service: AiGenerationServiceDep,
) -> dict[str, Any]:
    """Enqueue equipment generation (OpenAI or Fabricate)."""
    return service.start_generation(
        description=body.description,
        provider=body.provider,
        system_id=body.system_id,
        version_id=body.version_id,
        process_inline=body.process_inline,
    )


@router.get("/generation-jobs/{job_id}")
def get_generation_job(
    job_id: UUID,
    service: AiGenerationServiceDep,
) -> dict[str, Any]:
    """Return generation job status."""
    return service.get_job(job_id)


@router.post("/generation-jobs/{job_id}/cancel")
def cancel_generation_job(
    job_id: UUID,
    service: AiGenerationServiceDep,
) -> dict[str, Any]:
    """Cancel a queued or running generation job."""
    return service.cancel_job(job_id)


@router.post("/generation-jobs/{job_id}/refine")
def refine_generation_job(
    job_id: UUID,
    body: RefineJobRequest,
    service: AiGenerationServiceDep,
) -> dict[str, Any]:
    """Send a refine message to Fabricate and re-queue the job."""
    return service.refine_job(job_id, body.message)


@router.get("/generation-jobs/{job_id}/stream")
async def stream_generation_job(
    job_id: UUID,
    service: AiGenerationServiceDep,
    settings: SettingsDep,
) -> StreamingResponse:
    """SSE progress stream until a terminal generation status."""

    async def events() -> AsyncIterator[str]:
        poll = settings.generation_sse_poll_seconds
        while True:
            row = await asyncio.to_thread(service.get_job, job_id)
            payload = json.dumps(row, default=str)
            yield f"event: progress\ndata: {payload}\n\n"
            status_value = str(row["status"])
            if status_value in {s.value for s in TERMINAL_GENERATION_STATUSES}:
                yield f"event: done\ndata: {payload}\n\n"
                break
            await asyncio.sleep(poll)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/proposals/{proposal_id}")
def get_proposal(
    proposal_id: UUID,
    service: AiGenerationServiceDep,
) -> dict[str, Any]:
    """Return a proposal with review items."""
    return service.get_proposal(proposal_id)


@router.post("/proposals/items/{item_id}/decide")
def decide_proposal_item(
    item_id: UUID,
    body: ProposalItemDecisionRequest,
    service: AiGenerationServiceDep,
) -> dict[str, Any]:
    """Set accept/edit/reject for one proposal item."""
    return service.decide_item(
        item_id,
        decision=body.decision,
        edited_payload=body.edited_payload,
    )


@router.post("/proposals/{proposal_id}/commit")
def commit_proposal(
    proposal_id: UUID,
    body: ProposalCommitRequest,
    service: AiGenerationServiceDep,
) -> dict[str, Any]:
    """Commit accepted items through domain services."""
    return service.commit_proposal(
        proposal_id,
        system_name=body.system_name,
        create_system=body.create_system,
    )


@router.post("/chat")
def analyst_chat(
    body: AnalystChatBody,
    service: AiAnalystServiceDep,
) -> dict[str, Any]:
    """Answer a question using typed tools and grounded synthesis."""
    request = AnalystChatRequest(
        message=body.message,
        context=AnalystChatContext.model_validate(body.context.model_dump()),
        history=[
            AnalystChatTurn.model_validate(row.model_dump())
            for row in body.history
        ],
    )
    response = service.chat(request)
    return response.model_dump(mode="json")


@router.post("/chat/stream")
async def analyst_chat_stream(
    body: AnalystChatBody,
    service: AiAnalystServiceDep,
) -> StreamingResponse:
    """SSE stream of analyst progress and final grounded answer."""
    request = AnalystChatRequest(
        message=body.message,
        context=AnalystChatContext.model_validate(body.context.model_dump()),
        history=[
            AnalystChatTurn.model_validate(row.model_dump())
            for row in body.history
        ],
    )

    async def events() -> AsyncIterator[str]:
        iterator = await asyncio.to_thread(
            lambda: list(service.iter_sse_events(request))
        )
        for event_name, payload in iterator:
            data = json.dumps(payload, default=str)
            yield f"event: {event_name}\ndata: {data}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

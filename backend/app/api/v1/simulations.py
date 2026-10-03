"""REST + SSE routes for Monte Carlo simulation jobs."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import Header
from fastapi import Query
from fastapi import status
from fastapi.responses import StreamingResponse

from app.api.deps import SettingsDep
from app.api.deps import SimulationServiceDep
from app.api.v1.schemas import SimulationCreateRequest
from app.api.v1.schemas import SimulationEventsResponse
from app.api.v1.schemas import SimulationResultsResponse
from app.api.v1.schemas import SimulationStatusResponse
from app.domain.simulation.status import TERMINAL_STATUSES

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_simulation(
    body: SimulationCreateRequest,
    service: SimulationServiceDep,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
) -> SimulationStatusResponse:
    """Enqueue a Monte Carlo job (async; processed by worker)."""
    row = service.create(
        version_id=body.version_id,
        configuration=body.to_configuration(),
        idempotency_key=idempotency_key,
        reliability_model_id=body.reliability_model_id,
        seed=body.random_seed,
        scenario_version_id=body.scenario_version_id,
    )
    return SimulationStatusResponse.from_row(row)


@router.get("/{run_id}")
def get_simulation(
    run_id: UUID,
    service: SimulationServiceDep,
) -> SimulationStatusResponse:
    """Return simulation job details."""
    return SimulationStatusResponse.from_row(service.get(run_id))


@router.get("/{run_id}/status")
def get_simulation_status(
    run_id: UUID,
    service: SimulationServiceDep,
) -> SimulationStatusResponse:
    """Return compact job status/progress."""
    return SimulationStatusResponse.from_row(service.get_status(run_id))


@router.get("/{run_id}/results")
def get_simulation_results(
    run_id: UUID,
    service: SimulationServiceDep,
) -> SimulationResultsResponse:
    """Return aggregate metrics for a completed run."""
    return SimulationResultsResponse.model_validate(
        service.get_results(run_id)
    )


@router.get("/{run_id}/events")
def get_simulation_events(
    run_id: UUID,
    service: SimulationServiceDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    event_type: str | None = None,
    equipment_id: UUID | None = None,
) -> SimulationEventsResponse:
    """Return a page of normalized simulation events."""
    return SimulationEventsResponse.model_validate(
        service.get_events(
            run_id,
            offset=offset,
            limit=limit,
            event_type=event_type,
            equipment_id=equipment_id,
        )
    )


@router.post("/{run_id}/cancel")
def cancel_simulation(
    run_id: UUID,
    service: SimulationServiceDep,
) -> SimulationStatusResponse:
    """Cancel a queued or running simulation."""
    return SimulationStatusResponse.from_row(service.cancel(run_id))


@router.get("/{run_id}/stream")
async def stream_simulation_progress(
    run_id: UUID,
    service: SimulationServiceDep,
    settings: SettingsDep,
) -> StreamingResponse:
    """SSE stream of simulation status until a terminal state."""

    async def events() -> AsyncIterator[str]:
        poll = settings.simulation_sse_poll_seconds
        while True:
            row = await asyncio.to_thread(service.get_status, run_id)
            payload = _sse_data(row)
            yield f"event: progress\ndata: {payload}\n\n"
            status_value = str(row["status"])
            if status_value in {s.value for s in TERMINAL_STATUSES}:
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


def _sse_data(row: dict[str, Any]) -> str:
    body = SimulationStatusResponse.from_row(row).model_dump(mode="json")
    return json.dumps(body, default=str)

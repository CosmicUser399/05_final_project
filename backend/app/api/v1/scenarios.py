"""REST routes for scenarios, simulate and compare."""

from __future__ import annotations

from typing import Annotated
from typing import Any
from uuid import UUID

from fastapi import APIRouter
from fastapi import Header
from fastapi import Query
from fastapi import status
from pydantic import BaseModel
from pydantic import Field

from app.api.deps import ScenarioServiceDep
from app.api.v1.schemas import SimulationCreateRequest
from app.api.v1.schemas import SimulationStatusResponse
from app.domain.reliability.compiled import ScenarioChangeType
from app.domain.scenarios.dto import ScenarioChangeInput
from app.domain.scenarios.dto import ScenarioCreateInput
from app.domain.scenarios.dto import ScenarioVersionCreateInput
from app.domain.units import TimeUnit

router = APIRouter(tags=["scenarios"])


class ScenarioChangeRequest(BaseModel):
    """One overlay change in create/update payloads."""

    change_type: ScenarioChangeType
    target_lineage_id: UUID
    parameters: dict[str, Any] = Field(default_factory=dict)


class ScenarioCreateRequest(BaseModel):
    """Body for ``POST /versions/{id}/scenarios``."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    changes: list[ScenarioChangeRequest] = Field(default_factory=list)


class ScenarioVersionCreateRequest(BaseModel):
    """Body for ``POST /scenarios/{id}/versions``."""

    changes: list[ScenarioChangeRequest] = Field(default_factory=list)


class ScenarioSimulateRequest(BaseModel):
    """Body for ``POST /scenarios/{id}/simulate``."""

    reliability_model_id: UUID | None = None
    horizon: float = Field(gt=0)
    horizon_unit: TimeUnit = TimeUnit.HOURS
    number_of_runs: int = Field(default=100, ge=1)
    random_seed: int | None = None
    warmup_period: float = Field(default=0.0, ge=0)
    warmup_unit: TimeUnit = TimeUnit.HOURS
    confidence_level: float = Field(default=0.95, gt=0, lt=1)
    collect_event_log: bool = True
    collect_equipment_metrics: bool = True
    collect_resource_consumption: bool = True
    collect_production_loss: bool = True
    parallel_runs: int = Field(default=1, ge=1)
    event_log_limit: int | None = Field(default=None, ge=1)

    def to_simulation_body(self, version_id: UUID) -> SimulationCreateRequest:
        """Adapt to the shared simulation create schema."""
        return SimulationCreateRequest(
            version_id=version_id,
            reliability_model_id=self.reliability_model_id,
            horizon=self.horizon,
            horizon_unit=self.horizon_unit,
            number_of_runs=self.number_of_runs,
            random_seed=self.random_seed,
            warmup_period=self.warmup_period,
            warmup_unit=self.warmup_unit,
            confidence_level=self.confidence_level,
            collect_event_log=self.collect_event_log,
            collect_equipment_metrics=self.collect_equipment_metrics,
            collect_resource_consumption=(
                self.collect_resource_consumption
            ),
            collect_production_loss=self.collect_production_loss,
            parallel_runs=self.parallel_runs,
            event_log_limit=self.event_log_limit,
        )


def _to_change_inputs(
    items: list[ScenarioChangeRequest],
) -> list[ScenarioChangeInput]:
    return [
        ScenarioChangeInput(
            change_type=item.change_type,
            target_lineage_id=item.target_lineage_id,
            parameters=dict(item.parameters),
        )
        for item in items
    ]


@router.get("/versions/{version_id}/scenarios")
def list_scenarios(
    version_id: UUID,
    service: ScenarioServiceDep,
) -> list[dict[str, Any]]:
    """List scenarios for a system version."""
    return service.list_for_version(version_id)


@router.post(
    "/versions/{version_id}/scenarios",
    status_code=status.HTTP_201_CREATED,
)
def create_scenario(
    version_id: UUID,
    body: ScenarioCreateRequest,
    service: ScenarioServiceDep,
) -> dict[str, Any]:
    """Create a scenario overlay (baseline system version unchanged)."""
    payload = ScenarioCreateInput(
        name=body.name,
        description=body.description,
        changes=_to_change_inputs(body.changes),
    )
    return service.create(version_id, payload)


@router.get("/scenarios/{scenario_id}")
def get_scenario(
    scenario_id: UUID,
    service: ScenarioServiceDep,
) -> dict[str, Any]:
    """Return scenario details with current changes."""
    return service.get(scenario_id)


@router.post(
    "/scenarios/{scenario_id}/versions",
    status_code=status.HTTP_201_CREATED,
)
def add_scenario_version(
    scenario_id: UUID,
    body: ScenarioVersionCreateRequest,
    service: ScenarioServiceDep,
) -> dict[str, Any]:
    """Create a new immutable scenario version (new change set)."""
    payload = ScenarioVersionCreateInput(
        changes=_to_change_inputs(body.changes),
    )
    return service.add_version(scenario_id, payload)


@router.post(
    "/scenarios/{scenario_id}/simulate",
    status_code=status.HTTP_202_ACCEPTED,
)
def simulate_scenario(
    scenario_id: UUID,
    body: ScenarioSimulateRequest,
    service: ScenarioServiceDep,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
) -> SimulationStatusResponse:
    """Enqueue Monte Carlo for this scenario overlay."""
    scenario = service.get(scenario_id)
    version_id = UUID(str(scenario["version_id"]))
    sim_body = body.to_simulation_body(version_id)
    row = service.simulate(
        scenario_id,
        configuration=sim_body.to_configuration(),
        idempotency_key=idempotency_key,
        reliability_model_id=body.reliability_model_id,
        seed=body.random_seed,
    )
    return SimulationStatusResponse.from_row(row)


@router.get("/scenarios/{scenario_id}/compare")
def compare_scenario(
    scenario_id: UUID,
    service: ScenarioServiceDep,
    baseline_run_id: Annotated[UUID | None, Query()] = None,
    scenario_run_id: Annotated[UUID | None, Query()] = None,
) -> dict[str, Any]:
    """Compare completed baseline vs scenario metrics (TZ §71)."""
    return service.compare(
        scenario_id,
        baseline_run_id=baseline_run_id,
        scenario_run_id=scenario_run_id,
    )

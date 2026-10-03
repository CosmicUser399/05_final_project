"""FastAPI dependencies for application services."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from typing import cast

from fastapi import Depends
from fastapi import Request
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from app.application.connections_service import ConnectionsService
from app.application.diagnostics_service import DiagnosticsService
from app.application.equipment_service import EquipmentService
from app.application.failure_modes import FailureModeService
from app.application.maintenance_service import MaintenanceService
from app.application.petri_service import PetriService
from app.application.ports import PetriPilotPort
from app.application.production_service import ProductionService
from app.application.reliability_service import ReliabilityService
from app.application.resources_service import ResourcesService
from app.application.simulation_service import SimulationService
from app.application.systems import SystemService
from app.application.versions import VersionService
from app.config import Settings
from app.config import get_settings
from app.infrastructure.db.uow import SqlAlchemyUnitOfWork
from app.infrastructure.mcp.mock_petri_pilot import MockPetriPilotProvider
from app.infrastructure.mcp.petri_pilot import PetriPilotMCPAdapter


def get_app_settings() -> Settings:
    """Return application settings."""
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_session_factory(request: Request) -> sessionmaker[Session]:
    """Return the SQLAlchemy session factory from app state."""
    factory = getattr(request.app.state, "session_factory", None)
    if factory is None:
        msg = "session_factory is not configured"
        raise RuntimeError(msg)
    return cast(sessionmaker[Session], factory)


def get_uow_factory(
    session_factory: Annotated[
        sessionmaker[Session],
        Depends(get_session_factory),
    ],
) -> Callable[[], SqlAlchemyUnitOfWork]:
    """Build a unit-of-work factory bound to the session factory."""

    def factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(session_factory)

    return factory


UowFactoryDep = Annotated[
    Callable[[], SqlAlchemyUnitOfWork],
    Depends(get_uow_factory),
]


def get_system_service(uow_factory: UowFactoryDep) -> SystemService:
    """Provide the system application service."""
    return SystemService(uow_factory)


def get_version_service(uow_factory: UowFactoryDep) -> VersionService:
    """Provide the version application service."""
    return VersionService(uow_factory)


def get_equipment_service(uow_factory: UowFactoryDep) -> EquipmentService:
    """Provide the equipment application service."""
    return EquipmentService(uow_factory)


def get_failure_mode_service(
    uow_factory: UowFactoryDep,
) -> FailureModeService:
    """Provide the failure mode application service."""
    return FailureModeService(uow_factory)


def get_maintenance_service(
    uow_factory: UowFactoryDep,
) -> MaintenanceService:
    """Provide the maintenance application service."""
    return MaintenanceService(uow_factory)


def get_diagnostics_service(
    uow_factory: UowFactoryDep,
) -> DiagnosticsService:
    """Provide the diagnostics application service."""
    return DiagnosticsService(uow_factory)


def get_connections_service(
    uow_factory: UowFactoryDep,
) -> ConnectionsService:
    """Provide the connections application service."""
    return ConnectionsService(uow_factory)


def get_resources_service(
    uow_factory: UowFactoryDep,
) -> ResourcesService:
    """Provide the resources application service."""
    return ResourcesService(uow_factory)


def get_production_service(
    uow_factory: UowFactoryDep,
) -> ProductionService:
    """Provide the production application service."""
    return ProductionService(uow_factory)


def get_reliability_service(
    uow_factory: UowFactoryDep,
) -> ReliabilityService:
    """Provide the reliability model application service."""
    return ReliabilityService(uow_factory)


def get_petri_pilot(settings: SettingsDep) -> PetriPilotPort:
    """Provide Petri-Pilot port (mock by default in MVP/tests)."""
    if settings.petri_pilot_use_mock or not settings.petri_pilot_mcp_url:
        return MockPetriPilotProvider()
    return PetriPilotMCPAdapter(settings)


def get_petri_service(
    uow_factory: UowFactoryDep,
    settings: SettingsDep,
    pilot: Annotated[PetriPilotPort, Depends(get_petri_pilot)],
) -> PetriService:
    """Provide the Petri model application service."""
    return PetriService(
        uow_factory,
        pilot,
        max_states=settings.petri_pilot_max_states,
    )


def get_simulation_service(
    uow_factory: UowFactoryDep,
    settings: SettingsDep,
) -> SimulationService:
    """Provide the simulation job application service."""
    return SimulationService(uow_factory, settings)


SystemServiceDep = Annotated[SystemService, Depends(get_system_service)]
VersionServiceDep = Annotated[VersionService, Depends(get_version_service)]
EquipmentServiceDep = Annotated[
    EquipmentService,
    Depends(get_equipment_service),
]
FailureModeServiceDep = Annotated[
    FailureModeService,
    Depends(get_failure_mode_service),
]
MaintenanceServiceDep = Annotated[
    MaintenanceService,
    Depends(get_maintenance_service),
]
DiagnosticsServiceDep = Annotated[
    DiagnosticsService,
    Depends(get_diagnostics_service),
]
ConnectionsServiceDep = Annotated[
    ConnectionsService,
    Depends(get_connections_service),
]
ResourcesServiceDep = Annotated[
    ResourcesService,
    Depends(get_resources_service),
]
ProductionServiceDep = Annotated[
    ProductionService,
    Depends(get_production_service),
]
ReliabilityServiceDep = Annotated[
    ReliabilityService,
    Depends(get_reliability_service),
]
PetriServiceDep = Annotated[PetriService, Depends(get_petri_service)]
SimulationServiceDep = Annotated[
    SimulationService,
    Depends(get_simulation_service),
]

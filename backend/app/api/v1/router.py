"""Aggregate API v1 routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import connections
from app.api.v1 import diagnostics
from app.api.v1 import equipment
from app.api.v1 import failure_modes
from app.api.v1 import maintenance
from app.api.v1 import production
from app.api.v1 import resources
from app.api.v1 import systems
from app.api.v1 import versions

router = APIRouter()

router.include_router(systems.router)
router.include_router(versions.router)
router.include_router(equipment.router)
router.include_router(failure_modes.router)
router.include_router(maintenance.router)
router.include_router(diagnostics.router)
router.include_router(connections.router)
router.include_router(resources.router)
router.include_router(production.router)

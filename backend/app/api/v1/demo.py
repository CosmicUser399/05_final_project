"""REST routes for curated demo datasets."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi import status
from pydantic import BaseModel

from app.api.deps import DemoServiceDep

router = APIRouter(prefix="/demo", tags=["demo"])


class SeedUpp100Request(BaseModel):
    """Options for УПП-100 seed load."""

    write_seed_file: bool = True


@router.post("/upp100", status_code=status.HTTP_201_CREATED)
def seed_upp100(
    body: SeedUpp100Request,
    service: DemoServiceDep,
) -> dict[str, Any]:
    """Load the УПП-100 demo plant (software testing only)."""
    return service.seed_upp100(write_seed_file=body.write_seed_file)

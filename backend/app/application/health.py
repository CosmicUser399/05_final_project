"""Health and readiness use cases."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import Protocol


class DatabaseProbe(Protocol):
    """Port: checks that the database accepts connections."""

    def is_available(self) -> bool:
        """Return True when a trivial query succeeds."""
        ...


@dataclass(frozen=True)
class HealthStatus:
    """Liveness result."""

    status: str
    version: str


@dataclass(frozen=True)
class ReadinessStatus:
    """Readiness result with per-dependency checks."""

    ready: bool
    checks: dict[str, bool] = field(default_factory=dict)


def get_health(version: str) -> HealthStatus:
    """Return liveness status of the process."""
    return HealthStatus(status="ok", version=version)


def get_readiness(database: DatabaseProbe) -> ReadinessStatus:
    """Return readiness: all required dependencies must be available."""
    checks = {"database": database.is_available()}
    return ReadinessStatus(ready=all(checks.values()), checks=checks)

"""Typed domain errors.

The API layer maps these errors to HTTP codes and to the unified
``{"error": {"code", "message", "entity", "entity_id"}}`` body.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.validation import ValidationIssue


class DomainError(Exception):
    """Base class for all domain errors."""

    default_code = "DOMAIN_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        entity: str | None = None,
        entity_id: str | None = None,
    ) -> None:
        """Create an error with a machine-readable ``code``."""
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.entity = entity
        self.entity_id = entity_id


class ValidationError(DomainError):
    """Input or model failed validation (levels 1-3)."""

    default_code = "VALIDATION_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        entity: str | None = None,
        entity_id: str | None = None,
        issues: "Sequence[ValidationIssue] | None" = None,
    ) -> None:
        """Create a validation error, optionally with all issues."""
        super().__init__(
            message, code=code, entity=entity, entity_id=entity_id
        )
        self.issues: tuple[ValidationIssue, ...] = (
            tuple(issues) if issues else ()
        )


class UnitError(ValidationError):
    """Unknown or incompatible unit."""

    default_code = "INVALID_UNIT"


class NotFoundError(DomainError):
    """Requested entity does not exist."""

    default_code = "ENTITY_NOT_FOUND"


class ImmutableVersionError(DomainError):
    """Attempt to modify a frozen (non-DRAFT) system version."""

    default_code = "VERSION_FROZEN"


class InvalidTransitionError(DomainError):
    """Forbidden system version status transition."""

    default_code = "INVALID_STATUS_TRANSITION"


class UnsupportedOperationError(DomainError):
    """Operation is not defined for this object."""

    default_code = "UNSUPPORTED_OPERATION"


class ModelGenerationError(DomainError):
    """Reliability or Petri model could not be generated."""

    default_code = "MODEL_GENERATION_ERROR"


class ExternalServiceError(DomainError):
    """External provider timed out or returned an error."""

    default_code = "EXTERNAL_SERVICE_ERROR"


class SimulationError(DomainError):
    """Simulation could not be prepared or executed."""

    default_code = "SIMULATION_ERROR"

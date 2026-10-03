"""Provenance of engineering parameters.

Every reliability parameter carries its origin. ``AI_ESTIMATE`` values
and Fabricate output are synthetic and are never presented as facts.
"""

from datetime import UTC
from datetime import datetime
from enum import StrEnum
from uuid import UUID
from uuid import uuid4

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

FABRICATE_GENERATOR = "fabricate"


class SourceType(StrEnum):
    """Origin of an engineering value."""

    OREDA = "OREDA"
    ISO_14224 = "ISO_14224"
    USER_DEFINED = "USER_DEFINED"
    AI_ESTIMATE = "AI_ESTIMATE"
    ENGINEERING_ASSUMPTION = "ENGINEERING_ASSUMPTION"
    HISTORICAL_DATA = "HISTORICAL_DATA"
    MANUFACTURER_DATA = "MANUFACTURER_DATA"


class Confidence(StrEnum):
    """Confidence in a value."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ValueStatus(StrEnum):
    """Knowledge status of a value; ``UNKNOWN`` is a valid state."""

    KNOWN = "KNOWN"
    INFERRED = "INFERRED"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


_REFERENCE_REQUIRED = frozenset(
    {
        SourceType.OREDA,
        SourceType.ISO_14224,
        SourceType.HISTORICAL_DATA,
        SourceType.MANUFACTURER_DATA,
    }
)


class ReferenceSource(BaseModel):
    """A document or dataset values can be traced back to."""

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=uuid4)
    source_type: SourceType
    title: str = Field(min_length=1, max_length=300)
    edition: str | None = Field(default=None, max_length=100)
    locator: str | None = Field(default=None, max_length=300)


class Provenance(BaseModel):
    """Where a parameter value comes from and how far to trust it."""

    model_config = ConfigDict(frozen=True)

    source_type: SourceType
    source_reference: str | None = Field(default=None, max_length=500)
    confidence: Confidence = Confidence.LOW
    generated_by: str | None = Field(default=None, max_length=100)
    generated_at: datetime | None = None

    @model_validator(mode="after")
    def _check_consistency(self) -> "Provenance":
        reference = (self.source_reference or "").strip()
        if self.source_type in _REFERENCE_REQUIRED and not reference:
            raise ValueError(
                f"source_reference is required for {self.source_type}"
            )
        if (
            self.source_type is SourceType.AI_ESTIMATE
            and self.confidence is Confidence.HIGH
        ):
            raise ValueError("AI_ESTIMATE cannot have HIGH confidence")
        if self.generated_at is not None and self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return self

    @property
    def is_estimate(self) -> bool:
        """Return True if the value is an estimate, not a fact."""
        return self.source_type in (
            SourceType.AI_ESTIMATE,
            SourceType.ENGINEERING_ASSUMPTION,
        )

    @property
    def is_synthetic(self) -> bool:
        """Return True for AI/Fabricate generated values."""
        return self.source_type is SourceType.AI_ESTIMATE

    @classmethod
    def user_defined(cls, user: str | None = None) -> "Provenance":
        """Provenance for a value entered by the user."""
        return cls(
            source_type=SourceType.USER_DEFINED,
            confidence=Confidence.MEDIUM,
            generated_by=user,
            generated_at=datetime.now(UTC),
        )

    @classmethod
    def ai_estimate(
        cls, generated_by: str, source_reference: str | None = None
    ) -> "Provenance":
        """Provenance for a low-confidence AI estimate."""
        return cls(
            source_type=SourceType.AI_ESTIMATE,
            source_reference=source_reference,
            confidence=Confidence.LOW,
            generated_by=generated_by,
            generated_at=datetime.now(UTC),
        )

    @classmethod
    def fabricate_estimate(cls, conversation_id: str) -> "Provenance":
        """Provenance for synthetic data produced by Fabricate."""
        return cls.ai_estimate(
            generated_by=FABRICATE_GENERATOR,
            source_reference=conversation_id,
        )

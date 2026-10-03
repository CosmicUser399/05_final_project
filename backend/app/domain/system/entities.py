"""System and SystemVersion with status and freezing rules."""

from datetime import UTC
from datetime import datetime
from enum import StrEnum
from typing import Final
from typing import Self
from uuid import UUID
from uuid import uuid4

from pydantic import Field

from app.domain.base import Entity
from app.domain.errors import ImmutableVersionError
from app.domain.errors import InvalidTransitionError


class VersionStatus(StrEnum):
    """Lifecycle status of a system version."""

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    RELEASED = "RELEASED"
    ARCHIVED = "ARCHIVED"


ALLOWED_TRANSITIONS: Final[dict[VersionStatus, frozenset[VersionStatus]]] = {
    VersionStatus.DRAFT: frozenset(
        {VersionStatus.VALIDATED, VersionStatus.ARCHIVED}
    ),
    VersionStatus.VALIDATED: frozenset(
        {VersionStatus.RELEASED, VersionStatus.ARCHIVED}
    ),
    VersionStatus.RELEASED: frozenset({VersionStatus.ARCHIVED}),
    VersionStatus.ARCHIVED: frozenset(),
}


def _now() -> datetime:
    return datetime.now(UTC)


class System(Entity):
    """A technological system (plant, unit)."""

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    created_at: datetime = Field(default_factory=_now)
    created_by: UUID | None = None


class SystemVersion(Entity):
    """Immutable-after-validation snapshot container of a system.

    ``DRAFT`` is editable. From ``VALIDATED`` on the content is frozen:
    any change is made by cloning into a new ``DRAFT`` that keeps the
    same ``lineage_id``.
    """

    system_id: UUID
    lineage_id: UUID = Field(default_factory=uuid4)
    version_number: int = Field(default=1, ge=1)
    status: VersionStatus = VersionStatus.DRAFT
    parent_version_id: UUID | None = None
    comment: str | None = Field(default=None, max_length=2000)
    created_at: datetime = Field(default_factory=_now)
    created_by: UUID | None = None
    validated_at: datetime | None = None
    released_at: datetime | None = None

    @property
    def is_frozen(self) -> bool:
        """Return True if the content must not be modified."""
        return self.status is not VersionStatus.DRAFT

    def ensure_editable(self) -> None:
        """Raise ``ImmutableVersionError`` unless the version is DRAFT."""
        if self.is_frozen:
            raise ImmutableVersionError(
                f"version is {self.status}; clone it to edit",
                entity="SystemVersion",
                entity_id=str(self.id),
            )

    def can_transition_to(self, target: VersionStatus) -> bool:
        """Return True if ``status -> target`` is allowed."""
        return target in ALLOWED_TRANSITIONS[self.status]

    def transition_to(
        self, target: VersionStatus, when: datetime | None = None
    ) -> None:
        """Move to ``target`` or raise ``InvalidTransitionError``."""
        if not self.can_transition_to(target):
            raise InvalidTransitionError(
                f"cannot change status {self.status} -> {target}",
                entity="SystemVersion",
                entity_id=str(self.id),
            )
        moment = when or _now()
        self.status = target
        if target is VersionStatus.VALIDATED:
            self.validated_at = moment
        elif target is VersionStatus.RELEASED:
            self.released_at = moment

    def create_draft_clone(self, created_by: UUID | None = None) -> Self:
        """Return a new DRAFT with the next number and same lineage."""
        return type(self)(
            system_id=self.system_id,
            lineage_id=self.lineage_id,
            version_number=self.version_number + 1,
            status=VersionStatus.DRAFT,
            parent_version_id=self.id,
            created_by=created_by,
        )

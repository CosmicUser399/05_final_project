"""Base classes for domain entities."""

from typing import Self
from uuid import UUID
from uuid import uuid4

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class Entity(BaseModel):
    """Entity with a UUID identity; checked on every assignment."""

    model_config = ConfigDict(validate_assignment=True)

    id: UUID = Field(default_factory=uuid4)


class VersionedEntity(Entity):
    """Entity owned by a ``SystemVersion``.

    ``lineage_id`` is shared by all copies of the same logical object
    across versions; ``id`` is unique per version.
    """

    version_id: UUID
    lineage_id: UUID = Field(default_factory=uuid4)

    def clone_for_version(self, version_id: UUID) -> Self:
        """Copy into another version: new ``id``, same ``lineage_id``.

        References to other entities are not remapped here; this is
        done by the version cloning service.
        """
        return self.model_copy(
            update={"id": uuid4(), "version_id": version_id},
            deep=True,
        )

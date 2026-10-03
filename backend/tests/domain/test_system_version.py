"""Tests for System and SystemVersion freezing rules."""

from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError

from app.domain.errors import ImmutableVersionError
from app.domain.errors import InvalidTransitionError
from app.domain.system.entities import ALLOWED_TRANSITIONS
from app.domain.system.entities import System
from app.domain.system.entities import SystemVersion
from app.domain.system.entities import VersionStatus


def _version() -> SystemVersion:
    return SystemVersion(system_id=uuid4())


def test_new_version_is_editable_draft() -> None:
    version = _version()
    assert version.status is VersionStatus.DRAFT
    assert version.version_number == 1
    assert not version.is_frozen
    version.ensure_editable()


def test_system_requires_name() -> None:
    assert System(name="UPP-100").name == "UPP-100"
    with pytest.raises(PydanticValidationError):
        System(name="")


def test_happy_path_transitions_set_timestamps() -> None:
    version = _version()
    version.transition_to(VersionStatus.VALIDATED)
    assert version.validated_at is not None
    version.transition_to(VersionStatus.RELEASED)
    assert version.released_at is not None
    version.transition_to(VersionStatus.ARCHIVED)
    assert version.status is VersionStatus.ARCHIVED


@pytest.mark.parametrize(
    "status", [VersionStatus.VALIDATED, VersionStatus.RELEASED]
)
def test_non_draft_versions_are_frozen(status: VersionStatus) -> None:
    version = _version()
    version.transition_to(VersionStatus.VALIDATED)
    if status is VersionStatus.RELEASED:
        version.transition_to(VersionStatus.RELEASED)
    assert version.is_frozen
    with pytest.raises(ImmutableVersionError) as info:
        version.ensure_editable()
    assert info.value.code == "VERSION_FROZEN"
    assert info.value.entity == "SystemVersion"


def test_archived_is_frozen_too() -> None:
    version = _version()
    version.transition_to(VersionStatus.ARCHIVED)
    assert version.is_frozen


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (VersionStatus.DRAFT, VersionStatus.RELEASED),
        (VersionStatus.VALIDATED, VersionStatus.DRAFT),
        (VersionStatus.RELEASED, VersionStatus.DRAFT),
        (VersionStatus.RELEASED, VersionStatus.VALIDATED),
        (VersionStatus.ARCHIVED, VersionStatus.DRAFT),
        (VersionStatus.DRAFT, VersionStatus.DRAFT),
    ],
)
def test_forbidden_transitions(
    source: VersionStatus, target: VersionStatus
) -> None:
    version = SystemVersion(system_id=uuid4(), status=source)
    assert not version.can_transition_to(target)
    with pytest.raises(InvalidTransitionError):
        version.transition_to(target)
    assert version.status is source


def test_every_status_has_a_transition_entry() -> None:
    assert set(ALLOWED_TRANSITIONS) == set(VersionStatus)
    assert ALLOWED_TRANSITIONS[VersionStatus.ARCHIVED] == frozenset()


def test_clone_creates_new_draft_with_same_lineage() -> None:
    version = _version()
    version.transition_to(VersionStatus.VALIDATED)
    author = uuid4()
    draft = version.create_draft_clone(created_by=author)
    assert draft.id != version.id
    assert draft.lineage_id == version.lineage_id
    assert draft.system_id == version.system_id
    assert draft.status is VersionStatus.DRAFT
    assert draft.version_number == 2
    assert draft.parent_version_id == version.id
    assert draft.created_by == author
    assert version.status is VersionStatus.VALIDATED
    assert not draft.is_frozen

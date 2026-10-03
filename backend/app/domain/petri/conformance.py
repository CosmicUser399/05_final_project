"""Map RAM event logs to Petri-Pilot conformance format."""

from __future__ import annotations

import json
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict

from app.domain.petri.entities import PetriModel
from app.domain.petri.entities import TransitionRole


class ConformanceEvent(BaseModel):
    """One event in a Petri-Pilot conformance log."""

    model_config = ConfigDict(frozen=True)

    case: str
    activity: str
    timestamp: str | None = None


class _LoggedLike(Protocol):
    """Minimal event shape accepted by the mapper."""

    time_minutes: float
    event_type: str
    equipment_id: UUID | None
    failure_mode_id: UUID | None


_EVENT_TO_ROLE: dict[str, TransitionRole] = {
    "POTENTIAL_FAILURE": TransitionRole.TO_PF,
    "DETECTION": TransitionRole.DETECT,
    "CM_START": TransitionRole.CM_START,
    "CM_COMPLETE": TransitionRole.CM_DONE,
    "PM_START": TransitionRole.PM_START,
    "PM_COMPLETE": TransitionRole.PM_DONE,
}


def events_to_conformance_log(
    model: PetriModel,
    events: list[_LoggedLike] | tuple[_LoggedLike, ...],
    *,
    base_time: datetime | None = None,
) -> list[ConformanceEvent]:
    """Convert RAM events to opaque-activity conformance events.

    Only events that map to a transition role present in the matching
    failure-mode subnet are emitted. Case id is ``fm:<failure_mode_id>``.
    """
    origin = base_time or datetime(1970, 1, 1, tzinfo=UTC)
    out: list[ConformanceEvent] = []
    for event in events:
        if event.failure_mode_id is None:
            continue
        subnet_key = f"fm:{event.failure_mode_id}"
        role = _role_for_event(model, subnet_key, event.event_type)
        if role is None:
            continue
        transition = model.transition_by_role(subnet_key, role)
        if transition is None:
            continue
        stamp = origin + timedelta(minutes=float(event.time_minutes))
        out.append(
            ConformanceEvent(
                case=subnet_key,
                activity=transition.id,
                timestamp=stamp.isoformat().replace("+00:00", "Z"),
            )
        )
    return out


def conformance_log_json(events: list[ConformanceEvent]) -> str:
    """Serialize conformance events as a JSON array string."""
    payload = [e.model_dump(mode="json") for e in events]
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _role_for_event(
    model: PetriModel,
    subnet_key: str,
    event_type: str,
) -> TransitionRole | None:
    if event_type == "FAILURE":
        # Detectable modes use MISS; others use FAIL.
        if model.transition_by_role(subnet_key, TransitionRole.MISS):
            return TransitionRole.MISS
        return TransitionRole.FAIL
    return _EVENT_TO_ROLE.get(event_type)

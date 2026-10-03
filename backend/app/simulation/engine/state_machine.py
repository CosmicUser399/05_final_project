"""Equipment state machine with explicit transitions."""

from __future__ import annotations

from uuid import UUID

from app.domain.errors import SimulationError
from app.domain.simulation.states import EquipmentState

_ALLOWED: dict[EquipmentState, frozenset[EquipmentState]] = {
    EquipmentState.UP: frozenset(
        {
            EquipmentState.POTENTIAL_FAILURE,
            EquipmentState.FAILED,
            EquipmentState.MAINTENANCE,
            EquipmentState.STANDBY,
            EquipmentState.DIAGNOSIS,
        }
    ),
    EquipmentState.POTENTIAL_FAILURE: frozenset(
        {
            EquipmentState.FAILED,
            EquipmentState.DIAGNOSIS,
            EquipmentState.MAINTENANCE,
            EquipmentState.UP,
        }
    ),
    EquipmentState.FAILED: frozenset(
        {
            EquipmentState.DIAGNOSIS,
            EquipmentState.WAITING_FOR_RESOURCE,
            EquipmentState.WAITING_FOR_SPARE,
            EquipmentState.MAINTENANCE,
        }
    ),
    EquipmentState.DIAGNOSIS: frozenset(
        {
            EquipmentState.WAITING_FOR_RESOURCE,
            EquipmentState.WAITING_FOR_SPARE,
            EquipmentState.MAINTENANCE,
            EquipmentState.UP,
        }
    ),
    EquipmentState.WAITING_FOR_RESOURCE: frozenset(
        {
            EquipmentState.WAITING_FOR_SPARE,
            EquipmentState.MAINTENANCE,
            EquipmentState.DIAGNOSIS,
        }
    ),
    EquipmentState.WAITING_FOR_SPARE: frozenset(
        {
            EquipmentState.WAITING_FOR_RESOURCE,
            EquipmentState.MAINTENANCE,
        }
    ),
    EquipmentState.MAINTENANCE: frozenset(
        {
            EquipmentState.RESTORING,
            EquipmentState.UP,
            EquipmentState.STANDBY,
        }
    ),
    EquipmentState.RESTORING: frozenset(
        {
            EquipmentState.UP,
            EquipmentState.STANDBY,
        }
    ),
    EquipmentState.STANDBY: frozenset(
        {
            EquipmentState.UP,
            EquipmentState.MAINTENANCE,
        }
    ),
}


class EquipmentStateMachine:
    """Validate and apply equipment state transitions."""

    def __init__(
        self,
        equipment_id: UUID,
        initial: EquipmentState = EquipmentState.UP,
    ) -> None:
        """Create a machine for one equipment unit."""
        self.equipment_id = equipment_id
        self.state = initial

    def transition(self, new_state: EquipmentState) -> EquipmentState:
        """Move to ``new_state`` or raise ``SimulationError``."""
        if new_state is self.state:
            return self.state
        allowed = _ALLOWED.get(self.state, frozenset())
        if new_state not in allowed:
            raise SimulationError(
                f"illegal transition {self.state} -> {new_state}",
                code="ILLEGAL_STATE_TRANSITION",
                entity="equipment",
                entity_id=str(self.equipment_id),
            )
        self.state = new_state
        return self.state

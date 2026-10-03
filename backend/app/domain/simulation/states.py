"""Equipment states used by the RAM engine."""

from enum import StrEnum


class EquipmentState(StrEnum):
    """Explicit equipment state-machine states."""

    UP = "UP"
    POTENTIAL_FAILURE = "POTENTIAL_FAILURE"
    FAILED = "FAILED"
    DIAGNOSIS = "DIAGNOSIS"
    WAITING_FOR_RESOURCE = "WAITING_FOR_RESOURCE"
    WAITING_FOR_SPARE = "WAITING_FOR_SPARE"
    MAINTENANCE = "MAINTENANCE"
    RESTORING = "RESTORING"
    STANDBY = "STANDBY"


# States that produce (or can produce) process output.
PRODUCING_STATES: frozenset[EquipmentState] = frozenset(
    {
        EquipmentState.UP,
        EquipmentState.POTENTIAL_FAILURE,
    }
)

# States counted as corrective / preventive downtime.
DOWN_STATES: frozenset[EquipmentState] = frozenset(
    {
        EquipmentState.FAILED,
        EquipmentState.DIAGNOSIS,
        EquipmentState.WAITING_FOR_RESOURCE,
        EquipmentState.WAITING_FOR_SPARE,
        EquipmentState.MAINTENANCE,
        EquipmentState.RESTORING,
    }
)

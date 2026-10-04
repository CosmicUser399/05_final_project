# Equipment and version states

## SystemVersion

| Status | Editable | Notes |
|--------|----------|-------|
| DRAFT | yes | Working copy |
| VALIDATED | no | Frozen; clone to edit |
| RELEASED | no | Published baseline |
| ARCHIVED | no | Terminal |

## Equipment runtime (RAM engine)

`UP → POTENTIAL_FAILURE → FAILED → DIAGNOSIS → WAITING_FOR_RESOURCE →
WAITING_FOR_SPARE → MAINTENANCE → RESTORING → UP`, plus `STANDBY`.

PF interval: `T_pf = T_f - PF`; if `T_pf < 0` the potential failure is
not modelled.

## Simulation job

`CREATED / QUEUED / VALIDATING / RUNNING / AGGREGATING / COMPLETED /
FAILED / CANCELLED`.

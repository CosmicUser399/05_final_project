# RAM Engine (P4)

Event-driven single-trial simulation kernel. No database or UI
dependencies (ADR-004).

## Entry point

```python
from app.domain.reliability.compiled import CompiledModel
from app.domain.reliability.compiled import ScenarioOverlay
from app.domain.simulation import SimulationConfiguration
from app.simulation import SimulationEngine

result = SimulationEngine().run(
    model,
    ScenarioOverlay(),
    SimulationConfiguration(horizon=20, horizon_unit="YEARS", random_seed=42),
    seed=42,
)
```

Input: `CompiledModel` + optional `ScenarioOverlay` +
`SimulationConfiguration` + `seed`.
Output: `SimulationRunResult` (metrics, optional event log).

All internal times are minutes (`float64`).

## Components

| Component | Role |
|-----------|------|
| `SimulationClock` | Monotonic time |
| `EventQueue` | `heapq` ordered by `(time, seq)` |
| `RandomProvider` | `SeedSequence(entropy, spawn_key=(run_id, …))` |
| `FailureGenerator` / `CompetingRiskModel` | TTF sampling, min risk |
| `PFIntervalScheduler` | `T_pf = T_f - PF`; negative onset skipped |
| `DiagnosticEngine` | Lazy checks in `[T_pf, T_f)` |
| `MaintenanceEngine` | CM/PM selection, AGAN/ABAO/partial effects |
| `ResourceManager` / `SparePartManager` | Capacity, queues, lead time |
| `EquipmentStateMachine` | Explicit state transitions |
| `ProductionImpactEngine` | Capacity via `ReliabilityStructure` |
| `MetricsCollector` | Uptime, MTBF/MTTR/MTBM/MDT, Ai/Ao, loss |

## Metrics (definitions)

- `MTBF = uptime / failure_count`
- `MTTR = corrective_repair_time / cm_count`
- `Ai = MTBF / (MTBF + MTTR)`
- `Ao = MTBM / (MTBM + MDT)`
- Warm-up excluded from aggregates
- Production loss = `∫ nominal * (1 - capacity) dt`

## Golden checks

- P-101: Exp(MTBF=1000 h), MTTR=10 h → `Ai ≈ 1000/1010`
- PF: `T_f=1000 h`, `PF=100 h`, check at 950 h, `p=1` → detection,
  no functional `FAILURE`
- Competing risks, resource/spare waits, production loss, seed
  determinism

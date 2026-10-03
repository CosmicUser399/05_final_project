# Monte Carlo, metrics and jobs (P5)

Orchestrates N independent RAM Engine trials, aggregates metrics with
confidence intervals, persists results, and exposes async jobs via
REST + SSE.

## Entry points

```python
from app.simulation import MonteCarloRunner

result = MonteCarloRunner(software_version="0.1.0").run(
    model,
    scenario,
    configuration,  # number_of_runs, seed, parallel_runs, …
)
```

HTTP (worker executes the queue):

```http
POST /api/v1/simulations
Idempotency-Key: <optional unique key>

GET  /api/v1/simulations/{id}/status
GET  /api/v1/simulations/{id}/results
GET  /api/v1/simulations/{id}/events
GET  /api/v1/simulations/{id}/stream   # SSE progress
POST /api/v1/simulations/{id}/cancel
```

Worker: `python -m app.worker` (claims `QUEUED` rows).

## Lifecycle

`CREATED` → `QUEUED` → `VALIDATING` → `RUNNING` → `AGGREGATING` →
`COMPLETED` | `FAILED` | `CANCELLED`.

Claim:

- SQLite: atomic `UPDATE … WHERE status='QUEUED'`
- PostgreSQL: `SELECT … FOR UPDATE SKIP LOCKED`
- Heartbeat + reclaim of stuck active jobs

## Fingerprint

```text
simulation_fingerprint = SHA256(
  model_hash + scenario_hash + configuration_hash + seed + software_version
)
```

`configuration_hash` excludes per-trial `run_id`.

## Aggregates

System: R(horizon), Ai, Ao, MTBF/MTTR/MTBM/MDT, downtime, production
loss/availability, repair p90/p95, failure Pareto, per-equipment
summaries.

Intervals:

- proportions → Wilson (N ≥ 40) or Clopper-Pearson
- means → Student-t CI; also median / P5 / P50 / P95

## Persistence

Tables (Alembic `c8d4f2b01e53`): `simulation_configurations`,
`simulation_runs`, `system_metrics`, `equipment_metrics`,
`failure_events`, `maintenance_events`, `diagnostic_events`,
`production_loss_events`, `resource_consumption`,
`spare_part_consumption`.

Event logs are written for the first `SIMULATION_EVENT_LOG_RUNS`
trials only; inserts are batched with short transactions (WAL-friendly).

## Limits (env)

| Variable | Default |
|----------|---------|
| `SIMULATION_MAX_RUNS` | 100000 |
| `SIMULATION_MAX_WORKERS` | 4 |
| `SIMULATION_MAX_HORIZON_YEARS` | 50 |
| `SIMULATION_RESULT_BATCH_SIZE` | 500 |
| `SIMULATION_HEARTBEAT_TIMEOUT_SECONDS` | 120 |
| `SIMULATION_EVENT_LOG_RUNS` | 5 |

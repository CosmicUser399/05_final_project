# Simulation events

Events are stored in normalized tables (not one JSON blob), batched on
write:

- failure events
- maintenance events
- diagnostic events
- production loss events
- resource / spare consumption

Full event logs are kept for a limited number of runs
(`simulation_event_log_runs`); aggregates cover all runs.

API: `GET /api/v1/simulations/{id}/events` with pagination/filters.

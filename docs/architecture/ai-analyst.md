# AI Analyst (P10)

AI Analyst answers engineering questions about a system using **only**
typed read tools against Domain DB / stored simulation results.

## Boundary

Allowed tools (whitelist):

- `system.get`
- `equipment.search`
- `failure_mode.search`
- `maintenance.search`
- `simulation.get_metrics`
- `simulation.get_events`
- `simulation.compare`
- `scenario.get`
- `reference.search` (OREDA/ISO parameters + taxonomy; requires ingest)

Forbidden: `sql.execute`, `shell.execute`, `filesystem.*`, arbitrary DB.

## Pipeline

1. Request `POST /api/v1/ai/chat` with `message` + optional context
   (`system_id`, `version_id`, `scenario_id`, `simulation_run_id`,
   `equipment_id`).
2. Planner selects tools (heuristic + optional LLM plan JSON).
3. `AnalystToolExecutor` runs tools via application services.
4. Deterministic synthesis builds a **readable Russian** answer from
   tool payloads (no raw JSON dumps).
5. Optional LLM polish must pass **grounding**: every number in the
   answer must appear in tool results; otherwise the deterministic
   answer is returned.
6. Optional `history` (prior user/assistant turns) supports dialog
   continuity; numbers still come only from tools.
7. Response includes `answer`, `references`, `tool_calls`, `grounded`.

SSE: `POST /api/v1/ai/chat/stream` emits `started`, `planned`,
`tool_start`, `tool_result`, `done`, `answer`.

## UI

`/ai/analyst` — context selectors + dialog chat. History is persisted
in the browser (`localStorage`) per selected system/version/run.
Numbers are never calculated in the browser.

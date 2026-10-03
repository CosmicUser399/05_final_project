# AI Orchestrator and Fabricate (P7)

Runtime adapters are independent of Cursor MCP configuration. Secrets
come only from environment variables.

## Ports

- `AIProvider` — structured JSON completions (OpenAI via httpx, or mock).
- `FabricateProvider` — whitelist MCP tools only (no `delete_*`).
- `EquipmentProposalProvider` — unified
  `description -> proposal payload` for OpenAI and Fabricate.

## Pipeline

1. `POST /api/v1/ai/generate-system` with `provider=openai|fabricate`.
2. Job row in `generation_jobs` (`QUEUED` → … → `READY_FOR_REVIEW`).
3. Provider produces a validated `EquipmentProposalPayload` (never Domain DB).
4. Proposal + items stored for review (`proposals`, `proposal_items`).
5. User accept/edit/reject per row; `POST .../commit` calls domain services.

Fabricate artifacts are opened read-only after `PRAGMA integrity_check`
(`StagingImporter`). Provenance: `AI_ESTIMATE` / `LOW` /
`generated_by=fabricate` / `source_reference=<conversation_id>`.

## Config

See `.env.example`: `OPENAI_*`, `FABRICATE_*`,
`GENERATION_HEARTBEAT_TIMEOUT_SECONDS`, `GENERATION_SSE_POLL_SECONDS`.
Mocks are on by default (`OPENAI_USE_MOCK=true`, `FABRICATE_USE_MOCK=true`).

## Staging schema

`docs/api/fabricate-staging-schema.md` (version `1`).

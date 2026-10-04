# API overview

Base path: `/api/v1`. OpenAPI is the source for the typed TS client.

## Groups

- Systems / versions / model snapshot
- Equipment, connections, failure modes, maintenance, diagnostics
- Resources, spares, production
- Reliability compile/validate, Petri generate/validate/analyze
- Simulations (+ SSE progress), scenarios compare
- AI generation / proposals / analyst chat
- Reference (OREDA/ISO) ingest and search
- Excel export/import (`docs/api/excel.md`)
- Demo seed `POST /demo/upp100`

## Errors

```json
{"error": {"code": "...", "message": "...", "entity": null, "entity_id": null}}
```

Health: `GET /health`, `GET /ready` (also under `/api/v1`).

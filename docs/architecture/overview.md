# Architecture overview

Modular monolith for AI-assisted RAM modelling of process plants.

## Layers

```text
Browser (React)
  → FastAPI routers (thin DTO → use case)
    → application services
      → domain entities / rules
      → ports (AI, Fabricate, Petri-Pilot, JobRunner)
        → infrastructure adapters
        → simulation (pure RAM engine)
```

## Four levels (do not mix)

1. **Digital Twin** — Domain DB (editable `DRAFT` versions).
2. **Reliability Model** — immutable compiled snapshot + `model_hash`.
3. **Petri Model** — derived P/T network for formal checks.
4. **RAM Simulation** — Monte Carlo results keyed by fingerprint.

## Source of truth

Domain DB only. Excel, LLM, Fabricate artefacts, Petri JSON and UI
views are derived representations (ADR-002).

## Related docs

- Boundaries: `boundaries.md`
- Decisions: `decisions.md`
- Petri-Pilot: `petri-pilot.md`
- Excel exchange: `../api/excel.md`

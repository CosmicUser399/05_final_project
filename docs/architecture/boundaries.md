# Boundaries

## Allowed dependencies

| Layer | May import |
|-------|------------|
| `domain` | stdlib, pydantic (validation only), numpy/scipy maths |
| `application` | domain, ports, infrastructure UoW/repos |
| `infrastructure` | domain, external SDKs, SQLAlchemy, openpyxl |
| `simulation` | domain value objects / compiled model only |
| `api` | application services, DTOs |

## Forbidden

- Domain must not import FastAPI, SQLAlchemy, OpenAI, MCP, openpyxl.
- Routers hold no business rules.
- React holds no authoritative engineering calculations.
- AI has no SQL, shell, or filesystem write tools.
- Excel / Fabricate never write Domain DB without review/commit use cases.

## External ports

- `AIProvider`, `FabricateProvider`, `PetriPilotPort`,
  `SimulationJobRunner`, `EquipmentProposalProvider`.
- Each port has a Mock used by tests.

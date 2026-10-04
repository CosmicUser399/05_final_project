# Domain entities

Core aggregates live under `backend/app/domain/`.

## System lifecycle

- `System` — plant / unit container.
- `SystemVersion` — `DRAFT | VALIDATED | RELEASED | ARCHIVED`.
  Frozen from `VALIDATED`; edits clone to a new `DRAFT` with the same
  `lineage_id`.

## Structure

- `Equipment`, `EquipmentComponent`, `EquipmentConnection`
- `Taxonomy` / `TaxonomyNode` (business + ISO 14224 trees)

## Reliability

- `FailureMode` with embedded `PFInterval` (first-class)
- `FailureDistribution` + `Provenance`
- `ReliabilityStructure` (+ members): SERIES / PARALLEL / K_OF_N / STANDBY

## Maintenance & diagnostics

- `MaintenanceTask` (`INSPECTION | PREVENTIVE | CORRECTIVE`)
- `MaintenanceDistribution`, `MaintenanceEffect`
- `DiagnosticTask` (separate from maintenance)
- `Resource`, `SparePart` and requirements

## Production

- `ProductionFunction` (nominal rate)
- `ProductionImpact` (`loss_fraction` on equipment / failure mode)

## Scenarios & simulation artefacts

- `Scenario` / `ScenarioVersion` / `ScenarioChange` (overlay)
- Compiled reliability / Petri / simulation rows persist outside pure
  domain modules (infrastructure).

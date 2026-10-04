# Excel import / export

Boundary adapter only (Package §60, P12-01). Domain DB remains the
source of truth.

## Workbook sheets

Systems, Equipment, Components, Connections, FailureModes,
FailureDistributions, PFIntervals, Maintenance, MaintenanceEffects,
Diagnostics, Resources, SpareParts, Production.

Links use equipment **tags** (and failure mode / maintenance names),
not opaque UUIDs, so files are reviewable offline.

## Pipeline

```text
Export: DB → Domain → Excel
Import: Excel → DTO → validation → preview → commit → Domain DB
```

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/versions/{id}/excel` | Download `.xlsx` |
| POST | `/versions/{id}/excel/preview` | Validate multipart upload |
| POST | `/versions/{id}/excel/import` | Commit into **empty** DRAFT |

Limits: max 20 MB; file must be ZIP/OOXML (`PK` magic).

## Round-trip

`DB → Excel → DB` preserves supported structural and reliability fields
(see `backend/tests/api/test_p12_excel.py`).

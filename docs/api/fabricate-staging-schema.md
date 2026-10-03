# Fabricate staging schema (v1)

Target schema for SQLite artifacts produced by Fabricate. The runtime
`StagingImporter` accepts only the whitelisted tables and columns below.
Numeric reliability parameters are **not** imported by default.

Schema version: `1` (`FABRICATE_STAGING_SCHEMA_VERSION`).

## Tables

### `equipment` (required)

| Column | Type | Required | Notes |
|--------|------|----------|-------|
| tag | TEXT | yes | Unique within artifact; max 64 |
| name | TEXT | yes | Display name |
| description | TEXT | no | |
| parent_tag | TEXT | no | Must exist in `equipment.tag` |
| category | TEXT | no | Allowed: `PROCESS`, `ROTATING`, `STATIC`, `ELECTRICAL`, `INSTRUMENT`, `UTILITY`, `OTHER` |
| equipment_class | TEXT | no | Free text class label |
| equipment_type | TEXT | no | Free text type label |
| location | TEXT | no | |
| quantity | INTEGER | no | Default 1; 1..10000 |
| criticality | TEXT | no | `LOW`/`MEDIUM`/`HIGH`/`CRITICAL` |
| operating_mode | TEXT | no | `CONTINUOUS`/`INTERMITTENT`/`STANDBY` |
| standby_mode | TEXT | no | `NONE`/`COLD`/`WARM`/`HOT` |
| is_repairable | INTEGER/BOOL | no | Default true |

Tag notation: opaque plant tags (`P-101`, `E-201`, `C-301`); no real
site names required.

### `components` (optional)

| Column | Type | Required |
|--------|------|----------|
| equipment_tag | TEXT | yes |
| name | TEXT | yes |
| description | TEXT | no |
| quantity | INTEGER | no |

### `connections` (optional)

| Column | Type | Required |
|--------|------|----------|
| from_tag | TEXT | yes |
| to_tag | TEXT | yes |
| connection_type | TEXT | no (`PROCESS` default) |
| description | TEXT | no |

Allowed `connection_type`: `PROCESS`, `MATERIAL`, `ENERGY`,
`ELECTRICAL`, `CONTROL`, `SIGNAL`, `UTILITY`, `DEPENDENCY`.

### `failure_modes` (optional, draft only)

Imported as structure with `value_status=UNKNOWN`. Distribution
parameters and PF are **ignored** unless the user later confirms them.

| Column | Type | Required |
|--------|------|----------|
| equipment_tag | TEXT | yes |
| name | TEXT | yes |
| description | TEXT | no |
| is_detectable | INTEGER/BOOL | no |

### `maintenance_tasks` (optional, draft only)

| Column | Type | Required |
|--------|------|----------|
| equipment_tag | TEXT | yes |
| name | TEXT | yes |
| task_type | TEXT | no |

## Validation rules (importer)

1. SQLite file, size ≤ `FABRICATE_MAX_ARTIFACT_BYTES`.
2. `PRAGMA integrity_check` must return `ok`.
3. Open read-only; never attach to Domain DB.
4. Only whitelisted tables/columns; unknown tables ignored.
5. Unique `equipment.tag`; parent/connection tags must exist.
6. No parent cycles; row count ≤ `FABRICATE_MAX_EQUIPMENT_ROWS`.
7. Provenance: `AI_ESTIMATE`, `generated_by=fabricate`, `confidence=LOW`,
   `source_reference=<conversation_id>`.

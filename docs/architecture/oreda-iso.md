# OREDA / ISO 14224 reference data (P11)

## Spike (P11-01)

Licensed OREDA and ISO 14224 PDFs are **local only**
(`reference_data/oreda/*.pdf`, `reference_data/iso14224/*.pdf`,
gitignored). They are not redistributed with the repository.

Decision: **semi-automatic ingestion**

1. Extract candidate tables from the local PDF (text layer or OCR).
2. Engineer reviews rows and produces curated CSV/JSON.
3. Application loads curated files into Domain DB via repositories.

Blind PDF parsing is out of scope for MVP. The shipped demo seeds under
`backend/app/infrastructure/reference_data/seeds/` are **synthetic
values for software testing**, not handbook content.

## Schema

- `reference_sources` — bibliographic record (type, title, edition,
  locator).
- `reference_parameters` — curated numeric rows with
  value / unit / source_type / source_document / source_reference /
  confidence (M011).
- `taxonomies` / `taxonomy_nodes` — ISO 14224 tree
  (`kind=ISO_14224`); equipment links via `equipment.taxonomy_node_id`.

## Adapters

- `OREDARepository` — CSV ingest + search (no hard-coded rates in
  business logic).
- `ISO14224Repository` — JSON taxonomy ingest + code/name search.

## Application / API

`ReferenceDataService` exposes ingest, search, suggest, link equipment,
and apply parameter → `FailureDistribution` with `Provenance.oreda(...)`.

| Method | Path |
|--------|------|
| GET | `/api/v1/reference/status` |
| POST | `/api/v1/reference/ingest` |
| GET | `/api/v1/reference/parameters` |
| GET | `/api/v1/reference/taxonomy` |
| GET | `/api/v1/reference/suggest` |
| POST | `/api/v1/reference/equipment/{id}/link` |
| POST | `/api/v1/reference/equipment/{id}/auto-link` |
| POST | `/api/v1/reference/parameters/{id}/apply` |

## AI integration (P11-04)

1. Proposal review attaches `reference_suggestions` per equipment item
   (ISO node + OREDA rows) before AI_ESTIMATE is treated as a fact.
2. On proposal commit, `auto_link_equipment` maps class → ISO node when
   a match exists.
3. Analyst tool `reference.search` queries loaded parameters/taxonomy.

## UI

- `/reference` — browser (DataGrid + filters) and Provenance panel
  (value, source, reference, confidence).
- `ProvenanceBadge` / `ProvenancePanel` used in proposal review and
  reference browser; AI_ESTIMATE remains visually distinct from
  OREDA / ISO_14224.

# OREDA reference documents (local only)

Place licensed OREDA PDF handbooks here for the **semi-automatic**
ingestion workflow (P11-01). PDF files are gitignored and must not be
redistributed with the repository.

## Workflow

1. Extract candidate tables from the local PDF (text layer or OCR).
2. Review rows manually and save a curated CSV.
3. Load the CSV via `POST /api/v1/reference/ingest` or replace the
   demo seed under
   `backend/app/infrastructure/reference_data/seeds/`.

The shipped `oreda_demo_parameters.csv` contains **synthetic demo
values for software testing**, not handbook content.

# E2E (Playwright)

UI smoke tests for the Docker deployment entry point
(`http://localhost:18080`).

The full Package §101 acceptance flow is implemented as an API
integration test: `backend/tests/api/test_p12_acceptance.py`
(Mock AI / Petri, no live external services).

## Run

```powershell
# App must already be up (docker compose or local vite+uvicorn)
cd e2e
npm install
npx playwright install chromium
npm test
```

Override base URL:

```powershell
$env:E2E_BASE_URL = "http://localhost:18080"
npm test
```

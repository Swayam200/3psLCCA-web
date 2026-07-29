# Calculation Backend Setup

All LCCA calculations run on a small FastAPI backend (in `backend/`) that
wraps the [`3psLCCA-core`](https://github.com/3psLCCA/3psLCCA-core) Python
engine. The frontend sends the project JSON to the backend, which adapts it to
the core engine's schema, runs `run_full_lcc_analysis`, and returns the
results.

## Prerequisites

- Python **3.12+**
- A checkout of the `3psLCCA-core` repository (the calculation engine)

## 1. Get the core engine

`backend/requirements.txt` installs the core engine from a sibling checkout at
`../../3psLCCA-gui-python-venv/3psLCCA-core` (the layout used by the desktop
project). Either recreate that layout, or edit the last line of
`backend/requirements.txt` to point at your core checkout, e.g.:

```text
-e /absolute/path/to/3psLCCA-core
```

or install straight from GitHub:

```text
three_ps_lcca_core @ git+https://github.com/3psLCCA/3psLCCA-core.git@main
```

## 2. Create the environment and run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## 3. Point the frontend at it

The frontend defaults to `http://localhost:8000`. To use a different URL, set
it in `.env`:

```bash
VITE_LCCA_API_URL=https://lcca-api.example.com
```

## API

| Method | Path | Body | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | — | Liveness check |
| `POST` | `/api/lcca/validate` | `{ project, analysis_period_years, debug }` | Validate a project without calculating |
| `POST` | `/api/lcca/calculate` | `{ project, analysis_period_years, debug }` | Run the full LCC analysis |

`project` is the app's project JSON (the same shape the frontend stores). The
adapter in `backend/app/adapters/web_to_core.py` converts it into the core
engine's `input_data` / `construction_costs` / `wpi` structures.

## CORS

`backend/app/main.py` allows `http://localhost:5173` and
`http://localhost:5174` by default. When deploying the frontend elsewhere, add
its origin to the `allow_origins` list.

## Tests

```bash
cd backend
source .venv/bin/activate
pytest -q
```

The suite covers the web→core adapter (validation rules, schema mapping) and
the API endpoints.

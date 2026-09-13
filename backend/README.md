# 3psLCCA Web Backend

FastAPI backend for the web app. It imports `three_ps_lcca_core` only and does not import the desktop GUI package or PySide/PyQt modules.

The requirements install the same hash-pinned core 1.0.2 release as the browser.
A sibling engine checkout is not required.

## Local dev

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Then run the Vite frontend from the repo root:

```bash
npm run dev
```

Set `VITE_LCCA_API_URL` if the backend is not running at `http://localhost:8000`.

## Tests

```bash
cd backend
source .venv/bin/activate
pytest -q
```

From the repository root, `npm run test:backend` also locates the virtual
environment on macOS, Linux, and Windows. Set `LCCA_PYTHON` to select another
interpreter. The canonical setup and testing instructions are in
[tests/README.md](../tests/README.md).

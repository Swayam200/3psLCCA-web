# Static WebAssembly calculation engine

The production build runs `3psLCCA-core` inside the browser through a
self-hosted Pyodide/CPython WebAssembly runtime. FastAPI is not used unless
`VITE_LCCA_ENGINE=backend` is explicitly set for development.

## Build

The core repository must be available beside the web repository at
`../3psLCCA-gui-python-venv/3psLCCA-core`, or supplied through
`LCCA_CORE_PATH`.

```bash
npm ci
npm run build
```

The build creates a self-contained `dist/` containing the interface, Web
Worker, Pyodide runtime, core wheel, checksum manifest and native reference
output. Deploy only this folder to any static host.

For hosting under a subdirectory, build with its public path:

```bash
VITE_BASE_PATH=/3pslcca/ npm run build
```

## Verify

```bash
npx playwright install chromium
npm run test:wasm
```

`wasm-smoke.html` runs a calculation and compares the complete result against
the native CPython reference generated during the build.

## Optional development backend

```bash
VITE_LCCA_ENGINE=backend VITE_LCCA_API_URL=http://localhost:8000 npm run dev
```

The backend is a separate engine adapter. Removing it later does not require
changes to React components or the WebAssembly engine.

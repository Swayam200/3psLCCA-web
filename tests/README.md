# Testing 3psLCCA Web

The suite protects desktop-compatible calculations, project data, UI workflows,
and reports. It builds on the original Node and pytest regressions; it does not
replace expected values with outputs from the implementation under test.

## Fresh checkout

Use Node 22 (latest patch; minimum 22.12) and npm. `.nvmrc` and CI select Node 22.
Python 3.12 is needed only for backend and native/browser parity checks.

```sh
nvm use                         # optional, if using nvm
npm ci
npm run lint
npm test
npx playwright install chromium
npm run test:e2e
```

On Linux CI, install browser OS dependencies with
`npx playwright install --with-deps chromium`.

No `.env`, Appwrite account, backend server, AI key, or model download is needed
for the ordinary JavaScript and browser tests. Component tests use isolated
storage. Browser tests build the real production app into a temporary directory,
serve it on `127.0.0.1:4175/3psLCCA-web/`, mock calculation responses where needed,
and block external requests. They do not prove real-engine numerical parity;
use the dedicated parity command for that.

Install the backend separately:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
npm run test:backend
```

Windows: use `py -3.12 -m venv backend/.venv` and
`backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt`.
The npm command locates the correct platform-specific executable. Set
`LCCA_PYTHON` to use another interpreter. To develop a local core checkout,
explicitly install it with that interpreter's `pip install -e /path/to/3psLCCA-core`.
Normal setup uses the hash-pinned **1.0.2** wheel already used by the browser,
not a sibling directory or the latest engine branch.

## Commands and scope

| Command | Scope | External prerequisites |
| --- | --- | --- |
| `npm test` | Node unit/integration/build tests plus Vitest component/service tests | npm dependencies |
| `npm run test:unit` | Pure JS logic, schema, AI rules, API test doubles | None after install |
| `npm run test:integration` | Archives, Excel, report models, regressions, mocked storage | None after install |
| `npm run test:components` | Real React context and modal interactions | None after install |
| `npm run test:build` | AI flag on/off bundles, base paths, 404 app shell | None after install |
| `npm run test:e2e` | Guest, creation, editing/persistence, routes, calculations, exports, printable reports | Installed Chromium; free port 4175 |
| `npm run test:backend` | Native adapter, API, bridge | Python environment with core |
| `npm run verify:parity` | Global/India results under Pyodide versus native Python | Python/core plus runtime/engine downloads |
| `npm run test:report` | Full Pyodide-generated LaTeX versus reviewed golden | Pyodide package downloads |
| `npm run test:coverage` | Node coverage in terminal; component/service HTML and LCOV | npm dependencies |
| `npm run test:demo` | Independent `ai-demo` prototype; starts/stops its isolated server | Free port 4176 |
| `npm run lint` | Maintained source, tests, workers, build scripts/config | npm dependencies |

Every Node suite entry point prepares the generated SCC database and report ZIP.
The full Pyodide report test is deliberately skipped in `npm test`; this is
explicit in its output. A requested runtime check must pass, not silently skip.
The standalone prototype remains separate from the production application's AI.
Its runner clears provider keys and blocks provider calls, including invalid-key
tests. It never reuses an existing demo server.

## Layout and runner ownership

```text
tests/
  unit/                 Node *.test.js; AI logic under unit/ai/
  integration/          Node *.test.js; Vitest service *.spec.js
  components/           Vitest *.spec.jsx
  e2e/                  Playwright *.spec.js
  build/                Node tests that inspect actual production bundles
  fixtures/             Shared reference projects and reviewed report goldens
  helpers/              Isolated storage and test setup
backend/tests/          pytest adapter/API/bridge tests and fixtures
```

The Node dispatcher explicitly selects `.test.js`; Vitest explicitly selects
component/service `.spec` files; Playwright only discovers `tests/e2e/`. Avoid
adding tests outside those boundaries. Existing report fixture paths remain
stable for scripts and Python consumers. Historical phase/date regressions now
live in `projectCompatibility.test.js` and `carbonReportRegression.test.js`.

## Run one test and debug

```sh
npm run test:unit -- --test-name-pattern="traffic"
npm run test:integration -- --test-name-pattern="archive"
npx vitest run tests/integration/projectStorage.spec.js
npx vitest tests/components/projectModals.spec.jsx
npm run test:e2e -- --grep "renaming" --headed
npm run test:backend -- -k india
npx playwright show-report
```

Node name filters apply to the Node portion of a suite; `test:integration` still
runs its Vitest service tests. Use Vitest directly for a service-specific filter.
The default browser runner uses no retries. Failures retain traces and screenshots
in `test-results/`; the HTML report is in `playwright-report/`. The report workflow
attaches its generated PDF. These outputs are ignored by Git.

`coverage/components/index.html` describes the explicitly listed context, storage,
and modal modules; it is **not** whole-application coverage. Node coverage is
printed separately. Add coverage for important uncovered branches before raising
coverage expectations; do not chase a percentage with implementation-only tests.

## How to add a useful test

1. Choose the smallest level that exposes the behavior. Use Node for numerical
   transforms, Vitest for rendered components/services, and Playwright for a user
   journey across pages. Backend tests exercise the shared Python adapter.
2. Use a small, fixed fixture. Clone mutable inputs; isolate storage, clocks,
   environment settings, and service doubles; restore globals after each test.
3. Name the observable result and trigger. Include failure/boundary cases where
   meaningful: zero is valid, missing is not zero, units differ, IDs collide,
   saves fail, or a legacy archive uses an alias.
4. Assert results, visible behavior, and persisted data. Do not inspect source
   text to prove a UI works. The bundle tests are intentionally different: they
   inspect the artifact users receive.
5. Preserve unrelated fixture fields and reviewed numerical tolerances. Read
   `fixtures/README.md` before changing golden files.
6. Run the affected suite and the checks listed in root `AGENTS.md`.

## CI and current boundaries

`tests.yml` runs lint, ordinary tests/coverage, the prototype, Chromium workflows,
and backend tests on pull requests and main. `runtime-tests.yml` runs real engine
and report parity for relevant pull requests, main, and manual dispatch. The
deployment workflow also checks lint and the default test suite before building.
Repository administrators can make these checks required in branch protection.

Appwrite tests verify the existing sequential local-first contract with mocks.
Live account permissions, overlapping cloud-save races, corrupt full-project
storage recovery, and offline cloud-deletion recovery need separate behavior
work and dedicated acceptance criteria. This cleanup intentionally does not
change those behaviors. Real AI models remain an opt-in manual evaluation;
see `docs/ai-smoke-test.md`. Existing engine/report goldens are retained.

## Troubleshooting

- **Core import fails:** install `backend/requirements.txt` using the exact
  interpreter selected by `LCCA_PYTHON`; the parity preflight reports it.
- **Network unavailable:** run ordinary tests; report parity/runtime checks as
  blocked instead of claiming a complete pass.
- **Chromium missing:** rerun `npx playwright install chromium` using this repo's
  installed Playwright version. Do not upgrade the library to fix a missing browser.
- **Port 4175 in use or sandbox denies listening:** free that port or allow the
  isolated test server; it never reuses a developer's existing app server.
- **Golden mismatch:** compare the first differing value/line and engine version.
  Follow fixture review instructions; do not weaken assertions or update blindly.
- **Existing runtime/dependency warnings:** investigate separately from assertion
  failures. This cleanup does not upgrade React, the Python web stack, or engines.

# Contributor instructions for coding agents

Read `readme.md` for the application and `tests/README.md` for setup, suite
boundaries, and commands. The testing README is the canonical command reference;
do not create a second copy of it in another agent-specific file.

## Architecture and compatibility

- React/Vite browser application: `src/App.jsx`, `src/contexts/`, `src/gui/`.
- Normalization, derivations, and archives: `src/utils/`.
- Browser/backend selection: `src/lib/lccaApi.js` and `src/lib/lccaEngine/`.
- Shared web-to-core adapter: `backend/app/adapters/web_to_core.py`. It is also
  loaded as raw source into Pyodide; changes affect both execution paths.
- Persistence: `src/lib/projectStorageService.js`; Appwrite is optional.
- Reports: `src/report/` plus `src/gui/components/outputs/`. HTML, desktop LaTeX,
  and the jsPDF fallback are active paths. Preserve all unless explicitly asked.
- Legacy route and schema aliases preserve desktop archives and saved links.
  Verify usage before deleting anything that looks redundant.

## Verification by changed area

Run from the repository root:

| Changed area | Checks |
| --- | --- |
| Any maintained JS/JSX/script | `npm run lint`, `npm test` |
| Components, routing, state, storage | Above plus `npm run test:e2e` |
| Adapter/backend/core integration | `npm run test:backend`, `npm run verify:parity` |
| Reports/fixtures/runtime packaging | `npm run test:report`, `npm run test:e2e` |
| Production dependencies, flags, deployment | `npm run test:build`, `npm run build` |
| Standalone AI prototype | `npm run test:demo` |

`npm test` intentionally skips the full Pyodide report execution. Run
`npm run test:report` to execute it. Engine parity and runtime checks need network
access; backend checks need the pinned engine installed. Report actual failures,
skips and unavailable prerequisites separately; do not claim they passed.

## Editing and testing rules

- Preserve behavior and dependency versions during cleanup/refactoring tasks.
- Keep numerical tolerances and reviewed golden fixtures intact. A failing
  golden is evidence to investigate, not permission to regenerate expected data.
- Use `.test.js` for Node tests, `.spec.jsx` for Vitest components,
  `.spec.js` in `tests/integration/` for Vitest services, and `.spec.js` in
  `tests/e2e/` for Playwright. See `tests/README.md` before adding a test.
- Test observable behavior with isolated fixtures/storage; mock Appwrite and AI
  in ordinary tests. Never use a developer's account or real project data.
- Keep tests deterministic; use assertions that wait for state rather than sleeps.
- Preserve external effects when removing unused bindings (`await account.get()`
  must still run even if its returned value is unused).
- Keep lint exceptions local and explain why behavior requires them. Existing
  form synchronization exceptions are intentional; do not change effect timing
  or dependencies just to remove an exception.
- `public/data/cscc/`, `public/report/runtime.zip`, `dist/`, coverage and test
  reports are generated. `public/vendor/` and `vendor/report-runtime/` contain
  upstream code; use the documented synchronization scripts for vendor changes.
- Do not include unrelated local changes in the task's edits.

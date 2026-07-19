# 3ps-web × WASM Core — Integration Plan (CDN-first)

_Date: 2026-07-19 · Working branch: `feat/wasm-cdn-engine` (cut from `feat/wasm-static-web`)_
_Core: `Swayam200/3psLCCA-core@main` (merged, CI green, wasm-demo on GitHub Pages)_

## Branching strategy (frozen vs working)

| Branch | Repo | Role |
|---|---|---|
| `feat/wasm-static-runtime` | 3psLCCA-core | **FROZEN** — presentation material; no further pushes |
| `feat/wasm-static-web` | 3psLCCA-web | **FROZEN** — presentation baseline; no further pushes |
| `feat/wasm-cdn-engine` | 3psLCCA-web | **working branch** — all CDN-first changes land here |
| `main` (both repos) | — | untouched for now; merges happen post-presentation (Phase 5) |

The web CI's core checkout (`static-wasm.yml:19`, `ref: feat/wasm-static-runtime`) is a
read-only checkout — it doesn't modify the frozen branch, and core `main` has identical
content, so leave the ref as-is for now to avoid churn. Repoint to a core tag in Phase 5.

## 0. Where things stand

`feat/wasm-static-web` already contains a complete, tested in-browser pipeline:

| Piece | Status | Where |
|---|---|---|
| Pyodide runtime in a Web Worker | ✅ done | `src/lib/lccaEngine/lcca.worker.js` |
| Engine facade (WASM default, FastAPI dev-only) | ✅ done | `src/lib/lccaApi.js` |
| Python adapter (web project JSON → core schema) | ✅ done, single source | `src/wasm/python/web_to_core.py` (backend re-exports it) |
| JSON bridge, `debug=False` | ✅ done | `src/wasm/python/bridge.py` |
| Wheel build + manifest (sha256) + parity fixtures | ✅ done | `scripts/prepare-wasm-assets.mjs` |
| App wiring (Outputs page → WASM engine) | ✅ done | `src/gui/components/outputs/Outputs.jsx` |
| In-browser LaTeX report (SwiftLaTeX, local TeX Live) | ✅ done | `latexReportEngine.js` + `public/vendor/swiftlatex/` |
| Playwright: native parity + fully-static proof | ✅ done | `tests/wasm-static.spec.js` |
| CI build + subdir-hosting check (no deploy step) | ✅ done | `.github/workflows/static-wasm.yml` |

**What changes with the CDN-first decision:** the engine assets (Pyodide runtime + core
wheel) load from CDN as the **primary** source, with the **bundled copies in `dist/` as
automatic fallback**. The app itself deploys to GitHub Pages from this branch for testing.

### Asset sourcing model

| Asset | Primary (CDN) | Fallback (bundled) |
|---|---|---|
| Pyodide runtime (~13 MB) | jsDelivr: `https://cdn.jsdelivr.net/pyodide/v0.28.x/full/` (pin to the version in `package.json`) | `dist/pyodide/` (already shipped) |
| Core wheel (~80 KB) | Core repo's GitHub Pages: `https://swayam200.github.io/3psLCCA-core/wasm-demo/<wheel>.whl` — or jsDelivr-over-GitHub: `https://cdn.jsdelivr.net/gh/Swayam200/3psLCCA-core@main/wasm-demo/<wheel>.whl` | `dist/lcca-wasm/<wheel>.whl` (already shipped) |
| TeX Live for reports (~33 MB) | **stays bundled** (SwiftLaTeX local mode; CDN-ing 1,258 small files buys nothing) | `public/vendor/swiftlatex/texlive/` |
| Adapter/bridge Python source | n/a — inlined into the JS bundle via `?raw` imports | same |

Integrity: the wheel's sha256 already lives in `lcca-wasm/manifest.json`. CDN-fetched
wheels MUST be verified against that hash before install — this makes CDN vs bundled
functionally identical and protects against a stale/tampered CDN copy.

> Note on jsDelivr `@main`: it caches aggressively (~12 h) and `@main` moves. Prefer
> pinning to a commit or tag (`@<sha>` / `@v0.1.0`) once core is tagged; until then the
> sha256 check is the safety net — on mismatch we fall back to the bundled wheel.

---

## Phase 1 — CDN-first loading with bundled fallback (the actual code change)

All changes are inside `src/lib/lccaEngine/lcca.worker.js` + a small config surface:

1. **Config via env, with sane defaults** (in `wasmEngine.js`, passed to the worker):
   - `VITE_LCCA_PYODIDE_CDN` — default `https://cdn.jsdelivr.net/pyodide/v<pinned>/full/`
   - `VITE_LCCA_WHEEL_CDN` — default the core repo's GitHub Pages wheel URL
   - Empty string ⇒ skip CDN, bundled-only (keeps local dev and Playwright offline-capable).
2. **Loader order** in the worker:
   1. Try `import(pyodideCdn + 'pyodide.mjs')` → `loadPyodide({ indexURL: pyodideCdn })`.
   2. On any failure (network error, timeout ~10 s), fall back to the existing
      `assetUrl('pyodide/pyodide.mjs')` local path. Log which source won.
   3. Fetch wheel from `VITE_LCCA_WHEEL_CDN`; verify sha256 against `manifest.json`;
      on fetch failure or hash mismatch, fall back to `lcca-wasm/<wheel>` local.
3. **Surface the source in status** — extend the engine status payload with
   `assetSource: 'cdn' | 'bundled'` so `Outputs.jsx` can show "Engine: Browser
   WebAssembly (CDN)" vs "(bundled)". Cheap and makes demos/debugging obvious.
4. **Manifest still rules versions.** `prepare-wasm-assets.mjs` keeps writing
   `manifest.json` (wheel filename, sha256, coreVersion, pyodideVersion) at build time —
   the CDN URLs are derived from it, so bumping the core wheel remains one script run.
5. **Version discipline (core side, small ask):** keep the wheel filename in
   `Swayam200/3psLCCA-core` `wasm-demo/` stable or update `manifest.json` in lockstep;
   tagging core `v0.1.0` soon would let us pin jsDelivr to a tag instead of `@main`.

## Phase 2 — Test updates (the static-proof test must learn about CDN)

`tests/wasm-static.spec.js` currently asserts **all requests are same-origin** — that
test would fail the moment CDN loading works. Split it:

1. **Bundled mode test (unchanged guarantee):** run the built site with CDN env vars
   empty → assert same-origin-only + native parity. This preserves the "works fully
   static/offline" proof.
2. **CDN mode test (new):** run with CDN vars set → assert requests only go to
   same-origin + the two allow-listed CDN origins (`cdn.jsdelivr.net`,
   `swayam200.github.io`), and parity still holds.
3. **Fallback test (new, the important one):** CDN vars set but routes to CDN origins
   blocked via Playwright `context.route()` abort → engine must still initialize from
   bundled assets and produce parity results. This is the test that proves "backup"
   actually works.

## Phase 3 — Deploy 3ps-web to GitHub Pages from the working branch (testing target)

No merge to `main` for now — Pages deploys straight from `feat/wasm-cdn-engine`:

1. Add a `deploy-pages` job to `.github/workflows/static-wasm.yml`, triggered on push to
   `feat/wasm-cdn-engine` (and `workflow_dispatch`), gated on the existing build+test
   jobs. Use `actions/configure-pages` + `actions/upload-pages-artifact` +
   `actions/deploy-pages` — this deploys the CI-built `dist/` artifact, so we never
   commit `dist/` (77 MB) to git.
2. Build with `VITE_BASE_PATH=/3psLCCA-web/` (subdir hosting is already CI-verified)
   and the CDN env vars set. Live URL: `https://swayam200.github.io/3psLCCA-web/`.
3. Core checkout ref stays on `feat/wasm-static-runtime` (read-only, identical to core
   `main`, keeps the frozen branch untouched) — see Branching strategy above.
4. **Appwrite:** add `https://swayam200.github.io` to allowed platforms in the Appwrite
   console, or login/sync will CORS-fail on the deployed site. Guest mode works either way.
5. Post-deploy verification on the live URL: run India + Global calculation, generate a
   report PDF, check DevTools — engine assets from CDN, everything else same-origin,
   and status badge shows the CDN source. Then kill the network mid-refresh… no wait,
   simpler: verify fallback by temporarily setting a bogus CDN URL via a
   `workflow_dispatch` build input.

## Phase 4 — Hardening (unchanged, still worth it)

1. **Warm-up:** call `initializeLccaEngine()` on project open (not first Calculate) —
   with CDN primary this also front-loads the 13 MB Pyodide download while the user
   types.
2. **First-load hint:** "first load downloads ~13 MB, cached afterwards" near the
   engine status in `Outputs.jsx`; keep Calculate disabled until `ready`.
3. **Caching:** jsDelivr handles CDN caching; GitHub Pages fixes ~10 min for bundled —
   acceptable for a test deployment.
4. **Adapter path hygiene:** remove/guard the native-only `sys.path` probing at the top
   of `src/wasm/python/web_to_core.py` (can never fire under Pyodide).

## Phase 5 — Later (post-presentation, when the team is ready)

1. Merge `feat/wasm-cdn-engine` → web `main` (it contains everything from
   `feat/wasm-static-web` plus the CDN work); repoint Pages to `main`. The frozen
   presentation branches can then be deleted or kept as historical markers.
2. Tag core `v0.1.0`; pin the wheel CDN URL to the tag, repoint the web CI's core
   checkout from the frozen branch to that tag; consider a
   wheel-from-GitHub-release mode in `prepare-wasm-assets.mjs` (checksum-verified) so
   contributors don't need the sibling core checkout.
3. Retire `backend/` + `backendEngine.js` + `VITE_LCCA_API_URL` (already dev-only,
   nothing in React depends on them).
4. Desktop-parity roadmap (separate track): multi-project comparison, WPI custom
   profiles + hash-integrity UX, report section-toggle dialog, Excel import of
   construction data.

## Verification gates

| Gate | Command | Proves |
|---|---|---|
| Unit | `npm run test` | report model/engine, schema logic |
| Bundled parity | build with CDN vars empty → `npm run test:wasm` | fully static/offline still works |
| CDN parity | build with CDN vars set → CDN-mode spec | CDN loading works, origins allow-listed |
| Fallback | CDN-mode build + blocked CDN routes | bundled backup actually kicks in |
| Report | swiftlatex Playwright spec | in-browser PDF compiles |
| Core | core repo CI | engine correctness independent of web |

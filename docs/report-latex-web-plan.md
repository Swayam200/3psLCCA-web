# Desktop-identical LaTeX report on the web — architecture plan

Plan: Swayam/Claude · Status: **R0 spike passed** (both legs), 2026-08-18

## R0 results (reference project: M_20_2L_OF_S, Mumbai 20m 2-lane steel bridge)

- **CPython leg:** desktop's `compile_lcca_report_pdf` ran with a 6-line fake
  controller fed by the project's chunks as plain JSON — no engine, no Qt at
  runtime. Output vs the GUI-generated PDF: **40/40 pages, zero text
  differences on any page, every embedded image (logos + all matplotlib
  plots) byte-identical.** 4.2 s end-to-end including pdflatex.
- **Pyodide leg (Python-in-WASM, what the browser runs):** the same modules
  generated the `.tex` under Pyodide in ~2 s (imports 1.5 s, plots 0.3 s,
  build 0.2 s). The `.tex` is **sha256-identical to the CPython one** after
  normalizing three environment-path classes (random temp suffixes on plot
  filenames, FS mount prefixes, OS temp dir). Plot PNGs are visually
  indistinguishable; bytes differ only from freetype/PNG-encoder builds.
- **The compat layer measured** (this is the whole "shim", ~150 lines):
  fake controller (6 lines) · generic PySide6 stub classes · a functional
  `QColor` (~20 lines — theme code does real color math) · cut
  `project_controller` import (kills the engine/psutil chain) · pin
  matplotlib to Agg (plot helpers force QtAgg at import) · synchronous
  `ThreadPoolExecutor` (no threads in WASM).
- Upstream nice-to-haves surfaced (not blockers): guard the module-level
  `matplotlib.use("QtAgg")` in `plots_helper/Pie.py`; desktop bug —
  `report_section_dialog.py` uses Windows-only `os.startfile` to open the
  finished PDF, which crashes the auto-open on macOS
  (`subprocess.run(["open", path])` on darwin fixes it).
- Not covered by R0 (next gate, R2): XeTeX/pdfTeX-WASM compiling this
  template in the browser — evidenced by the archived `d060ca2` stack, to be
  re-verified on today's template.

## R1 results (2026-08-18)

Shipped and tested: `vendor/report-runtime` (desktop Python subtree +
pylatex/ordered_set + 4 output-relevant assets, synced by
`scripts/sync-report-runtime.mjs`), `report-runtime/report_compat.py`
(productionized R0 shim), `scripts/build-report-runtime.mjs` →
`public/report/runtime.zip` (3 MB), `public/report-worker.js` (Pyodide
worker), `src/gui/components/outputs/reportChunks.js` (the one web→desktop
mapper; import now preserves desktop `values`/`meta` losslessly).
Tests: mapper round-trip vs the desktop chunk store; web-data golden
semantically identical to the desktop golden (numbers canonicalized —
JSON→JS collapses `20.0`→`20`, desktop renders whichever it receives);
`npm run test:report` proves Pyodide regenerates the web-data golden tex
byte-exactly.

## R2 complete (2026-08-18): full report compiles in-browser

The engine blocker below is **fixed**. The earlier "fixed internal pool"
theory was wrong — with a debuggable from-source engine build the real
cause surfaced in minutes:

- **Root cause:** upstream SwiftLaTeX hardcodes `-halt-on-error` for
  document compiles, so every *recoverable* TeX error is a fatal exit that
  also loses its message (desktop runs `pdflatex -interaction=nonstopmode`,
  where the same errors recover). The 54-row material table crosses a page
  boundary, and longtable's page split on pre-2025 engines goes through a
  LaTeX-kernel shim that intentionally raises-and-ignores an
  infinite-shrink `\vsplit` error — fatal only under halt-on-error.
  (Modern binaries demote it to `ignored:`; the local MacTeX log shows
  exactly that, and desktop PDFs have always carried it.)
- **Fix:** rebuilt the engine from source (upstream master `87dfb95`,
  emscripten 6.0.7 — see `public/vendor/swiftlatex/BUILD.md` +
  `engine-build.patch`): halt-on-error only for format builds; PDF-file
  existence decides compile success (like the pdflatex CLI); failure
  results now append the `.log` transcript tail so future errors are never
  silent again. Second compat fix while re-testing: the 2026 macro tree
  assumes the `\partokencontext` primitive (TeX Live 2025) exists —
  microtype assigns to it unguarded — so `pdflatex.ini` now aliases it to
  a scratch count register at format-build time.
- **Verified:** full M_20_2L_OF_S report — **38 pages, 2.61 MB, ~15–25 s,
  zero TeX errors, deterministic bytes across runs** — through the
  production vendored path. Parity vs local MacTeX pdflatex on the same
  `.tex`: same page count, **0/38 pages differ** in whitespace-insensitive
  text, and the material-table pages pixel-diff at ≤0.11%. Regression
  variants A/G/J/K all pass. The stale 10 MB `swiftlatexpdftex.fmt` is
  gone (the worker builds the format fresh each session; a dumped format
  only loads on the exact engine build that wrote it).
- Note for R3: the worker compiles once, so `Page n of ??` and TOC/refs
  stay unresolved — wire the standard second pass (desktop does the same).

## R3 + R4 complete (2026-08-18): wired into the app, fallback in place

- `src/gui/components/outputs/latexReportEngine.js` orchestrates the two
  workers (lazy dynamic import — none of this is in the main bundle):
  project data → `desktopChunksForReport` → Pyodide report worker (.tex +
  plots) → path rewrite → SwiftLaTeX worker (**two passes**, resolving TOC
  and "Page n of m" like desktop's double compile) → download.
- Outputs' "Download Report" prefers this engine; on any failure it logs
  the reason and falls back to the existing jsPDF layout automatically
  (R4). The fallback path was exercised for real during testing.
- The section-selection modal's keys are byte-identical to desktop's
  `KEY_SHOW_*` config strings, so selections pass straight through to the
  desktop builder.
- `report-worker.js` is now a **module worker** (pyodide v0.28+/v314
  dropped classic-worker support — this was found the hard way).
- Verified end-to-end in the running app with the M_20_2L_OF_S archive:
  import → in-browser calculation → Generate PDF Report →
  `M_20_2L_OF_S_Report.pdf`, 2.54 MB, ~24 s with warm caches (log:
  runtime 2 s, packages 7 s, tex generation 2 s, format 4 s, two compile
  passes 4 s each). 147 node tests pass, including new `rewriteTexPaths`
  units.
- Deliberately not built: the latex-css HTML preview page from the
  original R3 sketch — the real PDF now arrives in seconds, so a
  lookalike preview adds little; revisit only if user feedback asks for
  an instant on-screen view.

## R2 history (how it looked when blocked)

Restored the archived SwiftLaTeX stack and extended it for today's
template. Working, verified in-browser via `public/report-smoke.html`:

- Vendored texlive tree completed with a **deterministic dependency
  enumeration** (local `pdflatex -recorder` on the reference report → copy
  every kpathsea INPUT by format code: tfm→`3/`, map→`11/`, tex→`26/`,
  pfb→`32/`, vf→`33/`, enc→`44/`).
- Engine patches (documented, in `public/vendor/swiftlatex/swiftlatexpdftex.js`):
  treat `text/html` 200s as not-found (dev-server SPA fallback poisoned
  optional probes like `geometry.cfg`); enable virtual-font (format 33)
  lookups upstream had hard-disabled.
- `ts1ptm.fd` substituted in the vendor tree (TS1/ptm → TS1/cmr): the
  wasm build aborts on the ptmr8c virtual-font path; visual effect limited
  to text-companion glyphs (₂, ³, °) in Times sections.
- **Everything except the material-emissions table compiles: 2.38 MB PDF
  in ~42 s in the browser.** Bisected precisely: the 54-row material table
  crashes the engine while EITHER half (27 rows) compiles, aborting
  without a TeX error. (Diagnosed at the time as a fixed internal pool —
  disproved above; the halves pass because they fit one page and never
  trigger the longtable page-split.) Not content-related: chars, fonts,
  microtype all ruled out by variants D–K in the smoke harness.

## Goal

**Report 1:1 with desktop (LaTeX).** The PDF a web user downloads should be
the same document desktop produces for the same project — same layout, same
tables, same appendices — not a lookalike.

Hard constraints:

- **Zero servers.** GitHub Pages serves static files only; nothing for the
  team to host, run, or keep alive. All computing happens in the visitor's
  browser (lazy-loaded, cached after first use).
- Open source only, no paid services.
- Project data never leaves the user's machine.

## How desktop does it today

```
project data → code_to_latex/ (15 Python modules) → .tex → Tectonic (XeTeX) → PDF
```

The 15 modules are Qt-free pure Python (verified: zero PySide imports).
Their inputs are field definitions plus a thin data-access layer
(`common_requested_data.get_chunk(...)`), and they lean on `pylatex`,
`pandas`, `bs4`, and matplotlib (plots) — all available as Pyodide wheels.

## The decision, split in two

A report pipeline has two stages; "1:1" is only as strong as the weakest:

### Stage 1 — who writes the `.tex`

| Option | 1:1 strength | Cost |
| --- | --- | --- |
| **A. Run desktop's own Python modules in the browser** (Pyodide + a ~100-line shim that makes `get_chunk` read the web project JSON) | Same code ⇒ same bytes, forever. Zero sync effort. | ~25–30 MB lazy Python runtime; shim maintenance |
| **B. Move report generation into 3psLCCA-core** (upstream ask) | Same as A but owned in one shared place, like calculations already are | Needs sir/core-team buy-in; not fork-doable alone |
| C. JS re-implementation of the template (the archived July stack, `latexReport.js` at `d060ca2`) | Equivalent *today*, drifts *tomorrow* — every desktop report change must be hand-ported | Cheapest to start, permanent sync tax |

**Chosen: A now, propose B as the endgame.** A is B implemented fork-side —
the shim work carries over if B lands. C is the fallback if Pyodide weight
is ever deemed unacceptable; it is the same disease (web/desktop drift)
this team keeps having to cure elsewhere, so it is explicitly not first
choice. This mirrors the project's proven pattern: one shared Python
adapter (`web_to_core.py`) + parity tests, not parallel implementations.

### Stage 2 — who compiles `.tex → PDF`

| Option | Verdict |
| --- | --- |
| **TeX compiled to WebAssembly in the browser** (SwiftLaTeX XeTeX/pdfTeX, or newer texlive-wasm builds) | **Chosen.** Real TeX, real PDF, offline, static-host friendly. ~32 MB lazy assets (vendored + pinned; the WASM doesn't rot even if upstream sleeps). Prefer the XeTeX engine to match Tectonic; the desktop template is pdflatex-compatible either way (desktop's own fallback is pdflatex). |
| Local desktop companion (POST `.tex` to the app-api on `localhost:8765`, native Tectonic compiles) | Optional bonus when desktop is installed — literally desktop-identical output. Never the only path. |
| Any server/CI compile | Rejected: violates zero-server, privacy, offline. |
| No compile — HTML/CSS print, Typst, jsPDF layout | Rejected for the deliverable: skips the `.tex` stage, so "similar" is the ceiling, never "same". |

### Where the mentor's latex-css fits

[latex-css](https://github.com/vincentdoerig/latex-css) (MIT, a few KB)
styles HTML like a LaTeX document but produces no PDF. Right home: the
**on-screen "View Report" preview** — instant, no WASM download, looks like
the final document — with the real LaTeX engine behind the "Download PDF"
button on that screen.

## What loads when (the whole budget)

| What | When | Size (one-time, then browser-cached) |
| --- | --- | --- |
| App | on visit | unchanged |
| Preview page + latex-css | opening "View Report" | a few KB |
| Pyodide + pandas/matplotlib/bs4/pylatex + report modules | first "Download PDF" click | ~25–30 MB |
| TeX engine + fonts (WASM) | same first click | ~32 MB |

Users who never generate a PDF download none of it. Heavy assets are
vendored via a build-time restore script (gitignored output, same pattern
as `scripts/build-cscc-db.mjs`) so main's tree stays clean.

## Phases

- **R0 — Feasibility spike (before committing to anything):** run desktop's
  `final_report.py` against a real web-project JSON through the shim —
  first under plain CPython, then under Pyodide. Exit criteria: a `.tex`
  byte-identical to desktop's for the same project. If R0 fails on
  something structural (e.g. `ProjectController` entanglement that can't be
  shimmed cleanly), fall back to Option C and stop pretending otherwise.
- **R1 — Shim + tex generation in-browser:** package the `code_to_latex`
  modules (fetched/vendored at build time from the desktop repo), ship the
  `common_requested_data` shim, produce `.tex` in a web worker.
- **R2 — Compile:** XeTeX-WASM worker turns the `.tex` into a PDF, with
  progress UI for the first-run download/compile. Parity check: side-by-side
  against a desktop-generated PDF of the same project.
- **R3 — Preview:** "View Report" page rendering the same report model as
  HTML styled with latex-css; "Download PDF" lives there.
- **R4 — Safety net:** keep jsPDF as automatic fallback (clearly marked
  "fallback layout") for browsers where WASM fails; tests: shim unit tests,
  tex snapshot test against a fixture project, Playwright smoke compile.
- **R5 (parallel, upstream ask):** propose to sir that report generation
  move into the 3psLCCA-core release so desktop and web consume one
  implementation. The R1 shim is the working prototype of that proposal.

## Risks, stated honestly

- **Pyodide + TeX ≈ 60 MB first-use download.** One-time, lazy, cached; the
  explicit price of "same code, same compiler". Accepted 2026-08-18.
- **Desktop code motion:** if `code_to_latex` gets refactored upstream, the
  vendored copy must be refreshed (a build-time fetch + a parity test makes
  this loud, not silent).
- **SwiftLaTeX upstream is dormant.** Mitigated: engine vendored and
  pinned; active forks (e.g. TeXlyre) exist; the archived `d060ca2` stack
  already proved it compiles this template in-browser.
- **Plots:** matplotlib-in-Pyodide keeps report plots identical to
  desktop's; if its weight ever hurts, the compromise is web-rendered chart
  PNGs (visually different from desktop — a knowing 1:1 exception, decided
  then, not now).

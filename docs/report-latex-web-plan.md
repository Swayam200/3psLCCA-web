# Desktop-identical LaTeX report on the web — architecture plan

Plan: Swayam/Claude · Status: proposed, 2026-08-18

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

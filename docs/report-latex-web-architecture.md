# How the web LaTeX report works — in simple words

Audience: anyone on the team. No web or LaTeX background needed.
Deep technical details live in `report-latex-web-plan.md`; this page is the
plain-language summary plus the maintenance workflow.

## The core idea

**We did not rewrite the desktop report for the web. We run the desktop's
own report code inside the browser.** Same code ⇒ same PDF, permanently.

## The architecture (three stages, all inside the visitor's browser)

```
your project data
      │
      ▼
① Translator (JavaScript)   reshapes web project data into the exact
      │                     "chunks" format the desktop app stores
      ▼
② Desktop's Python code     the desktop app's actual report modules
   running in the browser   (the same .py files) run under Pyodide
      │                     (Python compiled to WebAssembly) and
      │                     produce the .tex file + plots
      ▼
③ A real LaTeX compiler     pdfTeX — the same engine family desktop
   running in the browser   uses — compiled to WebAssembly turns the
      │                     .tex into the final PDF
      ▼
   the report PDF
```

- **Zero servers.** Everything is static files on GitHub Pages. There is
  nothing for the team to host, run, or keep alive.
- **Privacy.** Project data never leaves the visitor's machine.
- **First use** downloads the machinery (~60 MB, then browser-cached).
  Measured on the reference project: first report of a session ≈ 18 s from
  click to PDF, repeat reports ≈ 8 s.

## Does it use 3psLCCA-core? No — and that is correct

- **Numbers** (costs, emissions, NPV math) come from **3psLCCA-core** —
  already shared between desktop and web (web loads it via CDN).
- **The report document** was never in core. It lives in the desktop GUI
  repo (`three_ps_lcca_gui/code_to_latex/`, ~15 Python modules). The web
  ships a **verbatim copy** of those modules plus a ~150-line
  compatibility layer that stands in for desktop-only things they import
  but don't actually use for report content (Qt widgets, the storage
  engine, threads).

Proven equivalence: for the M_20_2L_OF_S reference project, the
browser-compiled PDF has identical text on every page versus a locally
compiled desktop-style PDF (whitespace-insensitive comparison, all 38
pages; table pages differ by ≤ 0.11 % of pixels — font rasterizer noise).

## When desktop's report changes in the future

The vendored copy is not maintained by hand. The update loop is:

1. **`node scripts/sync-report-runtime.mjs`** — re-copies the report
   Python from the desktop repo into `vendor/report-runtime/`
   (`RUNTIME_MANIFEST.json` records exactly what came from where).
2. **`npm run test:report`** — regenerates the report from a reference
   project and compares against golden output.
   - Desktop changed the report content? The diff shows exactly what
     changed; bless the new golden and ship.
   - Desktop added something the compatibility layer doesn't cover (say,
     a new Qt import)? The test fails loudly and points at it.
3. Commit. Minutes, not a re-port.

There is no silent drift: the failure mode is a loud test, never a
quietly different PDF.

## The endgame (upstream proposal, phase R5 in the plan)

Propose moving report generation into **3psLCCA-core** itself, like the
calculations. Desktop and web would then consume literally one shared
implementation and even the sync step disappears. Our compatibility layer
already proves the report code runs fine outside the desktop app — it is
the working prototype of that proposal.

## Suggestions / notes for the team

- **Desktop bugs found during this work** (worth fixing upstream):
  - `report_section_dialog.py` opens the finished PDF with the
    Windows-only `os.startfile`, which crashes on macOS
    (`subprocess.run(["open", path])` on darwin fixes it).
  - The Ricke SCC widget does not restore saved selections when reopened
    and overwrites them with "-- select --" placeholders on close — an
    imported project can silently lose its social-cost-of-carbon data
    (this visibly affects desktop results for imported projects; see
    `results-page-desktop-parity.md`).
- The wasm TeX engine is **built from source by us** (upstream SwiftLaTeX
  shipped no maintained binaries and had a fatal-error bug); recipe and
  patches: `public/vendor/swiftlatex/BUILD.md`.
- Report generation is single-threaded by nature (TeX's algorithm);
  speed-ups come from caching and pipeline overlap, not parallel compute.
  GitHub Pages also cannot serve the headers browser multithreading
  (SharedArrayBuffer) requires.

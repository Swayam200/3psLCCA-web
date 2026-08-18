# SwiftLaTeX pdfTeX engine — build provenance

`swiftlatexpdftex.js` + `swiftlatexpdftex.wasm` are built from source, not
taken from a SwiftLaTeX release (upstream ships no maintained binaries and
its 2020-era build had a fatal-error bug, below).

- Source: https://github.com/SwiftLaTeX/SwiftLaTeX `pdftex.wasm/`,
  commit `87dfb950eb9c8e9dcd4ee2a3ac97fbbbacfc618a` (2024-06-18 master).
- Toolchain: emscripten 6.0.7 (emsdk `latest`, 2026-08).
- Build: `cd pdftex.wasm/xpdf && make`, then `cd .. && make`
  (emsdk env active; emsdk needs python ≥ 3.10, e.g.
  `EMSDK_PYTHON=/opt/miniconda3/envs/3pslcca/bin/python`).
- Local modifications: `engine-build.patch` (apply with `git apply` in the
  SwiftLaTeX checkout). Summary:
  - `main.c` — halt-on-error only for format builds. Upstream set
    `haltonerrorp = 1` for document compiles too, which turned every
    recoverable TeX error into a silent fatal exit. The desktop app runs
    `pdflatex -interaction=nonstopmode` (errors recover); this was the
    "engine crashes on the 54-row material table" R2 blocker — longtable's
    page-split on pre-2025 engines goes through a LaTeX-kernel shim that
    *intentionally* raises and ignores an infinite-shrink error.
  - `pre.js` — (1) PDF-file existence decides compile success (recovered
    errors exit 1 but still produce the PDF, like the pdflatex CLI); the
    caller still sees the full log to apply its own fatal-error policy.
    (2) On failure, the tail of the `.log` transcript is appended to the
    returned log (the terminal stream loses the final error on abnormal
    exit). (3) Static hosting: treat `text/html` 200s as not-found
    (dev-server SPA fallback) and fall back to the request name when the
    server sends no `fileid`/`pkid` header.
  - `Makefile` — export `_malloc`/`FS`/`UTF8ToString`/`intArrayFromString`
    (auto-exported by 2020 emscripten, opt-in now), explicit
    `STACK_SIZE=16MB` (new default is 64KB), `ENVIRONMENT=worker`.

There is intentionally **no** `swiftlatexpdftex.fmt` here: the worker
builds the format fresh each session from `texlive/pdftex/26/latex.ltx`
via `compileFormat()` (a dumped format is only loadable by the exact
engine build that wrote it).

Related compatibility shims that live in the texlive tree, not the engine:
- `texlive/pdftex/26/pdflatex.ini` — defines `\partokencontext` (missing
  pre-2025 primitive) as a scratch count register so the 2026 macro tree
  (microtype) doesn't error.
- `texlive/pdftex/26/ts1ptm.fd` — TS1/ptm → TS1/cmr substitution.

Verified 2026-08-18 against the M_20_2L_OF_S reference report: full
38-page document compiles in-browser with zero TeX errors; text content
is whitespace-insensitively identical to a local MacTeX `pdflatex` run of
the same `.tex` on every page.

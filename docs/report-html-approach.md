# HTML report — proposal and sample

_Status: prototype for review. Sample PDF: `npm run report:sample` → `report-samples/M_20_2L_OF_S_HTML_Report.pdf`._

## The problem with today's report

The web app currently produces the report by running the desktop app's own
LaTeX pipeline inside the browser: a Python runtime (Pyodide + pandas +
matplotlib) generates the `.tex`, and a pdfTeX compiler built to WebAssembly
typesets it. That gives a byte-for-byte desktop-identical PDF, but at a price:

| | LaTeX-in-browser (current) | HTML report (proposed) |
|---|---|---|
| First-use download | **~60 MB** (Python runtime + TeX Live) | **~0.5 MB** (fonts + math renderer, loaded only on the Report page) |
| Time to report (reference project, warm) | **~8–18 s** | **~1 s** to display, **~1 s** more to print to PDF |
| Memory while generating | two WebAssembly runtimes, hundreds of MB | ordinary web page |
| Works on a 4 GB laptop | borderline; can stall or fail | yes — it is just a web page |
| Readable in the browser before downloading | no (PDF only) | **yes** — it is a page you scroll, then print if you want a file |
| PDF output | generated file, auto-downloaded | browser **Print → Save as PDF** |

Measured on the M_20_2L_OF_S reference project: the HTML report renders in
about 1.2 s and prints to a 27-page A4 PDF in about 1.2 s (headless Chromium).
The LaTeX report of the same project is 38 pages and took 15–25 s.

## How it works

Nothing new is computed. The report reads the **same data the LaTeX pipeline
reads** — the project converted to desktop "chunks" by the existing, golden-
tested mapper (`reportChunks.js`) plus the calculation results — and lays it
out as an ordinary web page styled to look like the LaTeX document (Latin
Modern fonts, numbered sections, booktabs-style tables). The browser's own
print engine paginates it and writes the PDF. Charts are drawn by the same
code as the Results page; equations in Appendix B are the desktop's own LaTeX
formulas rendered by KaTeX.

Every number is checked against the desktop report: `tests/reportDocument.test.js`
pins values straight from the LaTeX golden (`m20-report.golden.tex`) — bridge
and financial fields, construction totals and source markers, material,
transport, machinery and recycling tables, the full results table with stage
totals and grand total, the summary percentages, and the WPI appendix.

Where to find it: **Results → View Report**, or the **Report** entry in the
project sidebar. The **Sections…** button reuses the existing section picker.

## What is the same as the desktop report

- Section structure and order: title page, contents, introduction with the
  3PS-LCC framework figure, all input-data sections (bridge, financial,
  construction, maintenance, traffic, environmental, recycling), LCCA results
  table and figures, summary and conclusions, Appendices A, B and C.
- Every table's columns, row order, grouping, captions and intro sentences.
- All values and their formatting (2 decimals, thousands separators; 4-decimal
  WPI ratios; em-dash for missing values), the construction source markers
  (†, #, §, ‡) and legend, exclusion reasons, "Reconstruction | …" folding in
  the results table.
- Title page content: agency logo, project information card, evaluated-by /
  reviewed-by blocks with signature lines, disclaimer, 3psLCCA footer.
- Appendix A text, Appendix B glossary, equations and tables B-1…B-10.
- Section selection (the same checkboxes as before).
- Behaviour for GLOBAL traffic mode (paragraph instead of the India tables,
  no Appendix C) and for projects without calculation results (input
  sections only).

## What is different (and whether it matters)

| Difference | Why | Impact |
|---|---|---|
| **No page numbers in the table of contents** (and none in running headers) | A web page has no pages until it is printed; CSS cannot ask "which page am I on". The contents list, list of tables and list of figures are present but unnumbered. Page numbers *do* appear in the PDF if enabled in the browser's print dialog (footer). | Cosmetic. Fixable with a small pagination library (Paged.js, ~400 KB) as a follow-up phase — that also gives running headers and "Page x of y". |
| **Layout is similar, not identical** | Browser typesetting vs TeX: line breaks, page breaks and table widths differ; the PDF is 27 pages instead of 38 (browser tables are more compact, figures scale to width). | Cosmetic. Numbers and structure are identical. |
| **Saving the PDF is a print dialog**, not an automatic download | The browser writes the PDF; the user picks "Save as PDF" (the file name is pre-filled). | Workflow change. A one-click download is possible later with a JS PDF writer if wanted. |
| **Charts are vector drawings** (same code as the Results page) instead of matplotlib PNGs | No Python needed. | Sharper in print; visual style matches the on-screen Results page rather than matplotlib. |
| **Appendix C prints on a landscape page** via CSS named pages | Same intent as the LaTeX `landscape` environment. | Chromium/Edge/Firefox honour it; Safari prints the table portrait at reduced size. |
| Very long table rows are never split, and a table header repeats on each printed page | Print CSS rules. | Generally better than LaTeX's `longtable` continuation notes. |
| Remarks/notes fields are printed as plain text | Same as the LaTeX pipeline (`html_to_latex` strips formatting). | None. |

## What was deliberately kept

- The LaTeX pipeline is untouched and still available as **Generate PDF
  Report** on the Results page. The proposal is to make the HTML report the
  default and keep LaTeX as an "advanced / desktop-identical" option for
  capable machines.

## Open decisions for review

1. Adopt the HTML report as the default report path? (LaTeX stays available.)
2. Is the unnumbered contents list acceptable for now, with Paged.js page
   numbering as the next phase?
3. Is "Print → Save as PDF" acceptable, or is a one-click download required?

## Files

- `src/report/reportDocument.js` — document model (content rules ported from `code_to_latex/*`)
- `src/report/reportContent.js` — static text: intro, table intros, Appendix A, Appendix B (LaTeX equations)
- `src/report/ReportPage.jsx`, `ReportRoute.jsx`, `ReportCharts.jsx`, `Equation.jsx`, `report.css`
- `tests/reportDocument.test.js` — golden-value checks against the LaTeX report
- `scripts/print-report-sample.mjs` — prints the reference project to PDF with headless Chromium
- `public/report-assets/` — 3psLCCA header logo, 3PS-LCC framework figure, Latin Modern fonts (latex.css, MIT)

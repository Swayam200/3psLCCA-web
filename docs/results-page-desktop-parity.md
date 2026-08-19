# Results page — desktop parity audit and plan

Goal: make the web **Results/Outputs** page 1:1 with desktop's **Results**
page. Basis: side-by-side screenshots of the same project
(M_20_2L_OF_S, imported on both apps), 2026-08-19, plus code reading of
desktop `gui/components/outputs/lcc_data.py` and web
`src/gui/components/outputs/*`.

## 1. The numbers differ — and that comes first

Same source project, different totals:

| | Desktop | Web |
| --- | --- | --- |
| Total LCC | ₹ 21,130,458.89 (21.13 M) | ₹ 4,90,36,212 (49.04 M) |
| Economic pillar | 8,531,182.42 | 8.75 M |
| Environmental pillar | **0.00** | **27.69 M** |
| Social pillar | 12,595,276.47 | 12.60 M |

The Social pillar matches to the rupee — so the engines agree where the
inputs agree, and the two gaps are data issues, not math issues:

- **Environmental: desktop 0 vs web 27.69 M.** Almost certainly the
  known **desktop bug**: the Ricke SCC widget loses its saved selections
  on reopen (observed in desktop's own terminal log during R0), so the
  imported desktop project computes with no social cost of carbon ⇒ every
  carbon row shows 0.00. The web project has the SCC (₹ 13.197/kg CO₂e,
  verified against the CSCC database in PR #7), so web's 27.69 M is the
  defensible number. **Action: verify on desktop with a fresh (non-
  imported) project, then report the widget bug upstream.** Until fixed,
  imported desktop projects understate totals.
- **Economic: 8.53 M vs 8.75 M — difference ≈ 216 K = exactly desktop's
  "Recycling Costs −216,231.12" row.** Desktop's End-of-Life economic
  total is *negative* (−66,593.88) because the scrap/recycling credit
  exceeds demolition costs. The web's End-of-Life economic shows +0.15 M
  (demolition only) and its itemized list shows no recycling row. Both
  apps use the same result key (`total_scrap_value`, credited in
  desktop's `_CREDIT_KEYS`), and the web's `computeStagePillarTotals`
  does subtract it — so either the web calculation input mapping never
  sends recycling data to core, or the results object lacks the key.
  **Action: trace `total_scrap_value` from web inputs → core → results
  for this project; fix the mapping; add a golden test.**

**Parity gate:** before any UI work, add a test that runs the web
aggregation over the *desktop-computed* results dict we already have in
`tests/fixtures/m20-desktop-chunks.json` (`comparison_cache.results`) and
asserts every card/table/chart number equals what desktop's `lcc_data.py`
derives from the same dict. That separates display parity from
calculation parity permanently.

## 2. Structure and content differences (from the screenshots)

| Area | Desktop | Web today |
| --- | --- | --- |
| Page title | "Results" | "Outputs" |
| Report button | "Generate PDF Report", under the title | "Download Report", top-right |
| Summary | TLCC card + **"About This Analysis"** blurb (analysis period, assessment year) + 3 pillar cards + 3 stage cards | 3 cards (Total/Initial/Future) — different set |
| Pillar chart | "Across 3 Pillars of Sustainability": ratio strip (40.4 % : 0.0 % : 59.6 % and 8.53 M : 0 : 12.60 M), donut with **total in the centre**, outside labels, toggles: "Include stage-wise break-up" (with a note when negative values make it unavailable), "Change to bar chart"; plotly-style toolbar (pan/zoom/save) | "Sustainability Matrix" static donut, no centre total, no ratio strip, no toggles |
| Stage chart | "Across 3 Stages": ratio strip, "Show pillar wise" toggle, value labels above bars, stage legend, "All values in INR" note | "Lifecycle Disaggregation" small bar chart, no toggles/labels/strip |
| Consolidated table | 3 stage rows (reconstruction hidden when absent) + Total; colored header chips and stage chips; **full-precision INR** (e.g. 6,561,474.31) | 4 rows (Reconstruction shown as 0.00) + Grand Total; values in rounded M INR |
| Itemized list | Desktop labels ("Initial Construction Cost", "Time Costs", "Recycling Costs", "Carbon Emissions due to Rerouting during …"); pastel per-stage row backgrounds; exact INR values; **negative values draw bars leftward**; pillar legend on top | Different labels ("Construction Cost", "Loan Interest", "Scrap Value Credit", …), different row inventory, M INR values, positive-only bars |
| Number format | Full INR with Indian grouping; headlines humanized ("21.13 million") | Mixed: headline full digits, tables rounded M INR |

Web-only extras worth **keeping** (additions, not deviations): the
"Calculated with: engine | core version | timestamp" provenance line and
the "Ask the AI assistant" entry point.

## 3. Suggested plan

**Phase 0 — reconcile the numbers (no UI).**
Golden aggregation test as described above; fix the recycling/scrap
mapping; verify the SCC story on desktop and file the upstream bug.
Nothing else proceeds until the same inputs give the same numbers.

**Phase 1 — port desktop's row model verbatim.**
Desktop's `lcc_data.py` is a declarative table (stage, pillar, result
key, label + `_CREDIT_KEYS`). Port it 1:1 into a JS module (replacing
`breakdownStages.js`'s independent inventory), with a unit test pinning
every (stage, pillar, key, label) tuple against the Python source — the
same pattern that keeps the LaTeX report from drifting. This fixes all
label/row differences at once.

**Phase 2 — summary block.**
"Results" title; "Generate PDF Report" button; TLCC card + About blurb
(period, assessment year); pillar cards; stage cards; desktop's exact
color coding; full-precision Indian-grouped INR everywhere desktop uses
it.

**Phase 3 — charts.**
Ratio strips, donut centre total + outside labels, "Include stage-wise
break-up" (with desktop's negative-value note), "Change to bar chart",
"Show pillar wise", value labels, "All values in INR", save-as-image.
(The web charts are d3; the toggles matter more than the toolbar — decide
whether pan/zoom is worth porting or a knowing deviation.)

**Phase 4 — tables and itemized list.**
Colored chips, hide Reconstruction when absent, pastel stage groupings,
leftward negative bars, pillar legend.

Each phase ends with a screenshot-level side-by-side check against
desktop on the reference project, like the report work did.

## 4. Open questions for sir / the team

- Is desktop's Environmental = 0 on this imported project acknowledged as
  the SCC-widget restore bug (i.e. web's 27.69 M is correct)?
- Desktop's headline says "21.13 million"; is the humanized-millions
  format the standard, or full INR (the tables use full INR)?
- Is the plotly toolbar (pan/zoom/save) on charts a requirement, or is
  save-as-image alone acceptable on the web?

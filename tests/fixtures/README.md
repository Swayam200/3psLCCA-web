# Reference fixtures

These fixtures predate the testing cleanup. Their contents and expected results
are deliberately unchanged. Keep them here so both tests and verification scripts
can share stable paths; avoid copying large fixtures into individual suites.

| File | Purpose |
| --- | --- |
| `global-project.json` | Global-mode browser/native engine parity input |
| `india-project.json` | India-mode parity input, including traffic/WPI data |
| `m20.3ps` | Desktop M_20_2L_OF_S reference archive used by report/import tests |
| `m20-web-project.json` | Web representation of the M20 reference project |
| `m20-desktop-chunks.json` | Reference desktop chunks and calculated results |
| `m20-report.golden.tex` | Reviewed desktop report source |
| `m20-report-webdata.golden.tex` | Reviewed report generated from mapped web data |

Engine verification currently uses the application's published core release
1.0.2. The older M20 golden fixture set has no complete machine-generated provenance
manifest; do not invent an engine version or assume it was regenerated at this
cleanup. Existing comments and report architecture docs provide its history.

## Numerical and golden checks

- Real engine parity compares every returned field for global and India inputs.
  Numeric tolerance remains `max(1e-6 absolute, 1e-9 relative)`.
- Report-runtime tests normalize temporary paths. The desktop/web golden
  comparison also normalizes equivalent numeric spellings such as `20`/`20.0`.
- The generated web report is compared against the web-data golden; no expected
  numbers are regenerated from the implementation being tested.
- UI smoke calculation responses use reference results to test rendering and
  persistence, not to claim that a different input project calculates to M20.

## Updating a fixture

Only update for an intentional schema/formula/report change. Record the source
project, exact engine/runtime revision, command used, and reason in the change
description and this file. Compare changed numerical values with an independent
reference or desktop output. Review the text diff and a rendered report before
accepting a new golden. Run `npm test`, `npm run test:report`,
`npm run verify:parity`, and `npm run test:e2e` as applicable.

Use synthetic small projects for new edge cases. Exclude personal information,
credentials, machine-specific paths, and live account identifiers.

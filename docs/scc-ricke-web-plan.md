# Ricke et al. (Country-Level SCC) on the web — architecture plan

Owner: Ricky (SOC page) · Plan: Swayam/Claude · Status: proposed, 2026-08-16

## Where the three implementations stand

| | Desktop | Web today (main) | Web legacy (archive/wasm-cdn-engine) |
| --- | --- | --- | --- |
| Modes | Custom · NITI Aayog · **Ricke** (full param UI) | Custom only (legacy values migrate to custom); normalizer keeps a 6-combo hardcoded Ricke stub | Custom · NITI Aayog · **Ricke** — full 476-line UI existed |
| Data access | `cscc_db_v2.csv` (26 MB, 247,861 rows) → pandas **pickle**, indexed 9-part key lookup | none | **`fetch()` of the whole 26 MB CSV**, parsed in-browser — the reason it was dropped |
| Lookup key | (ISO3, run, dmgfuncpar, climate, SSP, RCP, prtp, eta, dr) → (16.7%, 50%, 83.3%) | — | same key, same semantics |

The dataset (Ricke, Drouet, Caldeira & Tavoni 2018, country-level SCC):
**170 countries** × 5 damage functions (`bhm_sr/lr`, `bhm_richpoor_sr/lr`,
`djo_richpoor`) × 2 `dmgfuncpar` (bootstrap/estimates) × 2 climate
(expected/uncertain) × 5 SSP × 3 RCP × **6 discount combos** (4 growth-adjusted
prtp/η + fixed 3%/5%) → ≈1,458 rows per country, three percentiles each.

## The insight that makes it feasible

Nobody ever needs the whole table — a session needs **one country's slice**.
Measured on the real data:

- one country, dense-array encoding, 4-sig-fig rounding: **29 KB raw,
  10.8 KB gzipped**
- the full source CSV gzips to 6.9 MB

So: ship nothing up front, fetch ~11 KB when the user picks Ricke mode.

## Architecture

1. **Source of truth in-repo, compressed once:** commit
   `data/cscc_db_v2.csv.gz` (6.9 MB — vs the 26 MB raw file that was
   stripped from main). Never served; build input only. (The raw CSV also
   remains recoverable from `archive/wasm-cdn-engine` git history.)
2. **Build-time generator** `scripts/build-cscc-db.mjs` (node, zlib, no
   deps): explodes the gz into `public/data/cscc/{ISO3}.json` (170 files,
   dense fixed-order arrays over the canonical enums, 4-sig-fig values,
   `null` for the ~19% missing combos) plus `public/data/cscc/index.json`
   (country list + enum orders + closest-RCP pairing + dataset version).
   Wire as `prebuild`/`predev` npm hooks, output gitignored — generated
   files never enter git; Pages gzips them on the wire automatically.
3. **Lazy loader** `src/lib/cscc.js`: `loadCsccCountry(iso3)` →
   `fetch(import.meta.env.BASE_URL + 'data/cscc/' + iso3 + '.json')`,
   module-level promise cache; browser HTTP cache handles persistence
   (immutable content → long cache headers not even needed on Pages).
   `lookupScc(countryData, {run, dmgfuncpar, climate, ssp, rcp, disc})` →
   `[lo, med, hi]` — a pure array-index computation from the enum orders,
   unit-testable in node with a fixture country.
4. **UI: resurrect, don't rewrite.** `git show
   archive/wasm-cdn-engine:src/gui/components/carbon_emission/SocialCost.jsx`
   has the full three-mode UI with the exact desktop dropdowns (damage
   function, dmgfuncpar, climate, SSP, RCP incl. "Closest RCP (Default)",
   6 discount combos, percentile pick, USD→INR rate). Swap its
   `loadRickeDb` (whole-CSV fetch+parse) for `loadCsccCountry` + `lookupScc`;
   everything else carries over. Port the closest-RCP pairing logic verbatim
   from desktop `scc_tabs/ricke.py`.
5. **Write path — loop-safe, per the carbon-freeze fix (PR #5):**
   - The UI resolves the SCC **on user action** (mode/param change) and
     writes `social_cost_data = { mode, ricke_params, calculated_scc_local,
     cost_of_carbon_local, usd_rate, … }`. No reactive persist effects.
   - `normalizeCarbonEmissionData` must **trust the stored value for Ricke
     mode when `ricke_params` are present** instead of recomputing from its
     hardcoded 6-combo stub (a sync normalizer cannot do async lookups, and
     the stub overwriting a precise stored value would both corrupt data and
     break stringify-idempotence). The stub remains only as a fallback for
     legacy rows with no params. Extend `tests/carbonNormalization.test.js`
     with a ricke-mode idempotence case — this is the invariant that
     prevented the carbon-page freeze from coming back.
6. **Parity test:** unit test comparing `lookupScc` output for a handful of
   known (IND, WLD) rows against values read straight from the CSV fixture —
   guarantees web numbers === desktop numbers forever.

## Cost of the whole thing

- Repo: +6.9 MB (one gz) + ~150-line generator + ~40-line loader
- Wire per user: **~11 KB, only when Ricke mode is opened** (0 for
  custom/NITI users)
- Build time: one CSV pass, ~1–2 s
- No services, no backend, works on GitHub Pages, offline after first fetch

## Sequencing / ownership

SOC page is Ricky's. Suggested split: Swayam lands steps 1–3 + tests (data
layer, no UI risk); Ricky lands 4–5 (UI + normalizer) with the legacy
component as his starting point. Either order works; the loader's contract
(`loadCsccCountry`/`lookupScc`) is the interface between the two halves.

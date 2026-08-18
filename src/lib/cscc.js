/**
 * Country-level Social Cost of Carbon (Ricke et al. 2018) — shared data
 * contract between the build-time generator (scripts/build-cscc-db.mjs),
 * the browser loader, and tests.
 *
 * Each country ships as one small JSON file of dense arrays: every
 * (run, dmgfuncpar, climate, ssp, rcp, discount) combination occupies a
 * fixed slot computed from the enum orders below, holding [lo, med, hi]
 * (the 16.7% / 50% / 83.3% percentiles, 2018 USD per tCO2) or null when
 * the dataset has no value for that combination. The enum orders are the
 * contract — changing them invalidates every generated file, so bump
 * CSCC_VERSION if they ever change.
 */

export const CSCC_VERSION = 1;

export const CSCC_ENUMS = {
    run: ['bhm_sr', 'bhm_richpoor_sr', 'bhm_lr', 'bhm_richpoor_lr', 'djo_richpoor'],
    dmgfuncpar: ['bootstrap', 'estimates'],
    climate: ['expected', 'uncertain'],
    ssp: ['SSP1', 'SSP2', 'SSP3', 'SSP4', 'SSP5'],
    rcp: ['rcp45', 'rcp60', 'rcp85'],
    // prtp / eta / dr triples, exactly the six combos the dataset carries.
    disc: [
        { prtp: '2', eta: '1p5', dr: 'NA' },
        { prtp: '1', eta: '1p5', dr: 'NA' },
        { prtp: '2', eta: '0p7', dr: 'NA' },
        { prtp: '1', eta: '0p7', dr: 'NA' },
        { prtp: 'NA', eta: 'NA', dr: '3' },
        { prtp: 'NA', eta: 'NA', dr: '5' },
    ],
};

export const CSCC_SLOT_COUNT =
    CSCC_ENUMS.run.length * CSCC_ENUMS.dmgfuncpar.length * CSCC_ENUMS.climate.length *
    CSCC_ENUMS.ssp.length * CSCC_ENUMS.rcp.length * CSCC_ENUMS.disc.length;

/** Paper's default SSP→RCP pairing (desktop ricke.py `_CLOSEST_RCP`). */
export const CLOSEST_RCP = { SSP1: 'rcp60', SSP2: 'rcp60', SSP3: 'rcp85', SSP4: 'rcp60', SSP5: 'rcp85' };

export const discIndex = (prtp, eta, dr) => CSCC_ENUMS.disc.findIndex(
    (combo) => combo.prtp === prtp && combo.eta === eta && combo.dr === dr
);

/**
 * Fixed slot for a (run, dmgfuncpar, climate, ssp, rcp, disc) combination;
 * -1 when any part is not a known enum value.
 */
export const slotIndex = ({ run, dmgfuncpar, climate, ssp, rcp, prtp, eta, dr }) => {
    const runIdx = CSCC_ENUMS.run.indexOf(run);
    const parIdx = CSCC_ENUMS.dmgfuncpar.indexOf(dmgfuncpar);
    const cliIdx = CSCC_ENUMS.climate.indexOf(climate);
    const sspIdx = CSCC_ENUMS.ssp.indexOf(ssp);
    const rcpIdx = CSCC_ENUMS.rcp.indexOf(rcp);
    const dscIdx = discIndex(prtp, eta, dr);
    if ([runIdx, parIdx, cliIdx, sspIdx, rcpIdx, dscIdx].includes(-1)) return -1;
    return ((((runIdx * 2 + parIdx) * 2 + cliIdx) * 5 + sspIdx) * 3 + rcpIdx) * 6 + dscIdx;
};

/**
 * Mirror of desktop ricke.py `_lookup`: returns
 * `{ values: [lo, med, hi], reason: 'ok' }` or `{ values: null, reason: 'na' | 'missing' }`.
 * `countryData` is one generated `{ISO3}.json` object.
 */
export const lookupScc = (countryData, params) => {
    const idx = slotIndex(params);
    if (idx < 0 || !Array.isArray(countryData?.values)) return { values: null, reason: 'missing' };
    const row = countryData.values[idx];
    if (row === null || row === undefined) return { values: null, reason: 'na' };
    return { values: row, reason: 'ok' };
};

const dataUrl = (file) => {
    const base = (typeof import.meta !== 'undefined' && import.meta.env?.BASE_URL) || '/';
    return `${base.endsWith('/') ? base : `${base}/`}data/cscc/${file}`;
};

const countryCache = new Map();
let indexPromise = null;

const fetchJson = async (url, label) => {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Unable to load ${label} (HTTP ${response.status})`);
    return response.json();
};

/**
 * Country list + dataset metadata (small, fetched once). Feeds the ISO3
 * dropdown when the project country is WLD/unknown.
 */
export const loadCsccIndex = () => {
    if (!indexPromise) {
        indexPromise = fetchJson(dataUrl('index.json'), 'Ricke SCC index').catch((error) => {
            indexPromise = null;
            throw error;
        });
    }
    return indexPromise;
};

/**
 * One country's SCC slice (~11 KB gzipped on the wire). Promise-cached per
 * ISO3 for the session; the browser HTTP cache keeps it across sessions.
 */
export const loadCsccCountry = (iso3) => {
    const code = String(iso3 || '').trim().toUpperCase();
    if (!/^[A-Z]{3}$/.test(code)) return Promise.reject(new Error(`Invalid ISO3 country code: ${iso3}`));
    if (!countryCache.has(code)) {
        const promise = fetchJson(dataUrl(`${code}.json`), `Ricke SCC data for ${code}`).catch((error) => {
            countryCache.delete(code);
            throw error;
        });
        countryCache.set(code, promise);
    }
    return countryCache.get(code);
};

/** Fire-and-forget warmup (e.g. for the project's country on page mount). */
export const prefetchCsccCountry = (iso3) => {
    loadCsccCountry(iso3).catch(() => { /* warmup only — real loads surface errors */ });
    loadCsccIndex().catch(() => { });
};

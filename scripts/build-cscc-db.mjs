/**
 * Explodes data/cscc_db_v2.csv.gz (Ricke et al. 2018 country-level SCC,
 * 247,861 rows) into public/data/cscc/{ISO3}.json — one small dense-array
 * file per country — plus index.json (country list + enum orders). Runs as
 * predev/prebuild; output is gitignored and served as static files, so a
 * browser only ever fetches the one ~11 KB country it needs.
 *
 * Slot layout is defined by src/lib/cscc.js — the same module the browser
 * lookup uses, so generator and reader cannot drift.
 */
import { gunzipSync } from 'node:zlib';
import { mkdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import process from 'node:process';
import { CSCC_ENUMS, CSCC_SLOT_COUNT, CSCC_VERSION, CLOSEST_RCP, slotIndex } from '../src/lib/cscc.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const sourcePath = join(root, 'data', 'cscc_db_v2.csv.gz');
const outDir = join(root, 'public', 'data', 'cscc');
const indexPath = join(outDir, 'index.json');

const mtime = (path) => {
    try {
        return statSync(path).mtimeMs;
    } catch {
        return null;
    }
};

const upToDate = () => {
    const built = mtime(indexPath);
    if (built === null) return false;
    if (built <= mtime(sourcePath)) return false;
    if (built <= mtime(fileURLToPath(import.meta.url))) return false;
    try {
        return JSON.parse(readFileSync(indexPath, 'utf8')).v === CSCC_VERSION;
    } catch {
        return false;
    }
};

if (upToDate() && !process.argv.includes('--force')) {
    process.exit(0);
}

const started = performance.now();
const csv = gunzipSync(readFileSync(sourcePath)).toString('utf8');
const lines = csv.trim().split('\n');
const header = lines.shift().split(',');
const col = Object.fromEntries(header.map((name, idx) => [name, idx]));
for (const required of ['run', 'dmgfuncpar', 'climate', 'SSP', 'RCP', 'ISO3', 'prtp', 'eta', 'dr', '16.7%', '50%', '83.3%']) {
    if (!(required in col)) throw new Error(`cscc_db_v2.csv.gz: missing column "${required}"`);
}

// 4 significant figures — SCC inputs are distribution percentiles, so this
// keeps files small without moving any displayed value.
const round4 = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? Number(parsed.toPrecision(4)) : null;
};

const countries = new Map();
let badSlots = 0;

for (const line of lines) {
    if (!line) continue;
    const cells = line.split(',');
    const iso3 = cells[col.ISO3];
    const idx = slotIndex({
        run: cells[col.run],
        dmgfuncpar: cells[col.dmgfuncpar],
        climate: cells[col.climate],
        ssp: cells[col.SSP],
        rcp: cells[col.RCP],
        prtp: cells[col.prtp],
        eta: cells[col.eta],
        dr: cells[col.dr],
    });
    if (idx < 0) {
        badSlots += 1;
        continue;
    }
    let values = countries.get(iso3);
    if (!values) {
        values = new Array(CSCC_SLOT_COUNT).fill(null);
        countries.set(iso3, values);
    }
    const lo = round4(cells[col['16.7%']]);
    const med = round4(cells[col['50%']]);
    const hi = round4(cells[col['83.3%']]);
    // Desktop treats a row with any NA percentile as "no data" — mirror that.
    values[idx] = lo === null || med === null || hi === null ? null : [lo, med, hi];
}

if (badSlots > 0) {
    throw new Error(`cscc_db_v2.csv.gz: ${badSlots} rows had values outside the enum contract in src/lib/cscc.js`);
}

rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });

const iso3List = Array.from(countries.keys()).sort();
for (const iso3 of iso3List) {
    writeFileSync(
        join(outDir, `${iso3}.json`),
        JSON.stringify({ v: CSCC_VERSION, iso3, values: countries.get(iso3) })
    );
}
writeFileSync(indexPath, JSON.stringify({
    v: CSCC_VERSION,
    dataset: 'Ricke, Drouet, Caldeira & Tavoni (2018) — country-level social cost of carbon (cscc_db_v2)',
    unit: 'USD (2018) per tCO2',
    countries: iso3List,
    enums: CSCC_ENUMS,
    closest_rcp: CLOSEST_RCP,
}));

console.log(`cscc: built ${iso3List.length} country files in ${Math.round(performance.now() - started)} ms → public/data/cscc/`);

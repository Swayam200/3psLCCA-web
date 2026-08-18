/**
 * Country-level SCC (Ricke et al. 2018) data layer.
 *
 * The parity suite is the desktop guarantee: for every (IND, WLD) row read
 * straight out of the committed csv.gz, the generated per-country JSON must
 * return the same three percentiles through lookupScc — so web numbers can
 * never drift from the numbers desktop reads out of its pandas pickle.
 *
 * Generated files come from `pretest` (scripts/build-cscc-db.mjs).
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { gunzipSync } from 'node:zlib';
import { join } from 'node:path';
import {
    CSCC_ENUMS,
    CSCC_SLOT_COUNT,
    CLOSEST_RCP,
    discIndex,
    lookupScc,
    slotIndex,
} from '../src/lib/cscc.js';
import { normalizeCarbonEmissionData } from '../src/utils/projectPageSchema.js';

const root = join(import.meta.dirname, '..');
const readCountry = (iso3) => JSON.parse(readFileSync(join(root, 'public', 'data', 'cscc', `${iso3}.json`), 'utf8'));
const round4 = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? Number(parsed.toPrecision(4)) : null;
};

const csvRows = (() => {
    const csv = gunzipSync(readFileSync(join(root, 'data', 'cscc_db_v2.csv.gz'))).toString('utf8');
    const lines = csv.trim().split('\n');
    const header = lines.shift().split(',');
    const col = Object.fromEntries(header.map((name, idx) => [name, idx]));
    return lines.filter(Boolean).map((line) => {
        const cells = line.split(',');
        return {
            iso3: cells[col.ISO3],
            params: {
                run: cells[col.run],
                dmgfuncpar: cells[col.dmgfuncpar],
                climate: cells[col.climate],
                ssp: cells[col.SSP],
                rcp: cells[col.RCP],
                prtp: cells[col.prtp],
                eta: cells[col.eta],
                dr: cells[col.dr],
            },
            lo: round4(cells[col['16.7%']]),
            med: round4(cells[col['50%']]),
            hi: round4(cells[col['83.3%']]),
        };
    });
})();

test('slot layout is a bijection over the full enum space', () => {
    const seen = new Set();
    for (const run of CSCC_ENUMS.run) {
        for (const dmgfuncpar of CSCC_ENUMS.dmgfuncpar) {
            for (const climate of CSCC_ENUMS.climate) {
                for (const ssp of CSCC_ENUMS.ssp) {
                    for (const rcp of CSCC_ENUMS.rcp) {
                        for (const disc of CSCC_ENUMS.disc) {
                            const idx = slotIndex({ run, dmgfuncpar, climate, ssp, rcp, ...disc });
                            assert.ok(idx >= 0 && idx < CSCC_SLOT_COUNT);
                            seen.add(idx);
                        }
                    }
                }
            }
        }
    }
    assert.equal(seen.size, CSCC_SLOT_COUNT);
    assert.equal(slotIndex({ run: 'nope', dmgfuncpar: 'bootstrap', climate: 'expected', ssp: 'SSP1', rcp: 'rcp45', prtp: '2', eta: '1p5', dr: 'NA' }), -1);
    assert.equal(discIndex('9', '9', '9'), -1);
});

test('closest-RCP pairing matches desktop ricke.py', () => {
    assert.deepEqual(CLOSEST_RCP, { SSP1: 'rcp60', SSP2: 'rcp60', SSP3: 'rcp85', SSP4: 'rcp60', SSP5: 'rcp85' });
});

test('index.json lists 170 countries including IND and WLD', () => {
    const index = JSON.parse(readFileSync(join(root, 'public', 'data', 'cscc', 'index.json'), 'utf8'));
    assert.equal(index.countries.length, 170);
    assert.ok(index.countries.includes('IND'));
    assert.ok(index.countries.includes('WLD'));
    assert.deepEqual(index.enums, CSCC_ENUMS);
});

for (const iso3 of ['IND', 'WLD']) {
    test(`full CSV parity for ${iso3}: every row's percentiles survive the round trip`, () => {
        const countryData = readCountry(iso3);
        assert.equal(countryData.values.length, CSCC_SLOT_COUNT);
        const rows = csvRows.filter((row) => row.iso3 === iso3);
        assert.ok(rows.length > 1000, `expected a full row set for ${iso3}, got ${rows.length}`);
        for (const row of rows) {
            const { values, reason } = lookupScc(countryData, row.params);
            if (row.lo === null || row.med === null || row.hi === null) {
                assert.equal(reason, 'na', `expected NA for ${JSON.stringify(row.params)}`);
            } else {
                assert.equal(reason, 'ok', `expected data for ${JSON.stringify(row.params)}`);
                assert.deepEqual(values, [row.lo, row.med, row.hi]);
            }
        }
    });
}

test('lookupScc reports missing for combinations outside the dataset', () => {
    const countryData = readCountry('IND');
    assert.equal(
        lookupScc(countryData, { run: 'bhm_sr', dmgfuncpar: 'bootstrap', climate: 'expected', ssp: 'SSP1', rcp: 'rcp45', prtp: 'bad', eta: 'bad', dr: 'bad' }).reason,
        'missing'
    );
    assert.equal(lookupScc(null, { run: 'bhm_sr', dmgfuncpar: 'bootstrap', climate: 'expected', ssp: 'SSP1', rcp: 'rcp45', prtp: '2', eta: '1p5', dr: 'NA' }).reason, 'missing');
});

test('a known IND lookup returns the exact CSV value (spot check)', () => {
    const sample = csvRows.find((row) => row.iso3 === 'IND' && row.lo !== null);
    const { values, reason } = lookupScc(readCountry('IND'), sample.params);
    assert.equal(reason, 'ok');
    assert.deepEqual(values, [sample.lo, sample.med, sample.hi]);
});

// ── normalizer contract: Ricke mode is loop-safe ────────────────────────────

const RICKE_SOCIAL = {
    source: 'K. Ricke et al. (Country-Level)',
    mode: 'K. Ricke et al. (Country-Level)',
    ricke: {
        iso3: 'IND',
        ssp: 'SSP2 (Middle of the Road)',
        rcp: 'Closest RCP (Default)',
        dmg_func: 'BHM SR (Short Run)',
        dmg_params: 'Bootstrap (Full Uncertainty)',
        climate_uncertainty: 'Expected (Central Projections)',
        discounting: 'Fixed 3%',
        percentile: '50.0% (Central)',
        usd_to_local_rate: 83,
        cpi_ratio: 1,
    },
    result: { selected_mode: 'K. Ricke et al. (Country-Level)', cost_of_carbon_local: 7.1538, currency: 'INR', unit: 'INR/kgCO2e' },
    cost_of_carbon_local: 7.1538,
    calculated_scc_local: 7.1538,
    currency: 'INR',
};

test('normalizer trusts the stored Ricke cost when params are present', () => {
    const normalized = normalizeCarbonEmissionData({ social_cost_data: RICKE_SOCIAL });
    assert.equal(normalized.social_cost_data.calculated_scc_local, 7.1538);
    assert.equal(normalized.social_cost_data.cost_of_carbon_local, 7.1538);
    assert.equal(normalized.social_cost_data.result.cost_of_carbon_local, 7.1538);
});

test('ricke-mode carbon data normalizes idempotently (carbon-freeze invariant)', () => {
    const once = normalizeCarbonEmissionData({ social_cost_data: RICKE_SOCIAL });
    const twice = normalizeCarbonEmissionData(once);
    assert.equal(JSON.stringify(twice), JSON.stringify(once));
});

test('legacy Ricke rows without params still fall back to the stub', () => {
    const normalized = normalizeCarbonEmissionData({
        social_cost_data: {
            mode: 'K. Ricke et al. (Country-Level)',
            ssp: 'SSP2 (Middle of the Road)',
            rcp: 'RCP 4.5 (Intermediate)',
            usd_rate: 83,
        },
    });
    assert.equal(normalized.social_cost_data.calculated_scc_local, 0.110 * 83);
    const twice = normalizeCarbonEmissionData(normalized);
    assert.equal(JSON.stringify(twice), JSON.stringify(normalized));
});

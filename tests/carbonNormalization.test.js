/**
 * Regression guard for the carbon-page freeze (React "Maximum update depth
 * exceeded"): components used to write derived carbon data back into the
 * store, and because normalizeCarbonEmissionData reshapes what it stores,
 * every write produced a different value than the guard compared against —
 * an infinite write loop that killed sidebar navigation.
 *
 * The structural invariant that keeps the loop impossible at the data layer:
 * normalization must be IDEMPOTENT — normalizing already-normalized data
 * must be a byte-identical no-op (JSON.stringify equality, which is what
 * effect guards use, so key order matters too).
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizeProjectSection, normalizeCarbonEmissionData } from '../src/utils/projectPageSchema.js';

const PROJECT = {
    foundation_data: [
        {
            name: 'Pile',
            rows: [
                { id: 'r1', workName: 'Steel Rebar (HYSD) Large', qty: 5, unit: 'MT', rate: 78000, carbonEmission: { factor: 2.6 }, state: {} },
                { id: 'r2', workName: 'PCC (Concrete Pump) Large (M15)', qty: 10, unit: 'cum', rate: 6600, carbonEmission: { factor: 0.11 }, state: {} },
                { id: 'r3', workName: 'Trashed row', qty: 1, unit: 'cum', state: { in_trash: true } },
            ],
        },
    ],
    substructure_data: [
        { name: 'Abutment', rows: [{ id: 'r4', workName: 'PCC (Concrete Pump) Large (M15)', qty: 0, unit: 'cum', carbonEmission: { factor: 0.11 }, state: {} }] },
    ],
    superstructure_data: [],
    miscellaneous_data: [],
    traffic_data: { vehicles: { small_cars: { vehicles_per_day: 1200 }, hcv: { vehicles_per_day: 400 } } },
};

const CARBON_INPUT = {
    material_emissions_data: { excluded_ids: ['foundation_data-r2'] },
    social_cost_data: { source: 'Custom / Manual Override', custom: { entered_value: 6.3936 } },
    machinery_emissions_data: { mode: 'detailed', detailed_entries: [{ rate: 2, hours: 8, days: 10, ef: 2.69 }] },
    diversion_emissions_data: { mode: 'calculate', reroute_km: 4 },
};

test('carbon normalization is idempotent — stringify-stable across repeats', () => {
    const once = normalizeCarbonEmissionData(CARBON_INPUT, PROJECT);
    const twice = normalizeCarbonEmissionData(once, PROJECT);
    const thrice = normalizeCarbonEmissionData(twice, PROJECT);
    assert.equal(JSON.stringify(twice), JSON.stringify(thrice),
        'second and third normalization passes must be byte-identical — otherwise any stringify-guarded write loops forever');
});

test('carbon normalization is idempotent through the section dispatcher too', () => {
    const once = normalizeProjectSection('carbon_emission_data', CARBON_INPUT, PROJECT);
    const twice = normalizeProjectSection('carbon_emission_data', once, PROJECT);
    const thrice = normalizeProjectSection('carbon_emission_data', twice, PROJECT);
    assert.equal(JSON.stringify(twice), JSON.stringify(thrice));
});

test('normalizer derives material rows, totals, and exclusions from construction data', () => {
    const result = normalizeCarbonEmissionData(CARBON_INPUT, PROJECT);
    const material = result.material_emissions_data;

    // Trashed rows never appear; live rows all do.
    const ids = material.rows.map((row) => row.id);
    assert.deepEqual(ids.sort(), ['foundation_data-r1', 'foundation_data-r2', 'substructure_data-r4']);

    // Exclusion flag follows excluded_ids.
    const excluded = material.rows.find((row) => row.id === 'foundation_data-r2');
    assert.equal(excluded.included, false);

    // Total = sum over included rows only: 5*2.6 (rebar) + 0*0.11 (abutment) = 13.
    assert.equal(material.total_kgCO2e, 13);
    assert.equal(material.category_totals.Foundation, 13);
});

test('social cost custom mode survives normalization with its entered value', () => {
    const result = normalizeCarbonEmissionData(CARBON_INPUT, PROJECT);
    const social = result.social_cost_data;
    assert.equal(social.cost_of_carbon_local, 6.3936);
    assert.equal(social.result.cost_of_carbon_local, 6.3936);
});

test('empty carbon data on an empty project normalizes idempotently', () => {
    const empty = {};
    const once = normalizeCarbonEmissionData(empty, {});
    const twice = normalizeCarbonEmissionData(once, {});
    const thrice = normalizeCarbonEmissionData(twice, {});
    assert.equal(JSON.stringify(twice), JSON.stringify(thrice));
});

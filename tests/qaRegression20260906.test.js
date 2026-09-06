/**
 * Regression coverage for the 2026-09-06 end-to-end QA follow-up:
 *   - unit compatibility between the priced quantity and the emission factor
 *   - a recycling save must not drop a web row from the report's carbon table
 *   - per-component row ids ("row-1") must not cross-map deliveries in the report
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveConversionFactor, canonicalUnit } from '../src/utils/carbonUnits.js';
import { computeMaterialEmissions, resolveRowConversion, REASON_UNIT_MISMATCH } from '../src/gui/components/carbon_emission/carbonUtils.js';
import { normalizeCarbonEmissionData } from '../src/utils/projectPageSchema.js';
import { desktopChunksForReport } from '../src/gui/components/outputs/reportChunks.js';
import { buildReportDocument } from '../src/report/reportDocument.js';

const findSection = (doc, id) => {
    const walk = (nodes) => {
        for (const node of nodes || []) {
            if (node.id === id) return node;
            const inner = walk(node.children);
            if (inner) return inner;
        }
        return null;
    };
    return walk(doc.inputSections);
};

test('resolveConversionFactor: same-dimension units convert, stored factors win, cross-dimension needs a factor', () => {
    assert.equal(canonicalUnit('m³ — Cubic Metre'), 'm³');
    assert.equal(canonicalUnit('MT'), 't');
    assert.equal(canonicalUnit('cum'), 'm³');
    assert.equal(canonicalUnit('Rmt'), 'm');

    const steel = resolveConversionFactor({ quantityUnit: 'MT', emissionUnit: 'kg' });
    assert.equal(steel.status, 'derived');
    assert.equal(steel.factor, 1000);

    const deckFromSor = resolveConversionFactor({ quantityUnit: 'cum', emissionUnit: 'kg', explicit: 2400, trusted: true });
    assert.equal(deckFromSor.status, 'explicit');
    assert.equal(deckFromSor.factor, 2400);

    const legacyDeck = resolveConversionFactor({ quantityUnit: 'cum', emissionUnit: 'kg', explicit: 2400 });
    assert.equal(legacyDeck.factor, 2400, 'a stored factor other than the default 1 is a real figure');

    const mismatch = resolveConversionFactor({ quantityUnit: 'cum', emissionUnit: 'kg', explicit: 1 });
    assert.equal(mismatch.status, 'mismatch');
    assert.equal(mismatch.factor, 0);
    assert.match(mismatch.note, /kg per m³/);

    const same = resolveConversionFactor({ quantityUnit: 'm³ — Cubic Metre', emissionUnit: 'm³ — Cubic Metre' });
    assert.equal(same.status, 'same');
    assert.equal(same.factor, 1);

    const count = resolveConversionFactor({ quantityUnit: 'Nos.', emissionUnit: 'kg', explicit: 1, trusted: true });
    assert.equal(count.status, 'explicit');
    assert.equal(count.factor, 1);
});

const sorProject = () => ({
    general_info: { project_name: 'Units', project_currency: 'INR' },
    superstructure_data: [{
        id: 'girders', name: 'Girders',
        rows: [
            // Schedule-of-rates steel: priced per MT, factor per kg, no stored conversion (older build).
            { id: 'row-1', workName: 'Structural Steel main Girder', qty: 45, unit: 'MT', rate: 107164, carbonEmission: { factor: 2.5, perUnit: 'kg', source: 'IFC' } },
        ],
    }, {
        id: 'deck', name: 'Deck Slab',
        rows: [
            // Current build stores the SOR density with its provenance.
            { id: 'row-2', workName: 'RCC Deck Slab', qty: 135, unit: 'cum', rate: 11702, carbonEmission: { factor: 0.11, perUnit: 'kg', source: 'IFC' }, conversionFactor: 2400, conversionFactorSource: 'db' },
        ],
    }],
    substructure_data: [{
        id: 'pier', name: 'Pier',
        rows: [
            // Volume priced, factor per kg, nothing to convert with.
            { id: 'row-3', workName: 'Concreting in Pier', qty: 220, unit: 'cum', rate: 9296.7, carbonEmission: { factor: 0.11, perUnit: 'kg', source: 'IFC' } },
        ],
    }],
    carbon_emission_data: {},
});

test('material emissions: MT → kg is converted, SOR density is applied, incompatible units are excluded with a reason', () => {
    const computed = computeMaterialEmissions(sorProject());
    const byName = Object.fromEntries(computed.rows.map((row) => [row.name, row]));

    assert.equal(byName['Structural Steel main Girder'].conversion_factor, 1000);
    assert.equal(byName['Structural Steel main Girder'].total_kgCO2e, 45 * 1000 * 2.5);
    assert.match(byName['Structural Steel main Girder'].warning, /t → kg/);

    assert.equal(byName['RCC Deck Slab'].total_kgCO2e, 135 * 2400 * 0.11);

    assert.equal(byName['Concreting in Pier'].calculated_included, false);
    assert.equal(byName['Concreting in Pier'].reason, REASON_UNIT_MISMATCH);

    assert.equal(computed.total_kgCO2e, 45 * 1000 * 2.5 + 135 * 2400 * 0.11);
});

test('calculation normaliser applies the same unit rule (no silent ×1)', () => {
    const project = sorProject();
    const material = normalizeCarbonEmissionData(project.carbon_emission_data, project).material_emissions_data;
    const byName = Object.fromEntries(material.rows.map((row) => [row.name, row]));
    assert.equal(byName['Structural Steel main Girder'].conversion_factor, 1000);
    assert.equal(byName['Concreting in Pier'].included, false);
    assert.equal(material.total_kgCO2e, 45 * 1000 * 2.5 + 135 * 2400 * 0.11);
});

test('report carbon table multiplies the same conversion and names the mismatch', () => {
    const doc = buildReportDocument(sorProject(), { results: null, currency: 'INR' });
    const material = findSection(doc, 'material');
    const included = material.included.flatMap((g) => g.rows);
    const steel = included.find((r) => r.material === 'Structural Steel main Girder');
    assert.equal(steel.cf, '1,000.00');
    assert.equal(steel.total, '112,500.00');
    const excluded = material.excluded.flatMap((g) => g.rows.map((r) => `${r.material}:${r.reason}`));
    assert.ok(excluded.includes(`Concreting in Pier:${REASON_UNIT_MISMATCH}`));
});

test('resolveRowConversion trusts imported desktop values and user-confirmed factors', () => {
    const imported = resolveRowConversion({ unit: 'cum', carbonEmission: { factor: 0.11, perUnit: 'kg' }, values: { conversion_factor: 2500, quantity: 10 } });
    assert.equal(imported.status, 'explicit');
    assert.equal(imported.factor, 2500);
    const confirmed = resolveRowConversion({ unit: 'Nos.', carbonEmission: { factor: 25, perUnit: 'kg' }, conversionFactor: 1, state: { carbon_conversion_confirmed: true } });
    assert.equal(confirmed.factor, 1);
});

const recyclingProject = () => ({
    general_info: { project_name: 'Recycling', project_currency: 'INR' },
    superstructure_data: [{
        id: 'girders', name: 'Girders',
        rows: [
            // What the Recycling page now writes: flat fields only.
            { id: 'row-a', workName: 'Steel A', qty: 45, unit: 'MT', rate: 100, carbonEmission: { factor: 2.5, perUnit: 'kg', source: 'IFC' }, scrapRate: 30000, postDemolitionRecoveryPercentage: 90 },
            // What older builds wrote: a partial `values` object on a web row.
            { id: 'row-b', workName: 'Steel B', qty: 45, unit: 'MT', rate: 100, carbonEmission: { factor: 2.5, perUnit: 'kg', source: 'IFC' }, scrapRate: 30000, postDemolitionRecoveryPercentage: 90, values: { scrap_rate: 30000, post_demolition_recovery_percentage: 90 } },
        ],
    }],
    carbon_emission_data: {},
});

test('a recycling save (flat fields or a legacy partial `values`) keeps the material in the report carbon table', () => {
    const chunks = desktopChunksForReport(recyclingProject(), { results: null, currency: 'INR' });
    const [a, b] = chunks.str_super_structure.Girders;
    assert.equal(a.state.included_in_carbon_emission, true);
    assert.equal(b.state.included_in_carbon_emission, true);
    assert.equal(b.values.material_name, 'Steel B', 'flat fields still populate the desktop record');

    const doc = buildReportDocument(recyclingProject(), { results: null, currency: 'INR' });
    const material = findSection(doc, 'material');
    const names = material.included.flatMap((g) => g.rows.map((r) => r.material));
    assert.deepEqual(names, ['Steel A', 'Steel B']);
    assert.equal(material.excluded.length, 0);

    const recycling = findSection(doc, 'recycling');
    assert.equal(recycling.included.flatMap((g) => g.rows).length, 2);
});

const collidingIdsProject = () => ({
    general_info: { project_name: 'Ids', project_currency: 'INR' },
    superstructure_data: [{
        id: 'girders', name: 'Girders',
        rows: [{ id: 'row-1', workName: 'Steel girders', qty: 45, unit: 'MT', rate: 100, carbonEmission: { factor: 2.5, perUnit: 'kg', source: 'IFC' } }],
    }],
    miscellaneous_data: [{
        id: 'railing', name: 'Railing',
        rows: [{ id: 'row-1', workName: 'MS railing', qty: 120, unit: 'RMT', rate: 3870, carbonEmission: { factor: 2.5, perUnit: 'kg', source: 'IFC' }, conversionFactor: 30, conversionFactorSource: 'db' }],
    }],
    carbon_emission_data: {},
    transport_data: {
        vehicles: [{
            id: 'del-1',
            vehicle: { name: 'Trailer', capacity: 25, gross_weight: 40, empty_weight: 15, emission_factor: 0.1, is_custom: true },
            route: { origin: 'Yard', destination: 'Site', distance_km: 350 },
            materials: [{ uuid: 'superstructure_data-row-1', kg_factor: 1000, material_name: 'Steel girders' }],
            summary: {}, meta: {}, state: {},
        }, {
            id: 'del-2',
            vehicle: { name: 'Desktop-style reference', capacity: 25, gross_weight: 40, empty_weight: 15, emission_factor: 0.1, is_custom: true },
            route: { origin: 'Yard', destination: 'Site', distance_km: 10 },
            // A bare id that exists in two components cannot be resolved safely.
            materials: [{ uuid: 'row-1', kg_factor: 1, material_name: 'Steel girders' }],
            summary: {}, meta: {}, state: {},
        }],
    },
});

test('report resolves a delivery by its chunk-qualified id even when two components share "row-1"', () => {
    const doc = buildReportDocument(collidingIdsProject(), { results: null, currency: 'INR' });
    const transport = findSection(doc, 'transport');
    const [steelDelivery, bareDelivery] = transport.deliveries;

    assert.equal(steelDelivery.rows[0].material, 'Steel girders');
    assert.equal(steelDelivery.rows[0].qtyKg, '45,000.00');
    assert.equal(steelDelivery.rows[0].trips, '2.00');
    // (40 + 15) t × 2 trips × 350 km × 0.1
    assert.equal(steelDelivery.rows[0].emissions, '3,850.00');

    // The ambiguous bare id is reported as unknown rather than silently
    // attributed to whichever component was indexed last.
    assert.equal(bareDelivery.rows[0].material, 'Steel girders');
    assert.equal(bareDelivery.rows[0].qtyKg, '—');
});

test('recycling summary written by the web page survives normalisation unchanged (no write loop)', async () => {
    const { normalizeRecyclingData } = await import('../src/utils/projectPageSchema.js');
    const { recyclingChunkData } = await import('../src/utils/recyclingDerivations.js');
    const summary = recyclingChunkData(recyclingProject(), 'INR');
    assert.equal(summary.total_recovered_value, 2 * 45 * 0.9 * 30000);
    const stored = normalizeRecyclingData(summary);
    assert.equal(stored.total_recovered_value, summary.total_recovered_value);
    assert.equal(stored.included_count, 2);
    // Desktop-shaped data with listed rows still sums those rows.
    const desktop = normalizeRecyclingData({ included: [{ recoveredValue: 10 }, { recoveredValue: 5 }], total_recovered_value: 999 });
    assert.equal(desktop.total_recovered_value, 15);
});

test('a row excluded on the Material Emissions page is reported as "Manually Excluded", not "Incomplete Data"', () => {
    const project = sorProject();
    project.superstructure_data[0].rows[0].state = { in_trash: false, included_in_carbon_emission: false };
    const doc = buildReportDocument(project, { results: null, currency: 'INR' });
    const material = findSection(doc, 'material');
    const excluded = material.excluded.flatMap((g) => g.rows.map((r) => `${r.material}:${r.reason}`));
    assert.ok(excluded.includes('Structural Steel main Girder:Manually Excluded'));
});

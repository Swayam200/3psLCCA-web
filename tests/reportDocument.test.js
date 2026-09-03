/**
 * The HTML report document must carry the same content as the desktop
 * LaTeX report. These checks pin values straight from the LaTeX golden
 * (tests/fixtures/m20-report.golden.tex) for the M_20_2L_OF_S reference
 * project, built the same way the runtime test builds it (desktop archive →
 * import3psFile → desktop results).
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { import3psFile } from '../src/utils/projectImport.js';
import { buildReportDocument } from '../src/report/reportDocument.js';
import { SECTION_KEYS } from '../src/gui/components/outputs/reportSections.js';

const root = join(import.meta.dirname, '..');
const fixture = (name) => join(root, 'tests', 'fixtures', name);
const desktopChunks = JSON.parse(readFileSync(fixture('m20-desktop-chunks.json'), 'utf8'));

const loadDocument = async (options = {}) => {
    const archive = readFileSync(fixture('m20.3ps'));
    const project = await import3psFile(archive.buffer.slice(archive.byteOffset, archive.byteOffset + archive.byteLength));
    return buildReportDocument(project, {
        results: desktopChunks.comparison_cache.results,
        currency: desktopChunks.comparison_cache.currency,
        ...options,
    });
};

const section = (doc, id) => {
    const flat = doc.inputSections.flatMap((s) => (s.kind === 'group' ? s.children : [s]));
    const found = flat.find((s) => s.id === id);
    assert.ok(found, `section ${id} present`);
    return found;
};

test('title page and front matter mirror the desktop title page', async () => {
    const doc = await loadDocument();
    assert.equal(doc.titlePage.projectName, 'M_20_2L_OF_S');
    assert.equal(doc.titlePage.projectCode, 'M_20_2L_OF_S');
    assert.equal(doc.titlePage.description, 'Mumbai | 20m | 2 Lane | One side Footpath | Steel Bridge');
    assert.equal(doc.titlePage.evaluatedBy.name, 'Prof. Siddhartha Ghosh and team');
    assert.equal(doc.titlePage.evaluatedBy.organization, 'IIT Bombay');
    assert.match(doc.titlePage.agencyLogo, /^data:image\/png;base64,/);
    assert.equal(doc.meta.currency, 'INR');
    assert.equal(doc.meta.trafficMode, 'INDIA');
});

test('input tables reproduce the golden values', async () => {
    const doc = await loadDocument();

    const bridge = section(doc, 'bridge');
    const row = (rows, label) => rows.find((r) => r.label === label)?.value;
    assert.equal(row(bridge.rows, 'Name of the Bridge'), 'Templatefile_Mumbai_SteelBridge');
    assert.equal(row(bridge.rows, 'Owner'), '—');
    assert.equal(row(bridge.rows, 'Span'), '20 (m)');
    assert.equal(row(bridge.rows, 'Footpath'), 'Footpath at one side');
    assert.equal(row(bridge.rows, 'Working Days per Month'), '26 (days)');

    const financial = section(doc, 'financial');
    assert.equal(row(financial.rows, 'Discount Rate'), '6.7 (%)');
    assert.equal(row(financial.rows, 'Investment Ratio'), '0.5');

    const construction = section(doc, 'construction');
    assert.equal(construction.tables.length, 4);
    const foundation = construction.tables[0];
    assert.equal(foundation.caption, 'Structure Work Data: Foundation');
    assert.deepEqual(foundation.sections.map((s) => s.header), ['Excavation', 'Pile', 'Pile Cap']);
    const excavation = foundation.sections[0].rows[0];
    assert.equal(excavation.quantity, '22.26');
    assert.equal(excavation.unit, 'm³');
    assert.equal(excavation.rate, '557.00');
    assert.equal(excavation.total, '12,401.05');
    assert.equal(excavation.mark, '†');
    const pcc = foundation.sections[1].rows[2];
    assert.equal(pcc.source, 'Maha PWD SOR');
    assert.equal(pcc.total, '7,531.90');
    const girder = construction.tables[2].sections[0].rows[0];
    assert.equal(girder.total, '2,496,119.61');

    const maintenance = section(doc, 'maintenance');
    assert.equal(row(maintenance.rows, 'Major Repair Frequency'), '60 (year)');
    assert.equal(row(maintenance.rows, 'Bearing & Expansion Joint Replacement Duration'), '2 (days)');

    const traffic = section(doc, 'traffic-road');
    assert.equal(row(traffic.rows, 'Rerouting Road Configuration'), 'Two Lane');
    assert.equal(row(traffic.rows, 'Road Hourly Capacity'), '2400 (PCU/hr)');
    assert.equal(row(traffic.rows, 'Crash Rate along Rerouting Route'), '3385.23 (acc / M km)');
    assert.equal(row(traffic.rows, 'Number of Peak Hours'), '2');

    const adt = section(doc, 'traffic-adt');
    assert.deepEqual(adt.rows[0], ['Small Car', '7,271', '12.18', '—']);
    assert.deepEqual(adt.rows[6], ['HCV', '40', '0.59', '7.22']);

    const diversion = section(doc, 'traffic-diversion');
    assert.equal(diversion.caption, 'Traffic Diversion Emissions (Detour: 0.10 km)');
    assert.deepEqual(diversion.rows[1], ['Big Car', '7,269', '0.27', '195.54']);
    assert.equal(diversion.total, '331.22');

    const peak = section(doc, 'traffic-peak');
    assert.deepEqual(peak.rows, [['Peak Hour 1', '10.00'], ['Peak Hour 2', '10.00']]);

    const scc = section(doc, 'scc');
    assert.equal(scc.kind, 'scc-ricke');
    assert.equal(row(scc.rows, 'Country (ISO3)'), 'IND');
    assert.equal(row(scc.rows, 'Percentile'), '50.0% (Central)');
    assert.equal(row(scc.rows, 'USD Conversion Rate'), '0 (INR/USD)');
    assert.equal(scc.applied, '0.00');
});

test('emission, transport, machinery and recycling tables reproduce the golden values', async () => {
    const doc = await loadDocument();

    const material = section(doc, 'material');
    assert.equal(material.included[0].header, 'Foundation — Pile');
    assert.deepEqual(
        material.included[0].rows.map((r) => r.total),
        ['6,333.43', '7,391.80', '381.22'],
    );
    assert.equal(material.included.find((s) => s.header === 'Super-Structure — Girder').rows[0].total, '58,231.30');
    assert.equal(material.included.find((s) => s.header === 'Misc — Asphalt, Utilities and Other Materials').rows[0].efUnit, 'kgCO₂e/m³');
    const excluded = material.excluded.flatMap((s) => s.rows);
    assert.deepEqual(
        excluded.map((r) => r.reason),
        ['Manually Excluded', 'Manually Excluded', 'Manually Excluded', 'Incomplete Data', 'Manually Excluded', 'Incomplete Data', 'Manually Excluded'],
    );

    const transport = section(doc, 'transport');
    assert.equal(transport.deliveries.length, 6);
    assert.deepEqual(
        transport.deliveries.map((d) => d.summary.total),
        ['490.20', '2,479.50', '444.60', '106.40', '74.10', '294.12'],
    );
    assert.equal(transport.deliveries[0].caption, 'Delivery 1 — From Excavation');
    assert.deepEqual(transport.deliveries[0].rows[0], {
        material: 'Excavation for foundation (pile cap depth + thickness of PCC)', category: 'Foundation',
        cf: '1,800.00', qtyKg: '40,075.20', trips: '5.00', emissions: '490.20',
    });
    assert.equal(transport.deliveries[1].rows.length, 9);

    const machinery = section(doc, 'machinery');
    assert.equal(machinery.mode, 'detailed');
    assert.deepEqual(machinery.rows[0], {
        name: 'Backhoe loader (JCB)', source: 'Diesel', rate: '5.00', hrs: '0.22', days: '1.00', ef: '2.69', consumption: '1.10', emissions: '2.96',
    });
    assert.equal(machinery.rows.find((r) => r.name.startsWith('Site office')).emissions, '1,417.73');

    const recycling = section(doc, 'recycling');
    const recIncluded = recycling.included.flatMap((s) => s.rows);
    assert.equal(recIncluded.length, 8);
    const girder = recIncluded.find((r) => r.material.startsWith('Structural Steel main Girder'));
    assert.equal(girder.pct, '95.00');
    assert.equal(girder.recQty, '22.13');
    assert.equal(girder.recovered, '575,325.24');
    const recExcluded = recycling.excluded.flatMap((s) => s.rows);
    assert.equal(recExcluded.find((r) => r.material === 'Reinforcement in pile').reason, 'Manually Excluded');
    assert.equal(recExcluded.find((r) => r.material === 'Median M30').reason, 'Incomplete Data');
});

test('results table, summary and WPI appendix reproduce the golden values', async () => {
    const doc = await loadDocument();

    const { table } = doc.results;
    assert.deepEqual(table.blocks.map((b) => b.title), ['Initial Stage', 'Use Stage', 'End-of-Life Stage']);
    assert.deepEqual(table.blocks.map((b) => b.total), ['17,305,488.93', '5,271,623.16', '508,001.73']);
    assert.equal(table.grandTotal, '23,085,113.82');
    const initialItems = table.blocks[0].items.filter((i) => i.label);
    assert.deepEqual(initialItems.map((i) => [i.label, i.value]), [
        ['Initial Construction Cost', '6,477,802.69'],
        ['Time Costs', '83,671.62'],
        ['Initial Carbon Emissions', '1,323,845.11'],
        ['Carbon emissions due to Rerouting (Construction)', '377,193.91'],
        ['Road User Costs (Construction)', '9,042,975.60'],
    ]);
    const eol = table.blocks[2].items.filter((i) => i.label);
    assert.equal(eol.find((i) => i.label === 'Recycling Costs').value, '-216,231.12');
    assert.equal(doc.results.figures.length, 3);

    assert.deepEqual(doc.summary, { stageLabel: 'Initial stage', stagePct: '74.96', pillarLabel: 'Social', pillarPct: '54.58' });

    const appendixC = doc.appendices.find((a) => a.kind === 'appendix-c');
    assert.ok(appendixC, 'India-mode report carries the WPI appendix');
    assert.equal(appendixC.wpi.columns.length, 17);
    assert.deepEqual(appendixC.wpi.sections[0].rows[0].slice(0, 3), ['Small Car', '1.7210', '1.7103']);
    assert.deepEqual(appendixC.wpi.sections[2].rows[0].slice(0, 3), ['Small Car', '85.40', '94.40']);
});

test('section selections remove sections and renumber tables', async () => {
    const full = await loadDocument();
    const trimmed = await loadDocument({
        selections: {
            [SECTION_KEYS.KEY_SHOW_TITLE_PAGE]: false,
            [SECTION_KEYS.KEY_SHOW_CONSTRUCTION]: false,
            [SECTION_KEYS.KEY_SHOW_TRANSPORT_EMISSION]: false,
        },
    });
    assert.equal(trimmed.titlePage, null);
    assert.equal(trimmed.inputSections.some((s) => s.id === 'construction'), false);
    assert.equal(trimmed.tables.length, full.tables.length - 4 - 7);
    assert.equal(trimmed.tables[0].caption, 'Bridge Data Summary');
    assert.equal(section(trimmed, 'maintenance').tableNo, 3);
});

test('a project without results still renders every input section', async () => {
    const doc = await loadDocument({ results: null });
    assert.equal(doc.meta.hasResults, false);
    assert.deepEqual(doc.results, { empty: true });
    assert.ok(doc.inputSections.length >= 6);
});

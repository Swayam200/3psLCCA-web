import test from 'node:test';
import assert from 'node:assert/strict';
import {
    applyConstructionImport,
    buildConstructionWorkbook,
    getActiveConstructionCount,
    getConstructionTrash,
    parseConstructionWorkbook,
    updatePreviewRow,
} from '../src/utils/constructionExcel.js';
import { deriveConstructionWorkData } from '../src/utils/projectDerivations.js';

const project = {
    name: 'Workbook Test',
    country: 'INDIA',
    currency: 'INR',
    general_info: {
        project_name: 'Workbook Test',
        project_code: 'WB-01',
        project_country: 'INDIA',
        project_currency: 'INR',
    },
    foundation_data: [{
        id: 'pile-cap',
        name: 'Pile Cap',
        rows: [{
            id: 'steel',
            srcId: '12.42',
            workName: 'Steel Rebar',
            qty: 10,
            unit: 't',
            rate: 74401.1,
            source: 'Bihar SOR',
            carbonEmission: { factor: 2.6, perUnit: 'kgCO2e/kg', source: 'IFC' },
            conversionFactor: 1000,
            scrapRate: 5,
            recoveryPct: 80,
            state: { in_trash: false },
        }],
    }],
    substructure_data: [],
    superstructure_data: [],
    miscellaneous_data: [],
};

test('construction workbook round-trips the desktop CAT# schema through preview', async () => {
    const workbook = await buildConstructionWorkbook(project, new Date('2026-06-12T00:00:00Z'));
    const buffer = await workbook.xlsx.writeBuffer();
    const preview = await parseConstructionWorkbook(buffer, {});

    assert.deepEqual(preview.sheets.map((sheet) => sheet.name), [
        'CAT#Foundation',
        'CAT#Sub-Structure',
        'CAT#Super-Structure',
        'CAT#Misc',
    ]);
    assert.equal(preview.metadata.find((item) => item.key === 'Project Name').value, 'Workbook Test');
    assert.equal(preview.sheets[0].rows[0].component, 'Pile Cap');
    assert.equal(preview.sheets[0].rows[0].workName, 'Steel Rebar');
    assert.equal(preview.sheets[0].rows[0].selected, true);

    const imported = applyConstructionImport({
        foundation_data: [],
        substructure_data: [],
        superstructure_data: [],
        miscellaneous_data: [],
    }, preview);
    assert.equal(imported.foundation_data[0].rows[0].rate, 74401.1);
    assert.equal(imported.foundation_data[0].rows[0].carbonEmission.factor, 2.6);
});

test('export writes desktop\'s exact column set including the bare-denominator header', async () => {
    const workbook = await buildConstructionWorkbook(project, new Date('2026-06-12T00:00:00Z'));
    const sheet = workbook.getWorksheet('CAT#Foundation');
    const headers = sheet.getRow(1).values.slice(1);
    // Desktop's excel_exporter.py header list, verbatim — a web export must
    // import into desktop without column warnings.
    assert.deepEqual(headers, [
        'CID#ID', 'CID#Name', 'CID#Quantity', 'CID#Unit', 'CID#Rate',
        'CID#Rate_Src', 'CID#Carbon_Emission_Factor', 'CID#Carbon_Emission_units_Den',
        'CID#Conversion_Factor', 'CID#Carbon_Emission_Src', 'CID#Scrap_Rate',
        'CID#Recovery_Pct', 'CID#Component',
    ]);
    // The stored ratio 'kgCO2e/kg' exports as its bare denominator.
    assert.equal(sheet.getRow(2).values[8], 'kg');
});

const buildWorkbookWithRow = async (headerOverrides, cellOverrides) => {
    const { default: ExcelJS } = await import('exceljs');
    const workbook = new ExcelJS.Workbook();
    const sheet = workbook.addWorksheet('CAT#Foundation');
    const headers = {
        'CID#Name': 'Concrete M40',
        'CID#Unit': 'cum',
        'CID#Rate': '8000',
        'CID#Carbon_Emission_Factor': '410',
        'CID#Component': 'Pile',
        ...headerOverrides,
    };
    sheet.addRow(Object.keys(headers));
    sheet.addRow(Object.keys(headers).map((key) => cellOverrides?.[key] ?? headers[key]));
    return workbook.xlsx.writeBuffer();
};

test('a desktop-exported workbook keeps its carbon unit (the _Den column is no longer dropped)', async () => {
    const buffer = await buildWorkbookWithRow({ 'CID#Carbon_Emission_units_Den': 'cum' });
    const preview = await parseConstructionWorkbook(buffer, {});
    const row = preview.sheets[0].rows[0];
    assert.equal(row.carbonUnitDen, 'cum');
    assert.equal(row.errors.length, 0);
    assert.equal(row.selected, true);
    assert.equal(row.warnings.some((w) => w.startsWith('Unrecognised CID# column')), false);

    const imported = applyConstructionImport({
        foundation_data: [], substructure_data: [], superstructure_data: [], miscellaneous_data: [],
    }, preview);
    assert.deepEqual(imported.foundation_data[0].rows[0].carbonEmission, {
        factor: 410, perUnit: 'm³', source: '',
    });
});

test('a ratio-only carbon_emission_units column resolves to its denominator', async () => {
    const buffer = await buildWorkbookWithRow({ 'CID#Carbon_Emission_units': 'kgCO₂e/kg' });
    const preview = await parseConstructionWorkbook(buffer, {});
    const row = preview.sheets[0].rows[0];
    assert.equal(row.errors.length, 0);
    const imported = applyConstructionImport({
        foundation_data: [], substructure_data: [], superstructure_data: [], miscellaneous_data: [],
    }, preview);
    assert.equal(imported.foundation_data[0].rows[0].carbonEmission.perUnit, 'kg');
});

test('a CO2 ratio in the bare-denominator column is rejected, like desktop', async () => {
    const buffer = await buildWorkbookWithRow({ 'CID#Carbon_Emission_units_Den': 'kgCO2e/kg' });
    const preview = await parseConstructionWorkbook(buffer, {});
    const row = preview.sheets[0].rows[0];
    assert.equal(row.selected, false);
    assert.equal(row.errors.some((e) => e.includes('must be a bare denominator')), true);
});

test('a bare unit in the ratio column is rejected with guidance, like desktop', async () => {
    const buffer = await buildWorkbookWithRow({ 'CID#Carbon_Emission_units': 'kg' });
    const preview = await parseConstructionWorkbook(buffer, {});
    const row = preview.sheets[0].rows[0];
    assert.equal(row.selected, false);
    assert.equal(row.errors.some((e) => e.includes("'carbon_emission_units_den' instead")), true);
});

test('carbon factor without any unit column warns; zero factor with a unit warns', async () => {
    const missing = await parseConstructionWorkbook(await buildWorkbookWithRow({}), {});
    assert.equal(
        missing.sheets[0].rows[0].warnings.some((w) => w.startsWith('carbon_emission provided but neither')),
        true,
    );

    const zero = await parseConstructionWorkbook(
        await buildWorkbookWithRow(
            { 'CID#Carbon_Emission_units_Den': 'kg' },
            { 'CID#Carbon_Emission_Factor': '0' },
        ),
        {},
    );
    assert.equal(
        zero.sheets[0].rows[0].warnings.some((w) => w.startsWith('Carbon emission factor is zero')),
        true,
    );
});

test('editing a previewed row revalidates without duplicating carbon warnings', async () => {
    const buffer = await buildWorkbookWithRow({});
    let preview = await parseConstructionWorkbook(buffer, {});
    const rowId = preview.sheets[0].rows[0].id;
    preview = updatePreviewRow(preview, 'CAT#Foundation', rowId, 'rate', '9000');
    preview = updatePreviewRow(preview, 'CAT#Foundation', rowId, 'rate', '9500');
    const warnings = preview.sheets[0].rows[0].warnings
        .filter((w) => w.startsWith('carbon_emission provided but neither'));
    assert.equal(warnings.length, 1);
    // And fixing the problem clears the warning entirely.
    preview = updatePreviewRow(preview, 'CAT#Foundation', rowId, 'carbonUnitDen', 'kg');
    assert.equal(
        preview.sheets[0].rows[0].warnings.some((w) => w.startsWith('carbon_emission provided')),
        false,
    );
});

test('trashed construction rows are isolated from counts and derived totals', () => {
    const withTrash = structuredClone(project);
    withTrash.foundation_data[0].rows.push({
        id: 'trashed',
        workName: 'Deleted concrete',
        qty: 100,
        rate: 500,
        state: { in_trash: true },
    });

    assert.equal(getConstructionTrash(withTrash).length, 1);
    assert.equal(getActiveConstructionCount(withTrash), 1);
    assert.equal(deriveConstructionWorkData(withTrash).grand_total, 744011);
});

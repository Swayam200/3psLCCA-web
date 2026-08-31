import { resolveCarbonDenom, denomToWebUnit, mentionsCo2 } from './carbonUnits.js';

const SHEETS = [
    { name: 'CAT#Foundation', key: 'foundation_data' },
    { name: 'CAT#Sub-Structure', key: 'substructure_data' },
    { name: 'CAT#Super-Structure', key: 'superstructure_data' },
    { name: 'CAT#Misc', key: 'miscellaneous_data' },
];

export const CONSTRUCTION_EXCEL_COLUMNS = [
    'CID#ID',
    'CID#Name',
    'CID#Quantity',
    'CID#Unit',
    'CID#Rate',
    'CID#Rate_Src',
    'CID#Carbon_Emission_Factor',
    'CID#Carbon_Emission_units_Den',
    'CID#Conversion_Factor',
    'CID#Carbon_Emission_Src',
    'CID#Scrap_Rate',
    'CID#Recovery_Pct',
    'CID#Component',
];

const FIELD_MAP = {
    id: 'srcId',
    name: 'workName',
    quantity: 'qty',
    unit: 'unit',
    rate: 'rate',
    rate_src: 'source',
    carbon_emission_factor: 'carbonFactor',
    // Two deliberately separate columns, like desktop's importer:
    // the bare denominator (e.g. "kg") and the full "kgCO2e/<unit>" ratio.
    carbon_emission_units_den: 'carbonUnitDen',
    carbon_emission_units: 'carbonUnit',
    conversion_factor: 'conversionFactor',
    carbon_emission_src: 'carbonSource',
    scrap_rate: 'scrapRate',
    recovery_pct: 'recoveryPct',
    component: 'component',
};

const NUMERIC_FIELDS = new Set([
    'qty',
    'rate',
    'carbonFactor',
    'conversionFactor',
    'scrapRate',
    'recoveryPct',
]);

const REQUIRED_FIELDS = [
    ['workName', 'Name'],
    ['unit', 'Unit'],
    ['rate', 'Rate'],
];

const uid = () => (
    globalThis.crypto?.randomUUID?.()
    || `construction-${Date.now()}-${Math.random().toString(36).slice(2)}`
);

const cellValue = (cell) => {
    const value = cell?.value;
    if (value == null) return '';
    if (typeof value === 'object') {
        if ('result' in value) return String(value.result ?? '').trim();
        if (Array.isArray(value.richText)) {
            return value.richText.map((part) => part.text || '').join('').trim();
        }
        if ('text' in value) return String(value.text ?? '').trim();
    }
    return String(value).trim();
};

const bareSheetName = (name) => String(name || '').replace(/^CAT#/i, '').trim();

const sheetKey = (name) => {
    const bare = bareSheetName(name).toLowerCase();
    if (bare === 'foundation') return 'foundation_data';
    if (bare === 'sub-structure' || bare === 'substructure') return 'substructure_data';
    if (bare === 'super-structure' || bare === 'superstructure') return 'superstructure_data';
    if (bare === 'misc' || bare === 'miscellaneous') return 'miscellaneous_data';
    return 'miscellaneous_data';
};

const normalizeHeader = (value) => String(value || '').trim().toLowerCase();

const findHeaderRow = (worksheet) => {
    const limit = Math.min(20, worksheet.rowCount);
    for (let rowNumber = 1; rowNumber <= limit; rowNumber += 1) {
        const row = worksheet.getRow(rowNumber);
        if (row.values.some((value) => normalizeHeader(value).startsWith('cid#'))) {
            return rowNumber;
        }
    }
    return null;
};

const validateRow = (row) => {
    const errors = [];
    const warnings = [...(row.warnings || [])];

    REQUIRED_FIELDS.forEach(([field, label]) => {
        if (String(row[field] ?? '').trim() === '') errors.push(`Missing required field: '${label}'`);
    });

    NUMERIC_FIELDS.forEach((field) => {
        const value = row[field];
        if (value !== '' && value != null && !Number.isFinite(Number(value))) {
            errors.push(`'${field}' must be a number (got '${value}')`);
        }
    });

    if (row.rate !== '' && Number(row.rate) < 0) warnings.push('Rate is negative - please verify');
    if (row.rate !== '' && Number(row.rate) === 0) warnings.push('Rate is zero - verify this is intentional');

    // Carbon-column validation, mirroring desktop's excel_importer.py.
    const ef = String(row.carbonFactor ?? '').trim();
    const den = String(row.carbonUnitDen ?? '').trim();
    const units = String(row.carbonUnit ?? '').trim();
    if (ef && !den && !units) {
        warnings.push(
            'carbon_emission provided but neither carbon_emission_units_den '
            + 'nor carbon_emission_units is filled in',
        );
    }
    if (den && mentionsCo2(den)) {
        errors.push(
            `'carbon_emission_units_den' must be a bare denominator `
            + `(e.g. 'kg'), not a full ratio - got '${den}'. Use `
            + `'carbon_emission_units' for the full 'kgCO2e/<unit>' string.`,
        );
    }
    if (units && !mentionsCo2(units)) {
        errors.push(
            `'carbon_emission_units' must be a full ratio starting with `
            + `'kgCO2e/' (e.g. 'kgCO2e/kg') - got '${units}', which doesn't `
            + `contain 'CO2'. If this is meant to be a bare denominator, use `
            + `'carbon_emission_units_den' instead.`,
        );
    }
    if (ef && (den || units) && Number.isFinite(Number(ef)) && Number(ef) === 0) {
        warnings.push('Carbon emission factor is zero - carbon calc will produce 0');
    }

    return { ...row, errors, warnings, selected: errors.length === 0 && !row.duplicate };
};

// Warnings validateRow re-derives on every pass; strip them before
// revalidating an edited row so they don't accumulate as duplicates.
const REDERIVED_WARNING_PREFIXES = ['Rate is ', 'carbon_emission provided', 'Carbon emission factor is zero'];
const isRederivedWarning = (warning) => REDERIVED_WARNING_PREFIXES.some((prefix) => warning.startsWith(prefix));

const existingMaterialNames = (projectData) => {
    const names = new Set();
    SHEETS.forEach(({ key }) => {
        (projectData?.[key] || []).forEach((section) => {
            (section.rows || []).forEach((row) => {
                if (row?.state?.in_trash) return;
                names.add(`${key}|${String(section.name || '').trim().toLowerCase()}|${String(row.workName || '').trim().toLowerCase()}`);
            });
        });
    });
    return names;
};

export async function parseConstructionWorkbook(arrayBuffer, projectData = {}) {
    const { default: ExcelJS } = await import('exceljs');
    const workbook = new ExcelJS.Workbook();
    await workbook.xlsx.load(arrayBuffer);

    const existing = existingMaterialNames(projectData);
    const sheets = [];
    const metadata = [];
    const seenIds = new Map();

    workbook.eachSheet((worksheet) => {
        if (worksheet.name.trim().toLowerCase() === 'metadata') {
            const headerRow = findHeaderRow(worksheet);
            if (headerRow) {
                const headers = {};
                worksheet.getRow(headerRow).eachCell((cell, col) => {
                    headers[normalizeHeader(cellValue(cell))] = col;
                });
                for (let rowNumber = headerRow + 1; rowNumber <= worksheet.rowCount; rowNumber += 1) {
                    const row = worksheet.getRow(rowNumber);
                    const key = cellValue(row.getCell(headers['cid#keys']));
                    if (key) metadata.push({ key, value: cellValue(row.getCell(headers['cid#values'])) });
                }
            }
            return;
        }

        if (!worksheet.name.trim().toLowerCase().startsWith('cat#')) return;
        const headerRow = findHeaderRow(worksheet);
        const key = sheetKey(worksheet.name);
        const fallback = !SHEETS.some((sheet) => sheet.name.toLowerCase() === worksheet.name.trim().toLowerCase());
        const rows = [];

        if (headerRow) {
            const columns = {};
            const warnings = [];
            worksheet.getRow(headerRow).eachCell((cell, col) => {
                const raw = cellValue(cell);
                const normalized = normalizeHeader(raw);
                if (!normalized.startsWith('cid#')) return;
                const field = FIELD_MAP[normalized.slice(4)];
                if (!field) warnings.push(`Unrecognised CID# column ignored: ${raw}`);
                else if (columns[field]) warnings.push(`Duplicate CID# column ignored: ${raw}`);
                else columns[field] = col;
            });

            for (let rowNumber = headerRow + 1; rowNumber <= worksheet.rowCount; rowNumber += 1) {
                const excelRow = worksheet.getRow(rowNumber);
                if (!excelRow.values.some((value) => String(value ?? '').trim())) continue;

                const row = { id: uid(), sheetName: worksheet.name, sectionKey: key, rowNumber, warnings: [...warnings] };
                Object.entries(columns).forEach(([field, col]) => {
                    row[field] = cellValue(excelRow.getCell(col));
                });
                row.component = String(row.component || '').trim() || 'Uncategorised';
                if (fallback && row.component !== 'Uncategorised') {
                    row.component = `${bareSheetName(worksheet.name)} - ${row.component}`;
                }
                if (row.srcId) {
                    if (seenIds.has(row.srcId)) {
                        row.warnings.push(`CID#ID '${row.srcId}' already appeared at ${seenIds.get(row.srcId)}`);
                    } else {
                        seenIds.set(row.srcId, `${worksheet.name}: row ${rowNumber}`);
                    }
                }
                const duplicateKey = `${key}|${row.component.toLowerCase()}|${String(row.workName || '').trim().toLowerCase()}`;
                row.duplicate = Boolean(row.workName && existing.has(duplicateKey));
                if (row.duplicate) row.warnings.push('A material with this name already exists in this component; select it to overwrite');
                rows.push(validateRow(row));
            }
        }

        sheets.push({ name: worksheet.name, sectionKey: key, fallback, rows });
    });

    if (!sheets.length && !metadata.length) {
        throw new Error('No supported CAT# construction sheets were found in this workbook.');
    }
    return { sheets, metadata };
}

export function updatePreviewRow(preview, sheetName, rowId, field, value) {
    return {
        ...preview,
        sheets: preview.sheets.map((sheet) => (
            sheet.name !== sheetName
                ? sheet
                : {
                    ...sheet,
                    rows: sheet.rows.map((row) => (
                        row.id !== rowId ? row : validateRow({ ...row, [field]: value, errors: [], warnings: row.warnings.filter((warning) => !isRederivedWarning(warning)) })
                    )),
                }
        )),
    };
}

const previewRowPerUnit = (row) => {
    const denom = resolveCarbonDenom({
        carbon_emission_units_den: row.carbonUnitDen,
        carbon_emission_units: row.carbonUnit,
    });
    return denomToWebUnit(denom) || denom || '';
};

const previewRowToMaterial = (row) => ({
    id: uid(),
    srcId: row.srcId || '',
    workName: row.workName || '',
    qty: row.qty === '' ? 0 : Number(row.qty),
    unit: row.unit || '',
    rate: row.rate === '' ? 0 : Number(row.rate),
    source: row.source || '',
    conversionFactor: row.conversionFactor === '' ? 1 : Number(row.conversionFactor),
    carbonEmission: row.carbonFactor === '' ? null : {
        factor: Number(row.carbonFactor),
        perUnit: previewRowPerUnit(row),
        source: row.carbonSource || '',
    },
    scrapRate: row.scrapRate === '' ? 0 : Number(row.scrapRate),
    recoveryPct: row.recoveryPct === '' ? 0 : Number(row.recoveryPct),
    state: { in_trash: false },
    importSource: 'excel',
});

export function applyConstructionImport(projectData, preview) {
    const next = {};
    SHEETS.forEach(({ key }) => {
        next[key] = (projectData?.[key] || []).map((section) => ({
            ...section,
            rows: [...(section.rows || [])],
        }));
    });

    preview.sheets.forEach((sheet) => {
        sheet.rows.filter((row) => row.selected && row.errors.length === 0).forEach((row) => {
            const sections = next[row.sectionKey];
            let section = sections.find((item) => item.name.trim().toLowerCase() === row.component.trim().toLowerCase());
            if (!section) {
                section = { id: uid(), name: row.component, rows: [], is_deleted: false };
                sections.push(section);
            }
            section.is_deleted = false;
            const existingIndex = section.rows.findIndex((item) => (
                !item?.state?.in_trash
                && String(item.workName || '').trim().toLowerCase() === String(row.workName || '').trim().toLowerCase()
            ));
            const material = previewRowToMaterial(row);
            if (existingIndex >= 0) {
                material.id = section.rows[existingIndex].id;
                section.rows[existingIndex] = material;
            } else {
                section.rows.push(material);
            }
        });
    });

    return next;
}

const denominator = (unit) => {
    const value = String(unit || '');
    return value.includes('/') ? value.split('/').pop().trim() : value;
};

const blankIfZero = (value) => {
    if (value === '' || value == null) return '';
    return Number(value) === 0 ? '' : value;
};

export async function buildConstructionWorkbook(projectData, date = new Date()) {
    const { default: ExcelJS } = await import('exceljs');
    const workbook = new ExcelJS.Workbook();
    const metadataSheet = workbook.addWorksheet('Metadata');
    metadataSheet.addRow(['CID#Keys', 'CID#Values']);
    const general = projectData?.general_info || {};
    const metadata = [
        ['Project Name', general.project_name || projectData?.name || ''],
        ['Project Code', general.project_code || ''],
        ['Country', general.project_country || projectData?.country || ''],
        ['Currency', general.project_currency || projectData?.currency || ''],
        ['Date', date.toISOString().slice(0, 10)],
    ];

    const sheetRows = SHEETS.map(({ name, key }) => {
        const rows = (projectData?.[key] || []).flatMap((section) => (
            (section.rows || [])
                .filter((row) => !row?.state?.in_trash)
                .map((row) => [
                    row.srcId || '',
                    row.workName || '',
                    row.qty ?? '',
                    row.unit || '',
                    row.rate ?? '',
                    row.source || '',
                    blankIfZero(row.carbonEmission?.factor),
                    denominator(row.carbonEmission?.perUnit),
                    blankIfZero(row.conversionFactor),
                    row.carbonEmission?.source || '',
                    blankIfZero(row.scrapRate),
                    blankIfZero(row.recoveryPct),
                    section.name || '',
                ])
        ));
        metadata.push([`${name} Total`, rows.length]);
        return { name, rows };
    });
    metadata.forEach((row) => metadataSheet.addRow(row));
    metadataSheet.columns = [{ width: 28 }, { width: 24 }];

    sheetRows.forEach(({ name, rows }) => {
        const worksheet = workbook.addWorksheet(name);
        worksheet.addRow(CONSTRUCTION_EXCEL_COLUMNS);
        rows.forEach((row) => worksheet.addRow(row));
        worksheet.getRow(1).font = { bold: true };
        worksheet.columns = CONSTRUCTION_EXCEL_COLUMNS.map((heading) => ({
            width: Math.max(14, Math.min(42, heading.length + 3)),
        }));
        worksheet.views = [{ state: 'frozen', ySplit: 1 }];
        worksheet.autoFilter = { from: 'A1', to: 'M1' };
    });

    return workbook;
}

export async function downloadConstructionWorkbook(projectData) {
    const workbook = await buildConstructionWorkbook(projectData);
    const buffer = await workbook.xlsx.writeBuffer();
    const projectName = projectData?.general_info?.project_name || projectData?.name || 'construction_works';
    const safeName = projectName.replace(/[\\/:*?"<>|]+/g, '_');
    const fileName = `${safeName}_${new Date().toISOString().slice(0, 10)}.xlsx`;
    const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = fileName;
    anchor.click();
    URL.revokeObjectURL(url);
    return fileName;
}

export const getConstructionTrash = (projectData) => (
    SHEETS.flatMap(({ name, key }) => (
        (projectData?.[key] || []).flatMap((section) => (
            (section.rows || [])
                .filter((row) => row?.state?.in_trash)
                .map((row) => ({ ...row, category: name.replace('CAT#', ''), sectionKey: key, sectionId: section.id, component: section.name }))
        ))
    ))
);

export const getActiveConstructionCount = (projectData) => (
    SHEETS.reduce((total, { key }) => (
        total + (projectData?.[key] || []).reduce((sectionTotal, section) => (
            sectionTotal + (section.rows || []).filter((row) => !row?.state?.in_trash).length
        ), 0)
    ), 0)
);

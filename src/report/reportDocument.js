/**
 * Report document model.
 *
 * Turns a web project + calculation results into an ordered, fully
 * resolved document (sections → tables/figures/paragraphs) that the HTML
 * report renders and the print stylesheet paginates.
 *
 * Content rules mirror the desktop LaTeX report module by module
 * (vendor/report-runtime/three_ps_lcca_gui/code_to_latex/*). The input is
 * the same desktop-shaped chunk dict the LaTeX pipeline consumes
 * (reportChunks.desktopChunksForReport), so both reports read identical
 * data; this module only decides what to show and how to format it.
 */
import { desktopChunksForReport } from '../gui/components/outputs/reportChunks.js';
import { MASTER_ROWS, CREDIT_KEYS } from '../gui/components/outputs/lccData.js';
import { SECTION_KEYS } from '../gui/components/outputs/reportSections.js';
import { resolveTrafficMode } from '../gui/components/carbon_emission/carbonUtils.js';
import {
    EMDASH, fmt, fmtPlain, fmtInt, fieldValue, unitDisplay, emissionUnitDisplay, stripHtml,
    RATIO_DECIMALS,
} from './reportFormat.js';
import { TABLE_INTROS } from './reportContent.js';

/* ── Desktop constants ───────────────────────────────────────────────────── */

/** definitions.STRUCTURE_CHUNKS: chunk id → category label used in emission/recycling headers. */
const STRUCTURE_CHUNKS = [
    ['str_foundation', 'Foundation'],
    ['str_sub_structure', 'Sub-Structure'],
    ['str_super_structure', 'Super-Structure'],
    ['str_misc', 'Misc'],
];

/** Construction table captions (structure_work_data_latex). */
const STRUCTURE_CAPTIONS = {
    str_foundation: 'Structure Work Data: Foundation',
    str_sub_structure: 'Structure Work Data: Sub-Structure',
    str_super_structure: 'Structure Work Data: Super Structure',
    str_misc: 'Structure Work Data: Miscellaneous',
};

const SOURCE_MARK = { db: '', manual: '#', db_modified: '§', excel: '†', excel_modified: '‡' };

/** traffic_data.main.LANE_TYPES */
const LANE_NAMES = {
    SL: 'Single Lane', IL: 'Intermediate Lane', '2L': 'Two Lane', '4L': 'Four Lane',
    '6L': 'Six Lane', '8L': 'Eight Lane', EW8: 'Expressway',
};

/** traffic_data.main._VEHICLES / _HAS_PWR */
const VEHICLES = [
    ['small_cars', 'Small Car'], ['big_cars', 'Big Car'], ['two_wheelers', 'Two Wheeler'],
    ['o_buses', 'Ordinary Buses'], ['d_buses', 'Deluxe Buses'], ['lcv', 'LCV'], ['hcv', 'HCV'], ['mcv', 'MCV'],
];
const HAS_PWR = new Set(['hcv', 'mcv']);

/** wpi_table._VEHICLES / _COLUMNS (labels as printed in Appendix C). */
const WPI_VEHICLES = [
    ['small_cars', 'Small Car'], ['big_cars', 'Big Car'], ['two_wheelers', 'Two Wheeler'],
    ['o_buses', 'Ordinary Bus'], ['d_buses', 'Deluxe Bus'], ['lcv', 'LCV'], ['hcv', 'HCV'], ['mcv', 'MCV'],
];
const WPI_COLUMNS = [
    ['petrol', 'Petrol Cost'], ['diesel', 'Diesel Cost'], ['engine_oil', 'Engine Oil Cost'],
    ['other_oil', 'Other Oil Cost'], ['grease', 'Grease Cost'], ['property_damage', 'Property Damage Cost'],
    ['tyre_cost', 'Tyre Cost'], ['spare_parts', 'Spare Parts Cost'], ['fixed_depreciation', 'Fixed Depreciation'],
    ['commodity_holding_cost', 'Commodity Holding Cost'], ['passenger_cost', 'Passenger Cost'],
    ['crew_cost', 'Crew Cost'], ['fatal', 'Fatal Injury Cost'], ['major', 'Major Injury Cost'],
    ['minor', 'Minor Injury Cost'], ['vot_cost', 'Value of Time Cost'],
];

const RICKE_SOURCES = new Set(['K. Ricke et al. (Country-Level)', 'ricke']);
const SCC_EXPLORER_URL = 'https://country-level-scc.github.io/explorer/';

/** Field tables (desktop FIELDS lists): [group | [key, label, unit]] */
const BRIDGE_FIELDS = [
    { group: 'Bridge Identification' },
    ['bridge_name', 'Name of the Bridge'], ['user_agency', 'Owner'],
    { group: 'Location' },
    ['project_country', 'Country'], ['location', 'Bridge Alignment & Location'],
    { group: 'Technical Specifications' },
    ['bridge_type', 'Type of Bridge'], ['span', 'Span', '(m)'], ['carriageway_width', 'Carriageway Width', '(m)'],
    ['num_lanes', 'Number of Lanes'], ['vehicle_path_direction', 'Vehicle Path Direction'], ['footpath', 'Footpath'],
    { group: 'Life Cycle' },
    ['design_life', 'Design Life', '(years)'], ['analysis_period', 'Analysis Period', '(years)'], ['year_of_construction', 'Year of Construction'],
    { group: 'Construction Schedule' },
    ['duration_construction_months', 'Duration of Construction', '(months)'],
    ['working_days_per_month', 'Working Days per Month', '(days)'], ['days_per_month', 'Days per Month', '(days)'],
];

const FINANCIAL_FIELDS = [
    { group: 'Financial Data' },
    ['discount_rate', 'Discount Rate', '(%)'], ['discount_rate_source', 'Source: Discount Rate'],
    ['inflation_rate', 'Inflation Rate', '(%)'], ['inflation_rate_source', 'Source: Inflation Rate'],
    ['interest_rate', 'Interest Rate', '(%)'], ['interest_rate_source', 'Source: Interest Rate'],
    ['investment_ratio', 'Investment Ratio'], ['investment_ratio_source', 'Source: Investment Ratio'],
];

const PCT_IC = '(% of initial construction cost)';
const MAINTENANCE_FIELDS = [
    { group: 'Routine Maintenance' },
    ['routine_inspection_cost', 'Routine Inspection Cost', PCT_IC], ['routine_inspection_freq', 'Routine Inspection Frequency', '(year)'],
    { group: 'Periodic Maintenance' },
    ['periodic_maintenance_cost', 'Periodic Maintenance Cost', PCT_IC],
    ['periodic_maintenance_carbon_cost', 'Periodic Maintenance Carbon Cost', PCT_IC],
    ['periodic_maintenance_freq', 'Periodic Maintenance Frequency', '(year)'],
    { group: 'Major Inspection' },
    ['major_inspection_cost', 'Major Inspection Cost', PCT_IC], ['major_inspection_freq', 'Major Inspection Frequency', '(year)'],
    { group: 'Major Repair' },
    ['major_repair_cost', 'Major Repair Cost', PCT_IC], ['major_repair_carbon_cost', 'Major Repair Carbon Cost', PCT_IC],
    ['major_repair_freq', 'Major Repair Frequency', '(year)'], ['major_repair_duration', 'Major Repair Duration', '(months)'],
    { group: 'Bearings & Expansion Joints' },
    ['bearing_exp_joint_cost', 'Bearing & Expansion Joint Replacement Cost', PCT_IC],
    ['bearing_exp_joint_freq', 'Bearing & Expansion Joint Replacement Frequency', '(year)'],
    ['bearing_exp_joint_duration', 'Bearing & Expansion Joint Replacement Duration', '(days)'],
];

const TRAFFIC_FIELDS = [
    { group: 'Rerouting Road Configuration' },
    ['alternate_road_carriageway', 'Rerouting Road Configuration'], ['carriage_width_in_m', 'Carriageway Width', '(m)'],
    ['hourly_capacity', 'Road Hourly Capacity', '(PCU/hr)'],
    { group: 'Accident Severity Distribution' },
    ['severity_minor', 'Minor Injury', '(%)'], ['severity_major', 'Major Injury', '(%)'], ['severity_fatal', 'Fatal Accident', '(%)'],
    { group: 'Road Parameters' },
    ['road_roughness_mm_per_km', 'Road Roughness', '(mm/km)'], ['road_rise_m_per_km', 'Road Rise', '(m/km)'],
    ['road_fall_m_per_km', 'Road Fall', '(m/km)'], ['additional_reroute_distance_km', 'Rerouting Distance', '(km)'],
    ['additional_travel_time_min', 'Rerouting Time', '(min)'],
    ['crash_rate_accidents_per_million_km', 'Crash Rate along Rerouting Route', '(acc / M km)'],
    ['work_zone_multiplier', 'Work Zone Multiplier'],
    { group: 'Traffic Flow' },
    ['num_peak_hours', 'Number of Peak Hours'],
];

const RICKE_FIELDS = (currency) => [
    { group: 'Socioeconomic & Climate Scenarios' },
    ['iso3', 'Country (ISO3)'], ['ssp', 'Socioeconomic Pathway (SSP)'], ['rcp', 'Climate Trajectory (RCP)'],
    { group: 'Damage Function & Model Parameters' },
    ['dmg_func', 'Damage Function'], ['dmg_params', 'Damage Parameters'], ['climate_uncertainty', 'Climate Uncertainty'],
    { group: 'Discounting & Valuation' },
    ['discounting', 'Discounting Approach'], ['percentile', 'Percentile'],
    { group: 'Currency Adjustment' },
    ['usd_to_local_rate', 'USD Conversion Rate', `(${currency}/USD)`],
    { group: 'Inflation Adjustment (CPI)' },
    ['cpi_ratio', 'CPI Ratio (Reference-Year CPI / 2018 CPI)'],
];

/* ── Small helpers ───────────────────────────────────────────────────────── */

const obj = (v) => (v && typeof v === 'object' && !Array.isArray(v) ? v : {});
const arr = (v) => (Array.isArray(v) ? v : []);
const num = (v, fallback = 0) => {
    if (v === null || v === undefined || v === '') return fallback;
    const n = Number(v);
    return Number.isFinite(n) ? n : fallback;
};
/** desktop `float(values.get(k, default) or default)` — falsy → default */
const numOr = (v, fallback) => {
    const n = Number(v);
    return v === null || v === undefined || v === '' || !Number.isFinite(n) || n === 0 ? fallback : n;
};

/** Remarks paragraph (html_to_latex.format_remarks_latex) or null. */
const notes = (data, key = 'remarks', label = 'Notes') => {
    const text = stripHtml(obj(data)[key]);
    return text ? { label, text } : null;
};

/** desktop fields_to_latex → key/value table rows with group headers. */
const fieldRows = (fields, data) => fields.map((entry) => (
    entry.group
        ? { group: entry.group }
        : { label: entry[1], value: fieldValue(obj(data)[entry[0]], entry[2] || '') }
));

/* ── Section builders (one per desktop LaTeX module) ─────────────────────── */

const buildTitlePage = (general, currency) => {
    const logo = general.agency_logo;
    const logoSrc = !logo ? null
        : String(logo).startsWith('data:') ? logo
            : `data:image/png;base64,${logo}`;
    return {
        projectName: general.project_name || EMDASH,
        projectCode: general.project_code || EMDASH,
        description: general.project_description || EMDASH,
        currency,
        agencyLogo: logoSrc,
        evaluatedBy: {
            name: general.contact_person || '',
            organization: general.agency_name || '',
            address: general.agency_address || '',
            email: general.agency_email || '',
            phone: general.agency_phone || '',
        },
        reviewedBy: {
            name: general.reviewer_name || '',
            organization: general.reviewer_organization || '',
            address: general.reviewer_address || '',
            email: general.reviewer_email || '',
            phone: general.reviewer_phone || '',
        },
    };
};

/** structure_work_data_latex._structure_table (one per structure chunk). */
const buildConstructionTables = (chunks, currency) => STRUCTURE_CHUNKS.map(([chunkId]) => {
    const sections = Object.entries(obj(chunks[chunkId])).map(([component, items]) => ({
        header: component,
        rows: arr(items)
            .filter((item) => obj(item.state).in_trash !== true)
            .map((item) => {
                const v = obj(item.values);
                const qty = num(v.quantity);
                const rate = num(v.rate);
                return {
                    material: v.material_name || '',
                    mark: SOURCE_MARK[obj(item.meta).source] || '',
                    quantity: fmt(qty),
                    unit: unitDisplay(v.unit),
                    rate: fmt(rate),
                    source: v.rate_source ? String(v.rate_source) : null,
                    total: fmt(qty * rate),
                };
            }),
    })).filter((section) => section.rows.length > 0);
    return { chunkId, caption: STRUCTURE_CAPTIONS[chunkId], currency, sections };
}).filter((table) => table.sections.length > 0);

/** structure_work_data_latex.collect_for_emissions */
const collectForEmissions = (chunks) => {
    const included = [];
    const excluded = [];
    for (const [chunkId, category] of STRUCTURE_CHUNKS) {
        for (const [component, items] of Object.entries(obj(chunks[chunkId]))) {
            const inc = [];
            const exc = [];
            for (const item of arr(items)) {
                const state = obj(item.state);
                if (state.in_trash === true) continue;
                const v = obj(item.values);
                const qty = num(v.quantity);
                const cf = numOr(v.conversion_factor, 1);
                const ef = num(v.carbon_emission);
                if (state.included_in_carbon_emission === true) {
                    inc.push({
                        material: v.material_name || '',
                        quantity: fmt(qty),
                        unit: unitDisplay(v.unit),
                        cf: fmt(cf),
                        ef: fmt(ef),
                        efUnit: emissionUnitDisplay(v.carbon_unit),
                        total: fmt(qty * cf * ef),
                        totalValue: qty * cf * ef,
                    });
                } else {
                    exc.push({
                        material: v.material_name || '',
                        reason: obj(v.exclusion_reason).carbon || 'Incomplete Data',
                    });
                }
            }
            const header = `${category} — ${component}`;
            if (inc.length) included.push({ header, rows: inc });
            if (exc.length) excluded.push({ header, rows: exc });
        }
    }
    return { included, excluded };
};

/** structure_work_data_latex.collect_for_recycling */
const collectForRecycling = (chunks) => {
    const included = [];
    const excluded = [];
    for (const [chunkId, category] of STRUCTURE_CHUNKS) {
        for (const [component, items] of Object.entries(obj(chunks[chunkId]))) {
            const inc = [];
            const exc = [];
            for (const item of arr(items)) {
                const state = obj(item.state);
                if (state.in_trash === true) continue;
                const v = obj(item.values);
                const qty = num(v.quantity);
                const pct = numOr(v.post_demolition_recovery_percentage, 0) || numOr(v.recyclability_percentage, 0);
                const scrap = num(v.scrap_rate);
                const valid = pct > 0 && scrap > 0 && qty > 0;
                const includedFlag = state.included_in_recyclability === undefined ? true : state.included_in_recyclability;
                if (valid && includedFlag) {
                    const recQty = qty * (pct / 100);
                    inc.push({
                        material: v.material_name || '',
                        pct: fmt(pct),
                        recQty: fmt(recQty),
                        unit: unitDisplay(v.unit),
                        scrap: fmt(scrap),
                        recovered: fmt(recQty * scrap),
                        recoveredValue: recQty * scrap,
                    });
                } else {
                    exc.push({ material: v.material_name || '', reason: valid ? 'Manually Excluded' : 'Incomplete Data' });
                }
            }
            const header = `${category} — ${component}`;
            if (inc.length) included.push({ header, rows: inc });
            if (exc.length) excluded.push({ header, rows: exc });
        }
    }
    return { included, excluded };
};

const WEB_MATERIAL_PREFIX = /^(foundation_data|substructure_data|superstructure_data|miscellaneous_data)-/;

/** transport_emissions_latex */
const buildTransport = (chunks) => {
    const index = {};
    for (const [chunkId, category] of STRUCTURE_CHUNKS) {
        for (const [component, items] of Object.entries(obj(chunks[chunkId]))) {
            for (const item of arr(items)) {
                if (item?.id) index[item.id] = { item, category, component };
            }
        }
    }

    const deliveries = [];
    let n = 0;
    for (const entry of arr(obj(chunks.transport_data).vehicles)) {
        if (obj(entry.state).in_trash === true) continue;
        n += 1;
        const vehicle = obj(entry.vehicle);
        const route = obj(entry.route);
        const capacity = num(vehicle.capacity);
        const gross = num(vehicle.gross_weight);
        const empty = vehicle.empty_weight === undefined || vehicle.empty_weight === null
            ? Math.max(0, gross - capacity) : num(vehicle.empty_weight);
        const distance = num(route.distance_km);
        const ef = num(vehicle.emission_factor);

        const rows = [];
        let total = 0;
        for (const matEntry of arr(entry.materials)) {
            const [uuid, kgFactor] = matEntry && typeof matEntry === 'object'
                ? [matEntry.uuid, numOr(matEntry.kg_factor, 1)] : [matEntry, 1];
            // Desktop references rows by id; the web transport page prefixes
            // the id with its structure chunk (e.g. "foundation_data-<id>").
            const record = index[uuid] || index[String(uuid ?? '').replace(WEB_MATERIAL_PREFIX, '')];
            if (!record) {
                const savedName = (matEntry && typeof matEntry === 'object' && matEntry.material_name) || '';
                rows.push({ material: savedName || 'Unknown', category: '', cf: EMDASH, qtyKg: EMDASH, trips: EMDASH, emissions: fmt(0) });
                continue;
            }
            const v = obj(record.item.values);
            if (obj(record.item.state).in_trash === true) {
                rows.push({ material: v.material_name || '', category: record.category, cf: EMDASH, qtyKg: EMDASH, trips: EMDASH, emissions: fmt(0) });
                continue;
            }
            const qtyKg = num(v.quantity) * kgFactor;
            const trips = capacity > 0 ? Math.ceil((qtyKg / 1000) / capacity) : 0;
            const emission = (gross + empty) * trips * distance * ef;
            total += emission;
            rows.push({
                material: v.material_name || '', category: record.category,
                cf: fmt(kgFactor), qtyKg: fmt(qtyKg), trips: fmt(trips), emissions: fmt(emission),
            });
        }

        const name = (vehicle.name || '').trim();
        const origin = (route.origin || '').trim();
        deliveries.push({
            index: n,
            caption: `Delivery ${n}${name ? `: ${name}` : ''} — From ${origin || `${fmtPlain(distance)} km`}`,
            summary: {
                delivery: `Delivery ${n}`, vehicle: name || EMDASH, origin,
                distance: fmt(distance), capacity: fmt(capacity), gross: fmt(gross), ef: fmt(ef), total: fmt(total),
            },
            rows,
            totalValue: total,
        });
    }
    return deliveries;
};

/** machinery_emissions_latex */
const buildMachinery = (data) => {
    const d = obj(data);
    if ((d.mode || 'detailed') === 'lumpsum') {
        const ls = obj(d.lumpsum);
        const rows = [
            ['Electricity', 'elec_consumption_per_day', 'elec_days', 'elec_ef'],
            ['Fuel', 'fuel_consumption_per_day', 'fuel_days', 'fuel_ef'],
        ].map(([label, consKey, daysKey, efKey]) => {
            const cons = num(ls[consKey]);
            const days = num(ls[daysKey]);
            const ef = num(ls[efKey]);
            return { source: label, consumption: fmt(cons), days: fmt(days), ef: fmt(ef), emissions: fmt(cons * days * ef), value: cons * days * ef };
        });
        const total = rows.reduce((s, r) => s + r.value, 0);
        return { mode: 'lumpsum', total: fmtPlain(total), rows };
    }
    const rows = arr(obj(d.detailed).rows).map((row) => {
        const rate = num(row.rate);
        const hrs = num(row.hrs);
        const days = num(row.days);
        const ef = num(row.ef);
        const consumption = rate * hrs * days;
        return {
            name: row.name || '', source: row.source || '',
            rate: fmt(rate), hrs: fmt(hrs), days: fmt(days), ef: fmt(ef),
            consumption: fmt(consumption), emissions: fmt(consumption * ef),
        };
    });
    return { mode: 'detailed', rows };
};

/** results_latex._stage_has_data */
const stageHasData = (results, stageKey) => {
    const stage = obj(results[stageKey]);
    const rows = MASTER_ROWS.filter(([sk]) => sk === stageKey);
    if (stageKey === 'reconstruction') {
        if (!stage.economic || typeof stage.economic !== 'object') return false;
        return rows.some(([, cat, key]) => num(obj(stage[cat])[key]) !== 0);
    }
    // stage_totals() is empty only when the stage dict itself is missing/empty
    return Object.keys(stage).length > 0;
};

/** results_latex.results_to_latex → grouped rows + totals. */
const buildResultsTable = (results) => {
    const hasRecon = stageHasData(results, 'reconstruction');
    const blocks = [];
    let grandTotal = 0;
    for (const [sk, title] of [['initial_stage', 'Initial Stage'], ['use_stage', 'Use Stage'], ['end_of_life', 'End-of-Life Stage']]) {
        if (!stageHasData(results, sk)) continue;
        const sources = sk === 'end_of_life' && hasRecon ? ['reconstruction', sk] : [sk];
        const rows = MASTER_ROWS.filter(([s]) => sources.includes(s));
        let currentCat = null;
        let stageTotal = 0;
        const items = [];
        for (const [source, cat, key, label] of rows) {
            if (cat !== currentCat) {
                items.push({ subgroup: cat.charAt(0).toUpperCase() + cat.slice(1) });
                currentCat = cat;
            }
            const raw = num(obj(obj(results[source])[cat])[key]);
            const value = CREDIT_KEYS.has(key) ? -raw : raw;
            stageTotal += value;
            grandTotal += value;
            items.push({ label: source === 'reconstruction' ? `Reconstruction | ${label}` : label, value: fmt(value) });
        }
        blocks.push({ title, items, total: fmt(stageTotal) });
    }
    return { blocks, grandTotal: fmt(grandTotal), grandTotalValue: grandTotal };
};

/** lcca_report_builder._summary_replacements */
const sumNumbers = (value, key = '') => {
    if (typeof value === 'number') return key === 'total_scrap_value' ? -value : value;
    if (Array.isArray(value)) return value.reduce((s, v) => s + sumNumbers(v), 0);
    if (value && typeof value === 'object') return Object.entries(value).reduce((s, [k, v]) => s + sumNumbers(v, k), 0);
    return 0;
};
const buildSummary = (results) => {
    const stages = [['initial_stage', 'Initial stage'], ['use_stage', 'Use stage'], ['end_of_life', 'End-of-life'], ['reconstruction', 'Reconstruction']];
    const pillars = [['economic', 'Economic'], ['environmental', 'Environmental'], ['social', 'Social']];
    const stageTotals = stages.filter(([k]) => results[k] && Object.keys(obj(results[k])).length)
        .map(([k, label]) => [label, sumNumbers(obj(results[k]))]);
    const pillarTotals = pillars.map(([k, label]) => [label, stages.reduce((s, [sk]) => s + sumNumbers(obj(obj(results[sk])[k])), 0)]);
    const grand = stageTotals.reduce((s, [, v]) => s + v, 0);
    if (!grand || !stageTotals.length) return null;
    const [stageLabel, stageValue] = stageTotals.reduce((a, b) => (b[1] > a[1] ? b : a));
    const [pillarLabel, pillarValue] = pillarTotals.reduce((a, b) => (b[1] > a[1] ? b : a));
    return {
        stageLabel, stagePct: ((stageValue / grand) * 100).toFixed(2),
        pillarLabel, pillarPct: ((pillarValue / grand) * 100).toFixed(2),
    };
};

/** wpi_tables_latex._wpi_combined_table (Appendix C) */
const buildWpiTable = (traffic) => {
    const snapshot = obj(obj(traffic.wpi).data_snapshot);
    const base = obj(snapshot.base);
    const selected = obj(snapshot.selected);
    const ratio = obj(snapshot.ratio);
    if (!Object.keys(base).length && !Object.keys(selected).length && !Object.keys(ratio).length) return null;
    const section = (header, data, decimals) => ({
        header,
        rows: WPI_VEHICLES.map(([key, label]) => [label, ...WPI_COLUMNS.map(([col]) => {
            const v = obj(data[key])[col];
            return v === undefined || v === null ? EMDASH : fmt(v, decimals);
        })]),
    });
    return {
        columns: ['Vehicle', ...WPI_COLUMNS.map(([, label]) => label)],
        sections: [
            section('Ratio (Selected / Base)', ratio, RATIO_DECIMALS),
            section('Selected Year Values', selected),
            section('Base Year Values (2019)', base),
        ],
    };
};

/* ── Document ────────────────────────────────────────────────────────────── */

const DEFAULT_ON = (selections, key) => (selections?.[key] === undefined ? true : Boolean(selections[key]));

/**
 * @param {object} projectData  web project state (ProjectDataContext shape)
 * @param {object} options
 * @param {object|null} options.results   engine results (outputs_data.results)
 * @param {string} [options.currency]
 * @param {object} [options.selections]   ReportSectionModal selections (SECTION_KEYS → bool)
 * @returns {object} document model consumed by ReportPage
 */
export const buildReportDocument = (projectData = {}, { results = null, currency = '', selections = {} } = {}) => {
    const chunks = desktopChunksForReport(projectData, { results, currency });
    const general = obj(chunks.general_info);
    // Desktop stores the literal placeholder "Currency" until one is chosen
    // (results_latex treats it as unset); fall back like desktop does.
    const cur = [chunks.comparison_cache.currency, general.project_currency, projectData.currency, 'INR']
        .find((c) => c && String(c).trim() && String(c).trim().toLowerCase() !== 'currency');
    const traffic = obj(chunks.traffic_and_road_data);
    const mode = String(traffic.mode || resolveTrafficMode(projectData) || '').toUpperCase();
    const isGlobal = mode === 'GLOBAL';
    const on = (key) => DEFAULT_ON(selections, key);
    const K = SECTION_KEYS;

    let tableNo = 0;
    let figureNo = 0;
    const nextTable = () => { tableNo += 1; return tableNo; };
    const nextFigure = () => { figureNo += 1; return figureNo; };

    const doc = {
        meta: {
            projectName: general.project_name || obj(chunks.bridge_data).bridge_name || 'LCCA',
            currency: cur,
            trafficMode: mode || 'INDIA',
            generatedAt: new Date().toISOString(),
            hasResults: chunks.comparison_cache.is_valid,
            engine: obj(obj(projectData.outputs_data).engine),
        },
        titlePage: on(K.KEY_SHOW_TITLE_PAGE) ? buildTitlePage(general, cur) : null,
        showToc: true,
        introduction: null,
        inputSections: [],
        results: null,
        summary: null,
        appendices: [],
        tables: [],   // [{no, caption}] for List of Tables
        figures: [],  // [{no, caption}] for List of Figures
    };

    const registerTable = (caption) => { const no = nextTable(); doc.tables.push({ no, caption }); return no; };
    const registerFigure = (caption) => { const no = nextFigure(); doc.figures.push({ no, caption }); return no; };

    // 1. Introduction
    if (on(K.KEY_SHOW_INTRODUCTION)) {
        doc.introduction = { figureNo: registerFigure('3PS-LCC framework') };
    }

    // 2. Input data
    const input = [];

    if (on(K.KEY_SHOW_BRIDGE_DESC)) {
        input.push({
            id: 'bridge', title: 'Bridge geometry and description', kind: 'fields',
            tableNo: registerTable('Bridge Data Summary'), caption: 'Bridge Data Summary',
            rows: fieldRows(BRIDGE_FIELDS, chunks.bridge_data), notes: notes(chunks.bridge_data),
        });
    }
    if (on(K.KEY_SHOW_FINANCIAL)) {
        input.push({
            id: 'financial', title: 'Financial inputs', kind: 'fields',
            tableNo: registerTable('Financial Data Summary'), caption: 'Financial Data Summary',
            rows: fieldRows(FINANCIAL_FIELDS, chunks.financial_data), notes: notes(chunks.financial_data),
        });
    }
    if (on(K.KEY_SHOW_CONSTRUCTION)) {
        const tables = buildConstructionTables(chunks, cur).map((t) => ({ ...t, tableNo: registerTable(t.caption) }));
        input.push({ id: 'construction', title: 'Construction data', kind: 'construction', tables, currency: cur });
    }
    if (on(K.KEY_SHOW_USE_STAGE)) {
        input.push({
            id: 'maintenance', title: 'Maintenance data', kind: 'fields',
            tableNo: registerTable('Maintenance Data Summary'), caption: 'Maintenance Data Summary',
            rows: fieldRows(MAINTENANCE_FIELDS, chunks.maintenance_data), notes: notes(chunks.maintenance_data),
        });
    }

    // Traffic (sub-sections)
    const trafficChildren = [];
    if (on(K.KEY_SHOW_ROAD_TRAFFIC)) {
        if (isGlobal) {
            const g = obj(traffic.global_entry);
            const cost = g.road_user_cost_per_day;
            trafficChildren.push({
                id: 'traffic-global', title: 'Traffic and Road Data', kind: 'global-traffic',
                costText: cost === undefined || cost === null || cost === '' ? EMDASH : fmt(cost),
                currency: cur, source: (g.source || '').trim(), comments: (g.comments || '').trim(),
            });
        } else {
            const display = { ...traffic, alternate_road_carriageway: LANE_NAMES[traffic.alternate_road_carriageway] || traffic.alternate_road_carriageway };
            const no = registerTable('Traffic and Road Data');
            trafficChildren.push({
                id: 'traffic-road', title: 'Traffic and Road Data', kind: 'fields',
                intro: TABLE_INTROS.traffic(no), tableNo: no, caption: 'Traffic and Road Data',
                rows: fieldRows(TRAFFIC_FIELDS, display), notes: notes(traffic),
            });
        }
    }
    if (!isGlobal) {
        const vehicleData = obj(traffic.vehicle_data && Object.keys(obj(traffic.vehicle_data)).length ? traffic.vehicle_data : traffic.vehicles);
        if (on(K.KEY_SHOW_AVG_TRAFFIC)) {
            const no = registerTable('Vehicle Traffic Data');
            trafficChildren.push({
                id: 'traffic-adt', title: 'Average Daily Traffic', kind: 'adt', intro: TABLE_INTROS.adt(no),
                tableNo: no, caption: 'Vehicle Traffic Data',
                rows: VEHICLES.map(([key, label]) => {
                    const v = obj(vehicleData[key]);
                    return [label, fmtInt(v.vehicles_per_day ?? 0), fmtPlain(v.accident_percentage ?? 0), HAS_PWR.has(key) ? fmtPlain(v.pwr ?? 0) : EMDASH];
                }),
            });
        }
        if (on(K.KEY_SHOW_VEHICLE_EMISSION)) {
            const em = obj(chunks.diversion_emissions);
            if (em.mode === 'Calculate by Vehicle') {
                const factors = obj(em.emission_factors);
                const rerouteKm = num(traffic.additional_reroute_distance_km);
                let total = 0;
                const rows = VEHICLES.map(([key, label]) => {
                    const vpd = Math.trunc(num(obj(vehicleData[key]).vehicles_per_day));
                    const factor = num(factors[key]);
                    const e = vpd * factor * rerouteKm;
                    total += e;
                    return [label, fmtInt(vpd), fmtPlain(factor), fmtPlain(e)];
                });
                const caption = `Traffic Diversion Emissions (Detour: ${fmtPlain(rerouteKm)} km)`;
                const no = registerTable(caption);
                trafficChildren.push({
                    id: 'traffic-diversion', title: 'Traffic Diversion Emissions', kind: 'diversion',
                    intro: TABLE_INTROS.diversion(no), tableNo: no, caption, rows, total: fmtPlain(total), notes: notes(em),
                });
            } else if (em.mode === 'Enter Directly') {
                trafficChildren.push({
                    id: 'traffic-diversion', title: 'Traffic Diversion Emissions', kind: 'diversion-direct',
                    total: fmt(num(em.total_direct_emissions)), source: (obj(em.direct_entry).source || '').trim(),
                    comments: (obj(em.direct_entry).comments || '').trim(), notes: notes(em),
                });
            }
        }
        if (on(K.KEY_SHOW_PEAK_HOUR)) {
            const peak = obj(traffic.peak_hour_distribution && Object.keys(obj(traffic.peak_hour_distribution)).length ? traffic.peak_hour_distribution : traffic.peak_distribution);
            const n = Math.trunc(num(traffic.num_peak_hours, Object.keys(peak).length));
            const rows = [];
            for (let i = 1; i <= n; i += 1) {
                const v = peak[`peak_hour_${i}`];
                rows.push([`Peak Hour ${i}`, v === undefined || v === null ? EMDASH : fmtPlain(num(v) * 100)]);
            }
            const no = registerTable('Peak Hour Traffic Distribution');
            trafficChildren.push({
                id: 'traffic-peak', title: 'Peak Hour Distribution', kind: 'peak', intro: TABLE_INTROS.peak(no),
                tableNo: no, caption: 'Peak Hour Traffic Distribution', rows,
            });
        }
    }
    if (trafficChildren.length) input.push({ id: 'traffic', title: 'Traffic data', kind: 'group', children: trafficChildren });

    // Environmental input data
    const env = [];
    if (on(K.KEY_SHOW_SOCIAL_CARBON)) {
        const scc = obj(chunks.social_cost_data);
        const source = scc.source || scc.mode || '';
        if (RICKE_SOURCES.has(source)) {
            const caption = 'Social Cost of Carbon — Ricke et al. Parameters';
            const no = registerTable(caption);
            const cost = obj(scc.result).cost_of_carbon_local;
            env.push({
                id: 'scc', title: 'Social Cost of Carbon', kind: 'scc-ricke', intro: TABLE_INTROS.scc(),
                tableNo: no, caption, rows: fieldRows(RICKE_FIELDS(cur), scc.ricke),
                applied: cost === undefined || cost === null ? EMDASH : fmtPlain(cost), currency: cur, explorerUrl: SCC_EXPLORER_URL,
            });
        } else {
            const custom = obj(scc.custom);
            const value = custom.entered_value ?? custom.scc_value;
            env.push({
                id: 'scc', title: 'Social Cost of Carbon', kind: 'scc-custom', intro: TABLE_INTROS.scc(),
                value: value === undefined || value === null ? EMDASH : fmtPlain(value), currency: cur,
                source: (custom.source || '').trim(), comments: (custom.comments || '').trim(),
            });
        }
    }
    if (on(K.KEY_SHOW_MATERIAL_EMISSION)) {
        const { included, excluded } = collectForEmissions(chunks);
        const incNo = included.length ? registerTable('Materials Included in Carbon Emissions Calculation') : null;
        const excNo = excluded.length ? registerTable('Materials Excluded from Carbon Emissions Calculation') : null;
        env.push({
            id: 'material', title: 'Material Emission Factors', kind: 'material',
            intro: TABLE_INTROS.material(incNo ?? EMDASH, excNo), included, excluded, incNo, excNo,
            notes: notes(chunks.material_emissions_data),
        });
    }
    if (on(K.KEY_SHOW_TRANSPORT_EMISSION)) {
        const deliveries = buildTransport(chunks);
        const summaryNo = deliveries.length ? registerTable('Transport Emissions — Summary by Vehicle') : null;
        deliveries.forEach((d) => { d.tableNo = registerTable(d.caption); });
        env.push({
            id: 'transport', title: 'Transport Emissions', kind: 'transport',
            intro: TABLE_INTROS.transport(summaryNo ?? EMDASH), summaryNo, deliveries, notes: notes(chunks.transport_data),
        });
    }
    if (on(K.KEY_SHOW_ONSITE_EMISSION)) {
        const machinery = buildMachinery(chunks.machinery_emissions_data);
        const caption = machinery.mode === 'lumpsum' ? 'Machinery and Equipment Emissions (Lump Sum)' : 'Machinery and Equipment Emissions (Detailed)';
        env.push({
            id: 'machinery', title: 'Machinery and Equipment Emissions', kind: 'machinery', intro: TABLE_INTROS.machinery(),
            tableNo: registerTable(caption), caption, ...machinery, notes: notes(chunks.machinery_emissions_data),
        });
    }
    if (env.length) input.push({ id: 'environment', title: 'Environmental input data', kind: 'group', children: env });

    if (on(K.KEY_SHOW_RECYCLING)) {
        const { included, excluded } = collectForRecycling(chunks);
        const incNo = included.length ? registerTable('Materials Included in Recyclability Calculation') : null;
        const excNo = excluded.length ? registerTable('Materials Excluded from Recyclability Calculation') : null;
        input.push({ id: 'recycling', title: 'Recycling data', kind: 'recycling', included, excluded, incNo, excNo, currency: cur, notes: notes(chunks.recycling_data) });
    }
    doc.inputSections = input;

    // 3. LCCA results
    const engineResults = obj(chunks.comparison_cache.results);
    if (on(K.KEY_SHOW_LCCA_RESULTS)) {
        if (chunks.comparison_cache.is_valid && Object.keys(engineResults).length) {
            const table = buildResultsTable(engineResults);
            const tableNoResults = registerTable('Life Cycle Cost Analysis Results');
            const figs = [
                { key: 'pillar_donut', caption: 'LCC components results' },
                { key: 'stage_bars', caption: 'Distribution of 3PS and 3 stages of LCC' },
                { key: 'pillar_bars', caption: 'Distribution of various components of road user cost during construction' },
            ].map((f) => ({ ...f, figureNo: registerFigure(f.caption) }));
            doc.results = {
                intro: TABLE_INTROS.results(tableNoResults), tableNo: tableNoResults, caption: 'Life Cycle Cost Analysis Results',
                currency: cur, table, figures: figs, figuresIntro: TABLE_INTROS.figures(figs.map((f) => f.figureNo)), rawResults: engineResults,
            };
        } else {
            doc.results = { empty: true };
        }
    }

    // 4. Summary and conclusions
    doc.summary = Object.keys(engineResults).length ? buildSummary(engineResults) : { stageLabel: '', stagePct: '', pillarLabel: '', pillarPct: '' };

    // 5. Appendices
    doc.appendices = [
        { id: 'appendix-a', kind: 'appendix-a' },
        { id: 'appendix-b', kind: 'appendix-b' },
    ];
    if (!isGlobal) {
        const wpi = buildWpiTable(traffic);
        if (wpi) doc.appendices.push({ id: 'appendix-c', kind: 'appendix-c', title: 'Appendix C: Miscellaneous data', wpi, currency: cur });
    }

    return doc;
};

export const _internal = { collectForEmissions, collectForRecycling, buildTransport, buildMachinery, buildResultsTable, buildSummary, buildWpiTable, LANE_NAMES };

/**
 * The project index — direct, schema-driven access to the LCCA input data.
 *
 * This replaces the per-question approach (curated context slices, per-topic
 * intents, a hand-written synonym table) with one generic mechanism:
 *
 *   1. WALK the whole normalized project tree once, turning every meaningful
 *      field into a searchable entry: "Financial data — Discount rate: 6.5",
 *      "Traffic data — HCV — Vehicles per day: 400", every material row,
 *      every computed result line. New schema fields become queryable
 *      automatically; nobody hand-registers anything.
 *   2. SEARCH the entries to answer a question:
 *      - lexical token match (rules tier) for exact mentions — "span",
 *        "discount rate", "HCV";
 *      - embedding similarity (encoder tier) for paraphrase and synonymy —
 *        "cement" ≈ "PCC M15" is what embeddings are for; the deleted synonym
 *        table was a hand-written imitation of one.
 *   3. The generative tiers receive the index in their context, so they can
 *      answer any data question directly.
 *
 * Hand-curated intents remain only for AGGREGATES (totals, drivers,
 * summaries) — computations, not lookups.
 */

import { BREAKDOWN_STAGES } from '../../../gui/components/outputs/breakdownStages.js';

// ---------------------------------------------------------------------------
// Walking
// ---------------------------------------------------------------------------

const SCALAR_SECTIONS = [
    ['general_info', 'General information'],
    ['bridge_data', 'Bridge data'],
    ['financial_data', 'Financial data'],
    ['traffic_data', 'Traffic data'],
    ['transport_data', 'Transport data'],
    ['carbon_emission_data', 'Carbon emissions data'],
    ['maintenance_repair_data', 'Maintenance & repair data'],
    ['recycling_data', 'Recycling data'],
    ['demolition_data', 'Demolition data'],
];

const MATERIAL_SECTIONS = [
    ['foundation_data', 'Foundation'],
    ['substructure_data', 'Sub Structure'],
    ['superstructure_data', 'Super Structure'],
    ['miscellaneous_data', 'Miscellaneous'],
];

const SKIP_KEYS = new Set([
    'id', 'ids', 'schema_version', 'createdat', 'state', 'result', 'results',
]);

const ACRONYMS = {
    hcv: 'HCV', mcv: 'MCV', lcv: 'LCV', adt: 'ADT', pwr: 'PWR', wpi: 'WPI',
    scc: 'SCC', ssp: 'SSP', rcp: 'RCP', inr: 'INR', usd: 'USD', vot: 'VOT',
    pcc: 'PCC', rcc: 'RCC', km: 'km', kgco2e: 'kgCO2e',
};

const humanize = (key) => String(key)
    .replace(/_/g, ' ')
    .trim()
    .split(' ')
    .map((word) => ACRONYMS[word.toLowerCase()] || word)
    .join(' ')
    .replace(/^./, (c) => c.toUpperCase());

const isScalar = (value) => ['string', 'number', 'boolean'].includes(typeof value);

const meaningful = (value) => !(
    value === null || value === undefined || value === ''
    || (typeof value === 'number' && !Number.isFinite(value))
);

const MAX_DEPTH = 4;
const MAX_ENTRIES = 600;
const MAX_ROWS_PER_SECTION = 40;

/** Recursively index the scalar leaves of one section's object tree. */
function walkObject(node, sectionLabel, path, out, depth = 0) {
    if (out.length >= MAX_ENTRIES || depth > MAX_DEPTH) return;
    if (!node || typeof node !== 'object') return;

    for (const [key, value] of Object.entries(node)) {
        if (SKIP_KEYS.has(key.toLowerCase())) continue;
        const label = [...path, humanize(key)];

        if (isScalar(value)) {
            if (!meaningful(value)) continue;
            out.push({
                kind: 'field',
                section: sectionLabel,
                label: label.join(' — '),
                value,
                text: `${sectionLabel} — ${label.join(' — ')}: ${value}`,
            });
        } else if (Array.isArray(value)) {
            // Generic arrays: index scalar lists inline, object rows by position.
            if (value.every(isScalar)) {
                if (value.length) {
                    out.push({
                        kind: 'field',
                        section: sectionLabel,
                        label: label.join(' — '),
                        value: value.join(', '),
                        text: `${sectionLabel} — ${label.join(' — ')}: ${value.join(', ')}`,
                    });
                }
            } else {
                value.slice(0, MAX_ROWS_PER_SECTION).forEach((item, index) => {
                    walkObject(item, sectionLabel, [...label, `#${index + 1}`], out, depth + 1);
                });
            }
        } else if (typeof value === 'object') {
            walkObject(value, sectionLabel, label, out, depth + 1);
        }
    }
}

/** Construction areas: one entry per active material row, one line each. */
function walkMaterials(project, out) {
    for (const [dataKey, sectionLabel] of MATERIAL_SECTIONS) {
        const sections = Array.isArray(project[dataKey]) ? project[dataKey] : [];
        for (const section of sections) {
            const rows = Array.isArray(section?.rows) ? section.rows : [];
            for (const row of rows.slice(0, MAX_ROWS_PER_SECTION)) {
                if (!row?.workName || row?.state?.in_trash) continue;
                const qty = meaningful(row.qty) ? ` — ${row.qty} ${row.unit || ''}`.trimEnd() : '';
                const rate = meaningful(row.rate) ? ` @ ${row.rate}` : '';
                out.push({
                    kind: 'material',
                    section: sectionLabel,
                    label: row.workName,
                    value: row.qty ?? null,
                    text: `${sectionLabel} material — ${row.workName}${qty}${rate}`,
                });
            }
        }
    }
}

/** Computed results: every non-zero breakdown line, with its display label. */
function walkResults(results, out) {
    if (!results) return;
    for (const stage of BREAKDOWN_STAGES) {
        const stageData = results[stage.resultKey];
        if (!stageData) continue;
        for (const row of stage.rows) {
            const value = stageData?.[row.pillar]?.[row.key];
            if (!meaningful(value) || value === 0) continue;
            out.push({
                kind: 'result',
                section: stage.label,
                label: row.label,
                value: Math.round(value),
                text: `Computed result — ${stage.label} — ${row.label} (${row.pillar}): ${Math.round(value)}`,
            });
        }
    }
}

/** Build the full index for one project. Bounded by construction. */
export function buildProjectIndex(projectData) {
    const project = projectData || {};
    const entries = [];
    walkMaterials(project, entries);
    for (const [dataKey, sectionLabel] of SCALAR_SECTIONS) {
        walkObject(project[dataKey], sectionLabel, [], entries);
    }
    walkResults(project.outputs_data?.results, entries);
    return entries.slice(0, MAX_ENTRIES);
}

// ---------------------------------------------------------------------------
// Lexical search (the rules tier's data access)
// ---------------------------------------------------------------------------

const STOPWORDS = new Set([
    'what', 'whats', 'which', 'was', 'is', 'are', 'the', 'a', 'an', 'of', 'in',
    'on', 'for', 'used', 'use', 'we', 'did', 'does', 'do', 'type', 'kind',
    'there', 'any', 'this', 'that', 'project', 'bridge', 'how', 'much', 'many',
    'was', 'were', 'been', 'and', 'to', 'with', 'per', 'our', 'my', 'me',
    'enter', 'entered', 'specified', 'value', 'data', 'tell', 'show', 'about',
    'have', 'has', 'had', 'it', 'its', 'they', 'will', 'would', 'can', 'could',
    // Generic unit-words: they appear in questions ("what RATE did we use")
    // but rarely in the field text they refer to ("@ 13400"). Specific field
    // names still carry them implicitly ("Discount rate" matches "discount").
    'rate', 'rates', 'amount', 'number',
]);

export const questionTerms = (question) =>
    String(question || '').toLowerCase().replace(/[^a-z0-9\s]/g, ' ')
        .split(/\s+/)
        .filter((word) => word.length > 1 && !STOPWORDS.has(word));

/**
 * Score entries by weighted token overlap. Token weights are inverse to how
 * many entries contain them, so "rate" (everywhere) counts little and "hcv"
 * (one entry) counts a lot — a tiny idf, no tuning knobs.
 */
export function lexicalSearch(question, entries, { limit = 4 } = {}) {
    const terms = [...new Set(questionTerms(question))];
    if (!terms.length || !entries.length) return [];

    const lowered = entries.map((entry) => entry.text.toLowerCase());
    const weights = new Map(terms.map((term) => {
        const df = lowered.reduce((n, text) => n + (text.includes(term) ? 1 : 0), 0);
        return [term, df === 0 ? 0 : 1 / Math.sqrt(df)];
    }));

    // A hit needs at least one reasonably specific term, or it's noise.
    const specific = terms.some((term) => {
        const w = weights.get(term);
        return w > 0 && w >= 1 / Math.sqrt(Math.max(1, entries.length * 0.25));
    });
    if (!specific) return [];

    const scored = entries
        .map((entry, i) => {
            const matched = terms.filter((term) => lowered[i].includes(term));
            return {
                entry,
                matched: matched.length,
                score: matched.reduce((sum, term) => sum + weights.get(term), 0),
            };
        })
        // Coverage gate: an entry must account for most of the question's
        // content words. One stray token ("life" in "the meaning of life"
        // hitting "Design life") is not an answer.
        .filter(({ matched }) => matched > 0 && matched / terms.length >= 0.6)
        .sort((a, b) => b.score - a.score);

    return scored.slice(0, limit);
}

/** Render search hits as one grounded sentence. */
export function formatMatches(matches) {
    const texts = matches.map(({ entry }) => entry.text);
    return `From the project data: ${texts.join('; ')}.`;
}

/** Inventory overview for "what is the bridge made of" style questions. */
export function materialsOverview(entries) {
    const materials = entries.filter((entry) => entry.kind === 'material');
    if (!materials.length) {
        return 'No construction materials have been entered yet — add them under '
            + 'Construction Work Data (Foundation, Sub/Super Structure, Miscellaneous).';
    }
    const bySection = new Map();
    for (const entry of materials) {
        if (!bySection.has(entry.section)) bySection.set(entry.section, []);
        bySection.get(entry.section).push(entry.label);
    }
    const parts = [...bySection.entries()].map(([section, names]) => {
        const shown = names.slice(0, 4);
        return `${section} (${names.length}): ${shown.join(', ')}${names.length > shown.length ? ', …' : ''}`;
    });
    return `The project has ${materials.length} material items. ${parts.join('. ')}.`;
}

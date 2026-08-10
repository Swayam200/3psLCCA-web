/**
 * In-memory project store + the CRUD primitives.
 *
 * ARCHITECTURAL POINT OF THE WHOLE DEMO:
 * the AI layer never touches this module's internal state directly. It emits
 * *operations* (see lib/ai/tools.js), which are validated and then executed
 * through exactly the same functions the REST handlers call. So an AI edit is
 * indistinguishable from a human edit — same validation, same audit trail,
 * same undo. If the model hallucinates a field or a section, it fails at the
 * same gate a malformed HTTP request would.
 */

import { createSeedProject, SECTION_KEYS, SECTION_LABELS } from './seed.js';

const VALID_PARAMS = {
    analysis_period: { min: 1, max: 150, label: 'Analysis period (years)' },
    discount_rate: { min: 0, max: 30, label: 'Discount rate (%)' },
    inflation_rate: { min: 0, max: 30, label: 'Inflation rate (%)' },
    maintenance_interval: { min: 1, max: 50, label: 'Maintenance interval (years)' },
    maintenance_pct: { min: 0, max: 50, label: 'Maintenance cost (% of construction)' },
    demolition_pct: { min: 0, max: 50, label: 'Demolition cost (% of construction)' },
    social_cost_of_carbon: { min: 0, max: 1e6, label: 'Social cost of carbon (INR/tCO₂e)' },
    annual_road_user_cost: { min: 0, max: 1e12, label: 'Annual road user cost (INR/yr)' },
};

export class ValidationError extends Error {
    constructor(message) {
        super(message);
        this.name = 'ValidationError';
        this.statusCode = 400;
    }
}

let project = createSeedProject();
let auditLog = [];
let undoStack = [];
let seq = 1000;

const snapshot = () => JSON.parse(JSON.stringify(project));

const record = (actor, action, detail, before) => {
    const entry = {
        id: `evt-${++seq}`,
        at: new Date().toISOString(),
        actor,          // 'user' | 'ai'
        action,
        detail,
    };
    auditLog.unshift(entry);
    undoStack.push({ entry, before });
    if (undoStack.length > 50) undoStack.shift();
    return entry;
};

const assertSection = (sectionKey) => {
    if (!SECTION_KEYS.includes(sectionKey)) {
        throw new ValidationError(
            `Unknown section "${sectionKey}". Valid sections: ${SECTION_KEYS.join(', ')}.`,
        );
    }
};

const requirePositive = (value, field) => {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 0) {
        throw new ValidationError(`"${field}" must be a non-negative number (got ${JSON.stringify(value)}).`);
    }
    return parsed;
};

export const getProject = () => project;
export const getAuditLog = () => auditLog;
export const getSectionKeys = () => SECTION_KEYS;
export const getSectionLabels = () => SECTION_LABELS;

export function findRow(id) {
    for (const key of SECTION_KEYS) {
        const row = project[key].find((r) => r.id === id);
        if (row) return { sectionKey: key, row };
    }
    return null;
}

/**
 * Resolve a row by id OR by a fuzzy work-name match. The AI path leans on the
 * name match ("delete the MS railing"); the UI path always passes an id.
 * Ambiguous matches are an error, not a guess — the model does not get to pick.
 */
export function resolveRow({ id, match, section }) {
    if (id) {
        const found = findRow(id);
        if (!found) throw new ValidationError(`No material with id "${id}".`);
        return found;
    }
    if (!match) throw new ValidationError('Provide either "id" or "match" to identify a material.');

    const needle = String(match).toLowerCase().trim();
    const keys = section ? [section] : SECTION_KEYS;
    if (section) assertSection(section);

    const hits = [];
    for (const key of keys) {
        for (const row of project[key]) {
            if (row.state.in_trash) continue;
            if (row.workName.toLowerCase().includes(needle)) hits.push({ sectionKey: key, row });
        }
    }
    if (hits.length === 0) throw new ValidationError(`No active material matching "${match}".`);
    if (hits.length > 1) {
        throw new ValidationError(
            `"${match}" is ambiguous — it matches ${hits.length} materials: `
            + `${hits.map((h) => h.row.workName).join('; ')}. Be more specific.`,
        );
    }
    return hits[0];
}

// ---------------------------------------------------------------- CREATE ----
export function createMaterial(sectionKey, payload, actor = 'user') {
    assertSection(sectionKey);
    const before = snapshot();

    const workName = String(payload.workName || '').trim();
    if (!workName) throw new ValidationError('"workName" is required.');

    const row = {
        id: `${sectionKey.replace('_data', '')}-row-${++seq}`,
        workName,
        qty: requirePositive(payload.qty ?? 0, 'qty'),
        unit: String(payload.unit || 'nos'),
        rate: requirePositive(payload.rate ?? 0, 'rate'),
        source: String(payload.source || (actor === 'ai' ? 'AI-assisted entry' : 'Manual entry')),
        carbonEmission: {
            factor: requirePositive(payload.carbonFactor ?? 0, 'carbonFactor'),
            perUnit: String(payload.unit || 'nos'),
            source: payload.carbonSource || 'User supplied',
        },
        state: { in_trash: false },
    };

    project[sectionKey].push(row);
    record(actor, 'create', `Added "${row.workName}" to ${SECTION_LABELS[sectionKey]} (${row.qty} ${row.unit} @ ${row.rate})`, before);
    return row;
}

// ---------------------------------------------------------------- UPDATE ----
const EDITABLE_FIELDS = ['workName', 'qty', 'unit', 'rate', 'source'];

export function updateMaterial(selector, fields, actor = 'user') {
    const { sectionKey, row } = resolveRow(selector);
    const before = snapshot();
    const changes = [];

    for (const [field, value] of Object.entries(fields || {})) {
        if (field === 'carbonFactor') {
            const next = requirePositive(value, 'carbonFactor');
            changes.push(`carbonFactor ${row.carbonEmission.factor} → ${next}`);
            row.carbonEmission.factor = next;
            continue;
        }
        if (!EDITABLE_FIELDS.includes(field)) {
            throw new ValidationError(
                `Field "${field}" is not editable. Editable: ${EDITABLE_FIELDS.join(', ')}, carbonFactor.`,
            );
        }
        const next = (field === 'qty' || field === 'rate')
            ? requirePositive(value, field)
            : String(value);
        if (row[field] !== next) changes.push(`${field} ${row[field]} → ${next}`);
        row[field] = next;
        if (field === 'unit') row.carbonEmission.perUnit = next;
    }

    if (!changes.length) throw new ValidationError('No changes were supplied.');
    record(actor, 'update', `Updated "${row.workName}" in ${SECTION_LABELS[sectionKey]}: ${changes.join(', ')}`, before);
    return row;
}

// ---------------------------------------------------------------- DELETE ----
/** Soft delete, matching the real app's construction "trash" workflow. */
export function deleteMaterial(selector, actor = 'user') {
    const { sectionKey, row } = resolveRow(selector);
    const before = snapshot();
    row.state.in_trash = true;
    record(actor, 'delete', `Moved "${row.workName}" (${SECTION_LABELS[sectionKey]}) to trash`, before);
    return row;
}

export function restoreMaterial(id, actor = 'user') {
    const found = findRow(id);
    if (!found) throw new ValidationError(`No material with id "${id}".`);
    const before = snapshot();
    found.row.state.in_trash = false;
    record(actor, 'restore', `Restored "${found.row.workName}" from trash`, before);
    return found.row;
}

// ------------------------------------------------------------ BULK / PARAM ---
export function scaleRates({ section, factor, field = 'rate' }, actor = 'user') {
    if (section) assertSection(section);
    const multiplier = Number(factor);
    if (!Number.isFinite(multiplier) || multiplier <= 0) {
        throw new ValidationError(`"factor" must be a positive number (got ${JSON.stringify(factor)}).`);
    }
    if (!['rate', 'qty'].includes(field)) {
        throw new ValidationError(`"field" must be "rate" or "qty" (got ${JSON.stringify(field)}).`);
    }

    const before = snapshot();
    const keys = section ? [section] : SECTION_KEYS;
    let touched = 0;
    for (const key of keys) {
        for (const row of project[key]) {
            if (row.state.in_trash) continue;
            row[field] = Number((row[field] * multiplier).toFixed(2));
            touched += 1;
        }
    }
    if (!touched) throw new ValidationError('No active materials matched.');

    const pct = ((multiplier - 1) * 100).toFixed(1);
    const scope = section ? SECTION_LABELS[section] : 'all sections';
    record(actor, 'scale', `Scaled ${field} by ${pct}% across ${scope} (${touched} rows)`, before);
    return { touched, multiplier, field, scope };
}

export function setParameter(name, value, actor = 'user') {
    const spec = VALID_PARAMS[name];
    if (!spec) {
        throw new ValidationError(
            `Unknown parameter "${name}". Valid: ${Object.keys(VALID_PARAMS).join(', ')}.`,
        );
    }
    const next = Number(value);
    if (!Number.isFinite(next) || next < spec.min || next > spec.max) {
        throw new ValidationError(
            `"${name}" must be between ${spec.min} and ${spec.max} (got ${JSON.stringify(value)}).`,
        );
    }
    const before = snapshot();
    const prev = project.financial_data[name];
    project.financial_data[name] = next;
    record(actor, 'parameter', `${spec.label}: ${prev} → ${next}`, before);
    return { name, previous: prev, value: next };
}

export const parameterSpecs = () =>
    Object.entries(VALID_PARAMS).map(([name, spec]) => ({ name, ...spec }));

// ------------------------------------------------------------------ UNDO ----
export function undoLast() {
    const last = undoStack.pop();
    if (!last) throw new ValidationError('Nothing to undo.');
    project = last.before;
    auditLog = auditLog.filter((e) => e.id !== last.entry.id);
    auditLog.unshift({
        id: `evt-${++seq}`,
        at: new Date().toISOString(),
        actor: 'user',
        action: 'undo',
        detail: `Undid: ${last.entry.detail}`,
    });
    return last.entry;
}

export function resetProject() {
    project = createSeedProject();
    auditLog = [];
    undoStack = [];
    seq = 1000;
    return project;
}

/**
 * The tool contract shared by every provider.
 *
 * This is the whole trick behind "ask for an update and it updates in real
 * time": the model is never asked to produce a report, a number, or a diff of
 * the UI. It is asked to produce a short list of *operations* drawn from this
 * fixed vocabulary. Everything downstream — validation, execution, recompute,
 * re-render — is ordinary deterministic application code.
 *
 * The same declarations are rendered into:
 *   - Gemini's  functionDeclarations
 *   - Claude's  tools[]
 *   - the mock provider's pattern table
 */

import {
    createMaterial, updateMaterial, deleteMaterial, restoreMaterial,
    scaleRates, setParameter, getSectionKeys, getSectionLabels,
    parameterSpecs, ValidationError,
} from '../store.js';

export const TOOLS = [
    {
        name: 'create_material',
        description:
            'Add a new construction material line item to one of the four construction '
            + 'sections. Use when the user asks to add/insert a material or work item.',
        parameters: {
            type: 'object',
            properties: {
                section: { type: 'string', enum: getSectionKeys(), description: 'Target construction section.' },
                workName: { type: 'string', description: 'Descriptive name of the work item, e.g. "Pier shaft, RCC M40".' },
                qty: { type: 'number', description: 'Quantity, in the given unit.' },
                unit: { type: 'string', description: 'Unit of measure, e.g. m³, m², m, kg, nos.' },
                rate: { type: 'number', description: 'Unit rate in project currency (INR).' },
                source: { type: 'string', description: 'Rate source / reference, if the user gave one.' },
                carbonFactor: { type: 'number', description: 'Embodied carbon in tCO2e per unit. Use 0 if unknown.' },
            },
            required: ['section', 'workName', 'qty', 'unit', 'rate'],
        },
    },
    {
        name: 'update_material',
        description:
            'Change fields on an existing material. Identify it with "match" (a distinctive '
            + 'substring of its work name) or "id". Only pass the fields that change.',
        parameters: {
            type: 'object',
            properties: {
                match: { type: 'string', description: 'Substring of the work name identifying the row.' },
                id: { type: 'string', description: 'Exact row id, if known.' },
                section: { type: 'string', enum: getSectionKeys(), description: 'Narrow the search to one section.' },
                fields: {
                    type: 'object',
                    description: 'Fields to change: workName, qty, unit, rate, source, carbonFactor.',
                    properties: {
                        workName: { type: 'string' },
                        qty: { type: 'number' },
                        unit: { type: 'string' },
                        rate: { type: 'number' },
                        source: { type: 'string' },
                        carbonFactor: { type: 'number' },
                    },
                },
            },
            required: ['fields'],
        },
    },
    {
        name: 'delete_material',
        description: 'Move a material to the trash (soft delete). It can be restored later.',
        parameters: {
            type: 'object',
            properties: {
                match: { type: 'string', description: 'Substring of the work name identifying the row.' },
                id: { type: 'string' },
                section: { type: 'string', enum: getSectionKeys() },
            },
            required: [],
        },
    },
    {
        name: 'restore_material',
        description: 'Restore a previously trashed material by its id.',
        parameters: {
            type: 'object',
            properties: { id: { type: 'string' } },
            required: ['id'],
        },
    },
    {
        name: 'scale_rates',
        description:
            'Bulk-multiply the rate (or quantity) of every active material, optionally limited '
            + 'to one section. Use for "increase all rates by 8%" style requests. '
            + 'factor 1.08 = +8%, factor 0.95 = −5%.',
        parameters: {
            type: 'object',
            properties: {
                section: { type: 'string', enum: getSectionKeys(), description: 'Omit to apply to all sections.' },
                factor: { type: 'number', description: 'Multiplier. 1.08 means +8%.' },
                field: { type: 'string', enum: ['rate', 'qty'], description: 'Defaults to "rate".' },
            },
            required: ['factor'],
        },
    },
    {
        name: 'set_parameter',
        description:
            'Change one financial/analysis parameter that drives the life-cycle calculation.',
        parameters: {
            type: 'object',
            properties: {
                name: { type: 'string', enum: parameterSpecs().map((p) => p.name) },
                value: { type: 'number' },
            },
            required: ['name', 'value'],
        },
    },
    {
        name: 'answer',
        description:
            'Answer a read-only question about the project without changing anything. '
            + 'Use this whenever the user asks "what is", "how much", "which", or similar.',
        parameters: {
            type: 'object',
            properties: { text: { type: 'string', description: 'The answer, in one or two sentences.' } },
            required: ['text'],
        },
    },
];

/** System prompt shared by the real providers. */
export const systemPrompt = () => {
    const labels = getSectionLabels();
    const params = parameterSpecs()
        .map((p) => `  - ${p.name}: ${p.label}, allowed ${p.min}–${p.max}`)
        .join('\n');

    return `You are the editing assistant inside 3psLCCA, a life-cycle cost analysis tool for bridge projects.

The user is looking at a project made of four construction sections:
${Object.entries(labels).map(([k, v]) => `  - ${k} ("${v}")`).join('\n')}

Each section holds material line items: { workName, qty, unit, rate, source, carbonFactor }.
Costs are in INR. Carbon factors are tCO2e per unit.

Tunable analysis parameters:
${params}

RULES
1. Translate the user's request into tool calls. Never describe an edit you could make with a tool — make it.
2. Emit several tool calls in one turn when the request implies several edits.
3. Never invent quantities, rates, or carbon factors the user did not give. If a required
   value is genuinely missing and cannot be inferred, use the "answer" tool to ask for it.
4. For read-only questions, use the "answer" tool only. Do not edit.
5. Percentage changes go through scale_rates (factor 1.08 for +8%), not one update per row.
6. Identify rows with a short distinctive substring of the work name, e.g. "MS railing".
Do not restate the tool calls in prose; the application shows the user what changed.`;
};

/** Map a tool name to its store function. Every AI edit funnels through here. */
const EXECUTORS = {
    create_material: (a) => {
        const row = createMaterial(a.section, a, 'ai');
        return { summary: `Added "${row.workName}" to ${getSectionLabels()[a.section]}.`, row };
    },
    update_material: (a) => {
        const row = updateMaterial({ id: a.id, match: a.match, section: a.section }, a.fields, 'ai');
        return { summary: `Updated "${row.workName}".`, row };
    },
    delete_material: (a) => {
        const row = deleteMaterial({ id: a.id, match: a.match, section: a.section }, 'ai');
        return { summary: `Moved "${row.workName}" to trash.`, row };
    },
    restore_material: (a) => {
        const row = restoreMaterial(a.id, 'ai');
        return { summary: `Restored "${row.workName}".`, row };
    },
    scale_rates: (a) => {
        const res = scaleRates(a, 'ai');
        const pct = ((res.multiplier - 1) * 100).toFixed(1);
        return { summary: `Scaled ${res.field} by ${pct}% across ${res.scope} (${res.touched} rows).`, result: res };
    },
    set_parameter: (a) => {
        const res = setParameter(a.name, a.value, 'ai');
        return { summary: `${a.name}: ${res.previous} → ${res.value}.`, result: res };
    },
    answer: (a) => ({ summary: a.text, readOnly: true }),
};

/**
 * Execute a model-produced call list. Each call is independently validated;
 * one bad call is reported and skipped rather than aborting the batch, so a
 * partially-wrong model response still does the parts it got right.
 */
export function executeCalls(calls) {
    const applied = [];
    const rejected = [];

    for (const call of calls) {
        const exec = EXECUTORS[call.name];
        if (!exec) {
            rejected.push({ name: call.name, args: call.args, error: `Unknown tool "${call.name}".` });
            continue;
        }
        try {
            const result = exec(call.args || {});
            applied.push({ name: call.name, args: call.args, ...result });
        } catch (error) {
            if (error instanceof ValidationError) {
                rejected.push({ name: call.name, args: call.args, error: error.message });
            } else {
                rejected.push({ name: call.name, args: call.args, error: `Unexpected: ${error.message}` });
            }
        }
    }
    return { applied, rejected };
}

/**
 * Direct data access via the schema-driven project index.
 *
 * Born from a real failure ("What was the type of cement used?" was
 * unanswerable) and a real review comment: per-question rules don't scale.
 * These tests deliberately ask about sections the AI code never
 * special-cases — traffic, demolition, bridge geometry — because the walker
 * must make the ENTIRE schema queryable with zero per-question code.
 */
import assert from 'node:assert/strict';
import test from 'node:test';

import { buildAiContext } from '../../src/lib/ai/tools/context.js';
import {
    buildProjectIndex, lexicalSearch, materialsOverview,
} from '../../src/lib/ai/tools/projectIndex.js';
import { systemPrompt } from '../../src/lib/ai/tools/schema.js';
import { generate as rulesGenerate } from '../../src/lib/ai/providers/rules.js';
import { generate as encoderGenerate } from '../../src/lib/ai/providers/localEncoder.js';
import { PROJECT_FIXTURE } from './fixtures.js';

const context = buildAiContext(PROJECT_FIXTURE);

const rulesAnswer = async (prompt) => {
    const result = await rulesGenerate(prompt, { context });
    return { text: result.calls[0].args.text, intent: result.intent, unparsed: Boolean(result.unparsed) };
};

// ------------------------------------------------------------- the walker ---

test('the walker indexes every section generically — no per-section code', () => {
    const index = buildProjectIndex(PROJECT_FIXTURE);
    const texts = index.map((entry) => entry.text);

    const expectations = [
        /Bridge data — Span: 240/,
        /Financial data — Discount rate: 6\.5/,
        /Traffic data — Vehicles — HCV — Vehicles per day: 400/,
        /Demolition data — Demolition cost pct: 6/,
        /Foundation material — PCC M15 levelling course — 180 m³ @ 6250/,
        /Computed result — Initial Stage Costs — Construction Cost \(economic\): 90000000/,
    ];
    for (const pattern of expectations) {
        assert.ok(texts.some((t) => pattern.test(t)), `missing: ${pattern}`);
    }
});

test('trashed rows and empty values never reach the index', () => {
    const index = buildProjectIndex(PROJECT_FIXTURE);
    assert.ok(!index.some((entry) => entry.text.includes('Old trashed item')));
    assert.ok(!index.some((entry) => entry.text.includes('undefined')));
});

test('the index is bounded', () => {
    const huge = {
        ...PROJECT_FIXTURE,
        carbon_emission_data: Object.fromEntries(
            Array.from({ length: 2000 }, (_, i) => [`field_${i}`, i + 1]),
        ),
    };
    assert.ok(buildProjectIndex(huge).length <= 600);
});

// -------------------------------------------------- lexical search (rules) ---

test('questions about never-special-cased fields answer via lexical search', async () => {
    const cases = [
        ['What is the span of the bridge?', /Span: 240/],
        ['What discount rate did we use?', /Discount rate: 6\.5/],
        ['How many HCV vehicles per day?', /HCV — Vehicles per day: 400/],
        ['What is the demolition cost percentage?', /Demolition cost pct: 6/],
    ];
    for (const [prompt, expected] of cases) {
        const { text, intent, unparsed } = await rulesAnswer(prompt);
        assert.equal(unparsed, false, prompt);
        assert.equal(intent, 'data_lookup', prompt);
        assert.match(text, expected, prompt);
    }
});

test('material rows are reachable by their own words', async () => {
    const { text, intent } = await rulesAnswer('What rate did we enter for the girder?');
    assert.equal(intent, 'data_lookup');
    assert.match(text, /PSC I-girder/);
});

test('unanswerable questions stay unparsed instead of returning noise', async () => {
    const { unparsed } = await rulesAnswer('What is the meaning of life?');
    assert.equal(unparsed, true);
});

test('generic-only terms do not trigger a low-value dump', () => {
    // "value"/"data" are stopwords; "cost" matches half the index — the
    // specificity gate must reject the search rather than return noise.
    const matches = lexicalSearch('cost cost cost', context.index);
    assert.equal(matches.length, 0);
});

// ------------------------------------------- semantic search (encoder tier) ---

test('encoder matches index entries semantically — the synonym table is dead', async () => {
    // Fake embedder: puts the question near the PCC material row, the way the
    // real MiniLM puts "cement" near concrete-family items.
    const fakeEmbed = async (texts) => texts.map((text) => {
        const lower = text.toLowerCase();
        const cementish = /cement|concrete|pcc|binder/.test(lower) ? 1 : 0;
        const other = lower.includes('total') ? 1 : 0;
        const norm = Math.hypot(cementish, other, 0.1);
        return [cementish / norm, other / norm, 0.1 / norm];
    });

    const result = await encoderGenerate('which binder was specified?', {
        context,
        embedder: fakeEmbed,
        threshold: 0.5,
    });
    assert.ok(!result.unparsed);
    assert.equal(result.intent, 'data_lookup');
    assert.match(result.calls[0].args.text, /PCC M15 levelling course/);
    assert.ok(result.confidence >= 0.5);
});

// ------------------------------------------------------------- aggregates ---

test('materials overview still works, now from the index', async () => {
    const { text, intent } = await rulesAnswer('What materials is the bridge made of?');
    assert.equal(intent, 'materials');
    assert.match(text, /4 material items/);
    assert.match(text, /Foundation \(2\)/);

    assert.match(materialsOverview([]), /No construction materials/);
});

// ------------------------------------------------------- generative tiers ---

test('the system prompt carries the full index as plain lines', () => {
    const prompt = systemPrompt(context);
    assert.match(prompt, /PROJECT DATA/);
    assert.match(prompt, /Traffic data — Vehicles — HCV — Vehicles per day: 400/);
    // ...but not the verbose structured entries.
    assert.ok(!prompt.includes('"kind": "field"'));
});

// ------------------------------------------------------------ edit safety ---

test('edit phrasings still refuse before any lookup can claim their nouns', async () => {
    for (const prompt of ['Set the discount rate to 8', 'Add a new material to the substructure']) {
        const { text, intent } = await rulesAnswer(prompt);
        assert.equal(intent, 'edit_refusal', prompt);
        assert.match(text, /read-only/);
    }
});

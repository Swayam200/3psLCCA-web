import assert from 'node:assert/strict';
import test from 'node:test';

import { buildAiContext, formatAmount } from '../../src/lib/ai/tools/context.js';
import { PROJECT_FIXTURE, UNCALCULATED_PROJECT, EXPECTED } from './fixtures.js';

test('context carries project and bridge identity', () => {
    const ctx = buildAiContext(PROJECT_FIXTURE);
    assert.equal(ctx.project.name, 'Kosi Crossing');
    assert.equal(ctx.project.currency, 'INR');
    assert.equal(ctx.bridge.span_m, 240);
    assert.equal(ctx.bridge.analysis_period_years, 50);
});

test('pillar and lifetime totals match lifecycleSummary arithmetic', () => {
    const ctx = buildAiContext(PROJECT_FIXTURE);
    assert.equal(ctx.results.pillar_totals.economic, EXPECTED.eco);
    assert.equal(ctx.results.pillar_totals.environmental, EXPECTED.env);
    assert.equal(ctx.results.pillar_totals.social, EXPECTED.social);
    assert.equal(ctx.results.lifetime_total, EXPECTED.lifetime);
});

test('top cost items are labelled with the display vocabulary and sorted', () => {
    const ctx = buildAiContext(PROJECT_FIXTURE);
    const top = ctx.results.top_cost_items[0];
    assert.equal(top.label, 'Construction Cost');
    assert.equal(top.stage, 'Initial Stage Costs');
    assert.equal(top.value, 90_000_000);
    const values = ctx.results.top_cost_items.map((item) => item.value);
    assert.deepEqual(values, [...values].sort((a, b) => b - a));
});

test('scrap value appears as a negative credit, never a cost', () => {
    const ctx = buildAiContext(PROJECT_FIXTURE);
    const scrap = ctx.results.credits.find((item) => item.label === 'Scrap Value Credit');
    assert.ok(scrap, 'scrap credit missing');
    assert.equal(scrap.value, -2_000_000);
    assert.ok(!ctx.results.top_cost_items.slice(0, 5).some((i) => i.label === 'Scrap Value Credit'));
});

test('uncalculated project yields results: null but keeps identity and validation', () => {
    const ctx = buildAiContext(UNCALCULATED_PROJECT);
    assert.equal(ctx.results, null);
    assert.equal(ctx.project.name, 'Kosi Crossing');
    assert.deepEqual(ctx.validation.errors, []);
});

test('validation messages are carried through, bounded', () => {
    const noisy = {
        ...PROJECT_FIXTURE,
        outputs_data: {
            ...PROJECT_FIXTURE.outputs_data,
            validation: { errors: Array.from({ length: 30 }, (_, i) => `e${i}`), warnings: [] },
        },
    };
    const ctx = buildAiContext(noisy);
    assert.equal(ctx.validation.errors.length, 12);
});

test('formatAmount formats INR in the Indian numbering system', () => {
    const formatted = formatAmount(90_000_000, 'INR');
    assert.match(formatted, /9,00,00,000/);
    assert.equal(formatAmount(null, 'INR'), '—');
});

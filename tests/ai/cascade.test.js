import assert from 'node:assert/strict';
import test from 'node:test';

import { runPrompt, resolve } from '../../src/lib/ai/router.js';
import { buildAiContext } from '../../src/lib/ai/tools/context.js';
import { PROJECT_FIXTURE } from './fixtures.js';

const context = buildAiContext(PROJECT_FIXTURE);
const prefs = (patch) => ({
    enabled: true, provider: 'gemini', mode: 'cascade', model: '', storage: 'none', proxyUrl: '',
    local: { encoder: true, gemma: false, encoderThreshold: 0.6 },
    ...patch,
});

// Injectable test stages, mirroring the shape cascadeStages() builds.
const okStage = (step, confidence, text = `${step} answered`) => ({
    step,
    threshold: 0.6,
    run: async () => ({ calls: [{ name: 'answer', args: { text } }], confidence }),
});
const lowStage = (step, confidence) => ({
    step,
    threshold: 0.6,
    run: async () => ({
        unparsed: false,
        confidence,
        calls: [{ name: 'answer', args: { text: 'low confidence guess' } }],
    }),
});
const unparsedStage = (step) => ({
    step,
    threshold: 0.6,
    run: async () => ({ unparsed: true, confidence: 0, calls: [{ name: 'answer', args: { text: `${step} declined` } }] }),
});
const errorStage = (step) => ({
    step,
    threshold: 0,
    run: async () => { throw new Error(`${step} exploded with key AIzaBoomBoomBoomBoomBoom123456`); },
});

test('cascade resolve: never degraded, no key needed', () => {
    const r = resolve(prefs({}), '');
    assert.equal(r.effectiveMode, 'cascade');
    assert.equal(r.degraded, false);
    assert.equal(r.local.encoder, true);
    assert.equal(r.local.gemma, false);
    assert.equal(r.local.encoderThreshold, 0.6);
});

test('first confident stage wins and later stages never run', async () => {
    let laterRan = false;
    const spy = { step: 'encoder', threshold: 0.6, run: async () => { laterRan = true; } };
    const outcome = await runPrompt('anything', {
        context,
        prefs: prefs({}),
        stages: [okStage('rules', 1), spy],
    });
    assert.equal(outcome.provider, 'rules');
    assert.equal(outcome.confidence, 1);
    assert.equal(laterRan, false);
    assert.deepEqual(outcome.route, [{ step: 'rules', outcome: 'ok', confidence: 1 }]);
});

test('low confidence falls through to the next tier', async () => {
    const outcome = await runPrompt('anything', {
        context,
        prefs: prefs({}),
        stages: [lowStage('encoder', 0.41), okStage('gemma', undefined, 'gemma answered')],
    });
    assert.equal(outcome.provider, 'gemma');
    assert.deepEqual(outcome.route.map((s) => s.outcome), ['low-confidence', 'ok']);
    assert.equal(outcome.route[0].confidence, 0.41);
    assert.equal(outcome.applied[0].summary, 'gemma answered');
});

test('undefined confidence (generative tier) is accepted when parsed', async () => {
    const outcome = await runPrompt('anything', {
        context,
        prefs: prefs({}),
        stages: [okStage('gemma', undefined)],
    });
    assert.equal(outcome.provider, 'gemma');
    assert.equal(outcome.confidence, undefined);
});

test('a stage error is recorded, redacted, and skipped', async () => {
    const outcome = await runPrompt('anything', {
        context,
        prefs: prefs({}),
        stages: [errorStage('encoder'), okStage('rules', 1)],
    });
    assert.equal(outcome.status, 'success');
    assert.equal(outcome.provider, 'rules');
    assert.equal(outcome.route[0].outcome, 'error');
    assert.ok(outcome.route[0].error.includes('[redacted]'));
    assert.ok(!outcome.route[0].error.includes('AIzaBoomBoomBoomBoomBoom123456'));
});

test('when every tier declines, the last refusal is surfaced with the full route', async () => {
    const outcome = await runPrompt('anything', {
        context,
        prefs: prefs({}),
        stages: [unparsedStage('rules'), unparsedStage('encoder')],
    });
    assert.equal(outcome.status, 'success');
    assert.equal(outcome.applied[0].summary, 'encoder declined');
    assert.deepEqual(outcome.route.map((s) => s.outcome), ['unparsed', 'unparsed']);
});

test('real cascade with defaults: rules answer known phrasings at confidence 1', async () => {
    // No stage override: uses the real stage builder. The encoder stage exists
    // but must not be reached (and must not download anything) because the
    // rules answer first.
    const outcome = await runPrompt('What is the total life-cycle cost?', {
        context,
        prefs: prefs({}),
    });
    assert.equal(outcome.provider, 'rules');
    assert.equal(outcome.confidence, 1);
    assert.equal(outcome.route.length, 1);
    assert.match(outcome.applied[0].summary, /15,70,00,000/);
});

test('gemma stage only joins the cascade when opted in', () => {
    const without = resolve(prefs({}), '');
    const withGemma = resolve(prefs({ local: { encoder: true, gemma: true, encoderThreshold: 0.6 } }), '');
    assert.equal(without.local.gemma, false);
    assert.equal(withGemma.local.gemma, true);
});

/**
 * The floating assistant's pure logic: the open-request bus, the per-page
 * suggestion chips, and the route-pill presentation helpers. The React frames
 * (AiFab, AiConversation) stay thin shells over these.
 */
import assert from 'node:assert/strict';
import test from 'node:test';

import { openAssistant, onAssistantOpen } from '../../src/gui/components/ai/assistantBus.js';
import { chipsForPage, GENERAL_CHIPS, RESULTS_CHIPS } from '../../src/gui/components/ai/pageChips.js';
import { pillLabel, tierColor, TIER_COLORS } from '../../src/gui/components/ai/routePills.js';

test('assistant bus delivers open requests to every subscriber', () => {
    let calls = 0;
    const unsubA = onAssistantOpen(() => { calls += 1; });
    const unsubB = onAssistantOpen(() => { calls += 10; });
    openAssistant();
    assert.equal(calls, 11);
    unsubA();
    openAssistant();
    assert.equal(calls, 21);
    unsubB();
    openAssistant();
    assert.equal(calls, 21, 'unsubscribed listeners must not fire');
});

test('assistant bus survives a listener unsubscribing mid-dispatch', () => {
    const seen = [];
    const unsubs = [];
    unsubs.push(onAssistantOpen(() => { seen.push('a'); unsubs.forEach((u) => u()); }));
    unsubs.push(onAssistantOpen(() => { seen.push('b'); }));
    openAssistant(); // iterates a snapshot, so 'b' still fires this round
    openAssistant(); // everyone is gone now
    assert.deepEqual(seen, ['a', 'b']);
});

test('chips follow the page the user is looking at', () => {
    assert.ok(chipsForPage('Bridge Data').includes('What is the span of the bridge?'));
    assert.ok(chipsForPage('Financial Data').includes('What discount rate did we use?'));
    assert.ok(chipsForPage('Traffic Data').includes('What is the traffic growth?'));
    assert.ok(chipsForPage('Foundation').includes('What was the type of cement used?'));
    assert.ok(chipsForPage('Super Structure').includes('How much steel reinforcement is there?'));
    assert.ok(chipsForPage('Demolition').includes('What is the demolition cost percentage?'));
    assert.equal(chipsForPage('Results'), RESULTS_CHIPS);
    assert.equal(chipsForPage('Outputs'), RESULTS_CHIPS);
});

test('unknown, empty, and emissions pages fall back to the general chips', () => {
    assert.equal(chipsForPage('General Information'), GENERAL_CHIPS);
    assert.equal(chipsForPage(undefined), GENERAL_CHIPS);
    // 'Traffic Rerouting Emissions' must NOT get the traffic-count chips.
    assert.equal(chipsForPage('Traffic Rerouting Emissions'), GENERAL_CHIPS);
});

test('pill labels state outcome and confidence honestly', () => {
    assert.equal(pillLabel({ step: 'rules', outcome: 'ok', confidence: 1 }), 'rules 100%');
    assert.equal(pillLabel({ step: 'encoder', outcome: 'low-confidence', confidence: 0.41 }), 'encoder: 41% < threshold');
    assert.equal(pillLabel({ step: 'rules', outcome: 'unparsed' }), 'rules: no match');
    assert.equal(pillLabel({ step: 'gemma', outcome: 'error' }), 'gemma: failed');
});

test('badge tint follows the tier that actually answered', () => {
    assert.equal(tierColor([{ step: 'rules', outcome: 'ok' }]), TIER_COLORS.rules);
    assert.equal(
        tierColor([{ step: 'rules', outcome: 'unparsed' }, { step: 'encoder', outcome: 'ok' }]),
        TIER_COLORS.encoder,
    );
    assert.equal(
        tierColor([{ step: 'rules', outcome: 'unparsed' }, { step: 'gemini', outcome: 'ok' }]),
        TIER_COLORS.generative,
    );
    assert.equal(tierColor([{ step: 'encoder', outcome: 'low-confidence' }]), null);
    assert.equal(tierColor(undefined), null);
});

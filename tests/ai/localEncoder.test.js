import assert from 'node:assert/strict';
import test from 'node:test';

import { createMatcher, generate } from '../../src/lib/ai/providers/localEncoder.js';
import { intentExamples } from '../../src/lib/ai/tools/intents.js';
import { buildAiContext } from '../../src/lib/ai/tools/context.js';
import { PROJECT_FIXTURE } from './fixtures.js';

const context = buildAiContext(PROJECT_FIXTURE);

/**
 * Fake embedder: deterministic bag-of-words vectors over a tiny vocabulary,
 * L2-normalised — enough to make paraphrases land near their intent examples
 * without any model. Injected through the provider's public options.
 */
const VOCAB = ['total', 'cost', 'lifetime', 'money', 'go', 'driver', 'expensive',
    'stage', 'pillar', 'carbon', 'warning', 'error', 'summary', 'overview',
    'engine', 'version', 'set', 'change', 'discount', 'project', 'bridge'];

const fakeEmbed = async (texts) => texts.map((text) => {
    const lower = text.toLowerCase();
    const vector = VOCAB.map((word) => (lower.includes(word) ? 1 : 0));
    const norm = Math.hypot(...vector) || 1;
    return vector.map((v) => v / norm);
});

test('intent examples exist for every intent and are non-trivial', () => {
    const examples = intentExamples();
    assert.ok(examples.length >= 30, `only ${examples.length} examples`);
    for (const { text } of examples) assert.ok(text.length > 8);
});

test('matcher returns the best candidate of each type', async () => {
    const match = createMatcher(fakeEmbed);
    const { bestIntent, bestEntry } = await match('what is the total lifetime cost');
    assert.equal(bestIntent.intent, 'total');
    assert.ok(bestIntent.score > 0.5);
    assert.ok(bestIntent.example);
    assert.ok('score' in bestEntry);
});

test('provider answers through the shared intent handlers when confident', async () => {
    // Entry gate raised above any bag-of-words entry score so the test
    // exercises the intent path (grounded entries win ties by design).
    const result = await generate('what is the total lifetime cost of the project', {
        context,
        embedder: fakeEmbed,
        threshold: 0.75,
        intentThreshold: 0.5,
    });
    assert.ok(!result.unparsed);
    assert.equal(result.intent, 'total');
    assert.ok(result.confidence > 0.5);
    assert.match(result.calls[0].args.text, /15,70,00,000/);
});

test('below the gates it refuses instead of guessing', async () => {
    const result = await generate('purple monkey dishwasher', {
        context,
        embedder: fakeEmbed,
        threshold: 0.5,
        intentThreshold: 0.5,
    });
    assert.equal(result.unparsed, true);
    assert.ok(result.confidence < 0.5);
    assert.match(result.calls[0].args.text, /below its 50% confidence threshold/);
});

test('edit-shaped phrasings land on the refusal intent, not a read intent', async () => {
    // The bag-of-words fake embedder matches on word overlap only, so the
    // prompt targets the refusal examples unambiguously. (Truly ambiguous
    // edit phrasings are guarded by the rules tier, which runs BEFORE the
    // encoder in every cascade — see rules.js pattern order.)
    const result = await generate('please change everything now', {
        context,
        embedder: fakeEmbed,
        threshold: 0.4,
        intentThreshold: 0.4,
    });
    assert.ok(!result.unparsed);
    assert.equal(result.intent, 'edit_refusal');
    assert.match(result.calls[0].args.text, /read-only/);
});

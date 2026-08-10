import assert from 'node:assert/strict';
import test from 'node:test';

import { resolve, providerStatus, runPrompt, MODES } from '../../src/lib/ai/router.js';
import { registerProvider } from '../../src/lib/ai/providers/registry.js';
import { buildAiContext } from '../../src/lib/ai/tools/context.js';
import { PROJECT_FIXTURE } from './fixtures.js';

const context = buildAiContext(PROJECT_FIXTURE);
const prefs = (patch) => ({
    enabled: true, provider: 'gemini', mode: 'rules', model: '', storage: 'none', proxyUrl: '',
    ...patch,
});

// Test doubles registered through the public extension point — the same one
// community providers use.
registerProvider('fake-ok', {
    label: 'Fake OK',
    module: {
        DEFAULT_MODEL: 'fake-1',
        generate: async () => ({ calls: [{ name: 'answer', args: { text: 'model says hi' } }], model: 'fake-1' }),
    },
});
registerProvider('fake-boom', {
    label: 'Fake Boom',
    module: {
        DEFAULT_MODEL: 'boom-1',
        generate: async () => { throw new Error('provider exploded: key sk-ant-abcdefghijklmnopqrstuvwx'); },
    },
});

test('all five modes exist', () => {
    assert.deepEqual(
        Object.keys(MODES).sort(),
        ['cascade', 'model', 'model-first', 'rules', 'rules-first'],
    );
});

test('a model mode with no key and no proxy degrades to rules', () => {
    const r = resolve(prefs({ mode: 'model' }), '');
    assert.equal(r.effectiveMode, 'rules');
    assert.equal(r.degraded, true);
});

test('a key or a proxy URL each make model modes usable', () => {
    assert.equal(resolve(prefs({ mode: 'model' }), 'some-key-1234567890').degraded, false);
    const viaProxy = resolve(prefs({ mode: 'model', proxyUrl: 'https://ai.example.org/x' }), '');
    assert.equal(viaProxy.degraded, false);
    assert.equal(viaProxy.via, 'proxy');
});

test('providerStatus never exposes the key, only a fingerprint', () => {
    const status = providerStatus(prefs({ mode: 'model' }), 'AIzaSecretSecretSecret1234');
    const serialized = JSON.stringify(status);
    assert.ok(!serialized.includes('AIzaSecretSecretSecret1234'));
    assert.equal(status.keyFingerprint, '••••1234');
    assert.equal(status.hasKey, true);
});

test('rules mode answers locally with a single-hop route at confidence 1', async () => {
    const outcome = await runPrompt('What is the total cost?', { context, prefs: prefs({}) });
    assert.equal(outcome.status, 'success');
    assert.equal(outcome.provider, 'rules');
    assert.deepEqual(outcome.route, [{ step: 'rules', outcome: 'ok', confidence: 1 }]);
    assert.equal(outcome.confidence, 1);
    assert.equal(outcome.applied.length, 1);
    assert.equal(outcome.applied[0].readOnly, true);
});

test('rules-first stays local when the rules match — no model call spent', async () => {
    const outcome = await runPrompt('What is the total cost?', {
        context,
        prefs: prefs({ mode: 'rules-first', provider: 'fake-ok' }),
        apiKey: 'irrelevant-key-123',
    });
    assert.equal(outcome.provider, 'rules');
    assert.equal(outcome.route.length, 1);
});

test('rules-first escalates to the model only on unparsed', async () => {
    const outcome = await runPrompt('Would stakeholders find this palatable?', {
        context,
        prefs: prefs({ mode: 'rules-first', provider: 'fake-ok' }),
        apiKey: 'irrelevant-key-123',
    });
    assert.equal(outcome.provider, 'fake-ok');
    assert.deepEqual(outcome.route.map((s) => s.outcome), ['unparsed', 'ok']);
    assert.equal(outcome.applied[0].summary, 'model says hi');
});

test('model-first falls back to rules when the provider throws, and redacts the error', async () => {
    const outcome = await runPrompt('What is the total cost?', {
        context,
        prefs: prefs({ mode: 'model-first', provider: 'fake-boom' }),
        apiKey: 'irrelevant-key-123',
    });
    assert.equal(outcome.status, 'success');
    assert.equal(outcome.provider, 'rules');
    assert.deepEqual(outcome.route.map((s) => s.outcome), ['error', 'ok']);
    const routeError = outcome.route[0].error;
    assert.ok(routeError.includes('[redacted]'), routeError);
    assert.ok(!routeError.includes('sk-ant-abcdefghijklmnopqrstuvwx'));
});

test('a degraded model mode still answers via rules', async () => {
    const outcome = await runPrompt('What is the total cost?', {
        context,
        prefs: prefs({ mode: 'model' }),
        apiKey: '',
    });
    assert.equal(outcome.status, 'success');
    assert.equal(outcome.degraded, true);
    assert.equal(outcome.provider, 'rules');
});

test('unknown tool calls from a provider are rejected, not executed', async () => {
    registerProvider('fake-rogue', {
        label: 'Rogue',
        module: {
            generate: async () => ({
                calls: [
                    { name: 'delete_everything', args: {} },
                    { name: 'answer', args: { text: 'legit part' } },
                ],
            }),
        },
    });
    const outcome = await runPrompt('anything at all please', {
        context,
        prefs: prefs({ mode: 'model', provider: 'fake-rogue' }),
        apiKey: 'irrelevant-key-123',
    });
    assert.equal(outcome.rejected.length, 1);
    assert.match(outcome.rejected[0].error, /read-only/);
    assert.equal(outcome.applied.length, 1);
    assert.equal(outcome.applied[0].summary, 'legit part');
});

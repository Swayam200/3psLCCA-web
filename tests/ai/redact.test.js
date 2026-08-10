import assert from 'node:assert/strict';
import test from 'node:test';

import { redact, providerError, fingerprint } from '../../src/lib/ai/redact.js';

test('redacts known provider key shapes', () => {
    for (const key of [
        'AIzaSyD-abcdefghijklmnopqrstuvwxyz123',
        'sk-ant-api03-abcdefghijklmnopqrstuvwx',
        'sk-abcdefghijklmnopqrstuvwxyz123456',
    ]) {
        assert.ok(!redact(`error with ${key} inside`).includes(key));
    }
});

test('redacts exact extra secrets even when oddly shaped', () => {
    const out = redact('the key short-key-99 leaked', 'short-key-99');
    assert.ok(!out.includes('short-key-99'));
    assert.ok(out.includes('[redacted]'));
});

test('leaves ordinary text alone', () => {
    const text = 'Calculation failed: span must be positive.';
    assert.equal(redact(text), text);
});

test('providerError extracts the human message from Gemini-shaped JSON', () => {
    const body = JSON.stringify({ error: { code: 400, message: 'API key not valid.', status: 'INVALID_ARGUMENT' } });
    assert.equal(providerError('Gemini API', 400, body), 'Gemini API 400: API key not valid.');
});

test('providerError truncates unrecognised bodies and redacts keys in them', () => {
    const body = `${'x'.repeat(300)} AIzaLeakyLeakyLeakyLeakyLeaky123`;
    const out = providerError('X API', 500, body);
    assert.ok(out.length < 300);
    assert.ok(!out.includes('AIzaLeaky'));
});

test('fingerprint shows at most the last 4 characters', () => {
    assert.equal(fingerprint('AIzaSomethingLong1234'), '••••1234');
    assert.equal(fingerprint('abc'), '••••');
    assert.equal(fingerprint(''), null);
});

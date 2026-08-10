import assert from 'node:assert/strict';
import test from 'node:test';

// settings.js reads window.localStorage / window.sessionStorage lazily, so a
// stub installed before import time is all it needs to run under Node.
const makeStorage = () => {
    const map = new Map();
    return {
        getItem: (k) => (map.has(k) ? map.get(k) : null),
        setItem: (k, v) => map.set(k, String(v)),
        removeItem: (k) => map.delete(k),
        _dump: () => Object.fromEntries(map),
    };
};

globalThis.window = { localStorage: makeStorage(), sessionStorage: makeStorage() };

const {
    loadPrefs, savePrefs, loadKey, saveKey, clearKey, maskKey, DEFAULT_PREFS,
} = await import('../../src/lib/ai/settings.js');

const SECRET = '3pslcca.ai.key';

test('prefs default sensibly: disabled, rules mode, session storage', () => {
    const prefs = loadPrefs();
    assert.equal(prefs.enabled, false);
    assert.equal(prefs.mode, 'rules');
    assert.equal(prefs.storage, 'session');
});

test('savePrefs merges patches over stored values', () => {
    savePrefs({ mode: 'rules-first' });
    savePrefs({ provider: 'claude' });
    const prefs = loadPrefs();
    assert.equal(prefs.mode, 'rules-first');
    assert.equal(prefs.provider, 'claude');
    assert.equal(prefs.enabled, DEFAULT_PREFS.enabled);
});

test('the key lives in exactly one store, and switching policy moves it', () => {
    saveKey('my-test-key-123', 'local');
    assert.equal(window.localStorage.getItem(SECRET), 'my-test-key-123');
    assert.equal(window.sessionStorage.getItem(SECRET), null);

    saveKey('my-test-key-123', 'session');
    assert.equal(window.localStorage.getItem(SECRET), null);
    assert.equal(window.sessionStorage.getItem(SECRET), 'my-test-key-123');
});

test('storage policy "none" keeps the key in memory only', () => {
    saveKey('memory-only-key-1', 'none');
    assert.equal(window.localStorage.getItem(SECRET), null);
    assert.equal(window.sessionStorage.getItem(SECRET), null);
    assert.equal(loadKey(), 'memory-only-key-1');
});

test('clearKey removes every copy', () => {
    saveKey('doomed-key-12345', 'local');
    clearKey();
    assert.equal(loadKey(), '');
    assert.equal(window.localStorage.getItem(SECRET), null);
    assert.equal(window.sessionStorage.getItem(SECRET), null);
});

test('prefs never contain the key', () => {
    saveKey('sneaky-key-99999', 'local');
    savePrefs({ mode: 'model' });
    const rawPrefs = window.localStorage.getItem('3pslcca.ai.prefs');
    assert.ok(!rawPrefs.includes('sneaky-key-99999'));
    clearKey();
});

test('a threshold stored for a different encoder model is discarded', async () => {
    const { ENCODER_MODEL_ID, DEFAULT_ENCODER_THRESHOLD } = await import('../../src/lib/ai/providers/localEncoder.js');

    // Simulate prefs saved while the old MiniLM encoder was current.
    window.localStorage.setItem('3pslcca.ai.prefs', JSON.stringify({
        mode: 'cascade',
        local: { encoder: true, encoderThreshold: 0.6, encoderModel: 'Xenova/all-MiniLM-L6-v2' },
    }));
    const migrated = loadPrefs();
    assert.equal(migrated.local.encoderThreshold, DEFAULT_ENCODER_THRESHOLD);
    assert.equal(migrated.local.encoderModel, ENCODER_MODEL_ID);
    assert.equal(migrated.mode, 'cascade');           // everything else survives
    assert.equal(migrated.local.encoder, true);

    // A threshold stored FOR the current model is the user's choice — kept.
    window.localStorage.setItem('3pslcca.ai.prefs', JSON.stringify({
        local: { encoderThreshold: 0.9, encoderModel: ENCODER_MODEL_ID },
    }));
    assert.equal(loadPrefs().local.encoderThreshold, 0.9);
    window.localStorage.removeItem('3pslcca.ai.prefs');
});

test('maskKey shows at most the last 4 characters', () => {
    assert.equal(maskKey('AIzaWhatever5678'), '••••5678');
    assert.equal(maskKey(''), '');
});

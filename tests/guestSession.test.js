/**
 * Guest auto-resume marker: a returning guest lands on the home page, not the
 * auth page. The marker must round-trip, reject junk, and never throw when
 * storage is absent (node) or hostile (quota/security errors).
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import { loadGuestSession, saveGuestSession, clearGuestSession } from '../src/lib/guestSession.js';

const stubStorage = () => {
    const map = new Map();
    globalThis.localStorage = {
        getItem: (key) => (map.has(key) ? map.get(key) : null),
        setItem: (key, value) => map.set(key, String(value)),
        removeItem: (key) => map.delete(key),
    };
    return () => { delete globalThis.localStorage; };
};

test('guest session round-trips through save/load/clear', () => {
    const restore = stubStorage();
    try {
        assert.equal(loadGuestSession(), null);
        saveGuestSession('Swayam');
        const session = loadGuestSession();
        assert.equal(session.name, 'Swayam');
        assert.ok(session.savedAt, 'savedAt timestamp recorded');
        clearGuestSession();
        assert.equal(loadGuestSession(), null);
    } finally {
        restore();
    }
});

test('blank names are not saved; corrupt entries load as null', () => {
    const restore = stubStorage();
    try {
        saveGuestSession('   ');
        assert.equal(loadGuestSession(), null);
        globalThis.localStorage.setItem('3pslcca.guestSession', '{not json');
        assert.equal(loadGuestSession(), null);
        globalThis.localStorage.setItem('3pslcca.guestSession', JSON.stringify({ nope: true }));
        assert.equal(loadGuestSession(), null);
    } finally {
        restore();
    }
});

test('no localStorage at all (plain node) is silently a no-op', () => {
    assert.equal(loadGuestSession(), null);
    saveGuestSession('Ghost');
    clearGuestSession();
});

test('a throwing storage backend never crashes the app shell', () => {
    globalThis.localStorage = {
        getItem: () => { throw new Error('SecurityError'); },
        setItem: () => { throw new Error('QuotaExceededError'); },
        removeItem: () => { throw new Error('SecurityError'); },
    };
    try {
        assert.equal(loadGuestSession(), null);
        saveGuestSession('Swayam');
        clearGuestSession();
    } finally {
        delete globalThis.localStorage;
    }
});

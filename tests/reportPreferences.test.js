import test from 'node:test';
import assert from 'node:assert/strict';
import {
    STORAGE_KEY, DEFAULT_PREFERENCES, REPORT_HTML, REPORT_LATEX,
    readReportPreferences, writeReportPreferences, effectivePrimaryReport,
    deviceMemoryGb, isLowMemoryDevice,
} from '../src/utils/reportPreferences.js';

const memoryStorage = () => {
    const map = new Map();
    return {
        getItem: (k) => (map.has(k) ? map.get(k) : null),
        setItem: (k, v) => map.set(k, String(v)),
        removeItem: (k) => map.delete(k),
    };
};

test('defaults: standard report primary, desktop PDF off', () => {
    const prefs = readReportPreferences(memoryStorage());
    assert.deepEqual(prefs, { ...DEFAULT_PREFERENCES });
    assert.equal(effectivePrimaryReport(prefs), REPORT_HTML);
});

test('enabling the desktop PDF and making it primary round-trips through storage', () => {
    const storage = memoryStorage();
    const events = [];
    const target = { dispatchEvent: (e) => events.push(e.type) };
    writeReportPreferences({ desktopPdfEnabled: true }, storage, target);
    writeReportPreferences({ primaryReport: REPORT_LATEX }, storage, target);
    const prefs = readReportPreferences(storage);
    assert.equal(prefs.desktopPdfEnabled, true);
    assert.equal(prefs.primaryReport, REPORT_LATEX);
    assert.equal(effectivePrimaryReport(prefs), REPORT_LATEX);
    assert.equal(events.length, 2);
    assert.equal(JSON.parse(storage.getItem(STORAGE_KEY)).primaryReport, REPORT_LATEX);
});

test('the desktop PDF cannot stay primary once it is disabled', () => {
    const storage = memoryStorage();
    writeReportPreferences({ desktopPdfEnabled: true, primaryReport: REPORT_LATEX }, storage, null);
    writeReportPreferences({ desktopPdfEnabled: false }, storage, null);
    const prefs = readReportPreferences(storage);
    assert.equal(prefs.primaryReport, REPORT_HTML);
    assert.equal(effectivePrimaryReport(prefs), REPORT_HTML);
});

test('corrupt or foreign stored values fall back to the defaults', () => {
    const storage = memoryStorage();
    storage.setItem(STORAGE_KEY, '{not json');
    assert.deepEqual(readReportPreferences(storage), { ...DEFAULT_PREFERENCES });
    storage.setItem(STORAGE_KEY, JSON.stringify({ desktopPdfEnabled: 'yes', primaryReport: 'pdf' }));
    assert.deepEqual(readReportPreferences(storage), { ...DEFAULT_PREFERENCES });
    assert.deepEqual(readReportPreferences(null), { ...DEFAULT_PREFERENCES });
});

test('low-memory detection uses navigator.deviceMemory and treats unknown as not low', () => {
    assert.equal(deviceMemoryGb({ deviceMemory: 4 }), 4);
    assert.equal(deviceMemoryGb({}), null);
    assert.equal(deviceMemoryGb(undefined), null);
    assert.equal(isLowMemoryDevice({ deviceMemory: 4 }), true);
    assert.equal(isLowMemoryDevice({ deviceMemory: 2 }), true);
    assert.equal(isLowMemoryDevice({ deviceMemory: 8 }), false);
    assert.equal(isLowMemoryDevice({}), false);
});

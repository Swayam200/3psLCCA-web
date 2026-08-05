import test from 'node:test';
import assert from 'node:assert/strict';

import {
  __setBrowserEngineLoaderForTests,
  calculateLcca,
  validateLcca,
  getLccaEngineMode,
  initializeLccaEngine,
} from '../src/lib/lccaApi.js';

const SUCCESS = { status: 'success', results: { ok: true }, computed: {}, validation: { errors: [], warnings: [] } };

const workingEngine = (log = []) => ({
  initializeBrowserEngine: async (onStatus) => {
    onStatus?.('Booting Pyodide runtime...');
    log.push('init');
    return { status: 'ready', engineVersion: '1.0.0', pyodideVersion: '314.0.2' };
  },
  calculateLcca: async () => { log.push('calculate'); return SUCCESS; },
  validateLcca: async () => { log.push('validate'); return SUCCESS; },
});

const brokenEngine = () => ({
  initializeBrowserEngine: async () => { throw new Error('CDN unreachable'); },
  calculateLcca: async () => { throw new Error('CDN unreachable'); },
  validateLcca: async () => { throw new Error('CDN unreachable'); },
});

const stubBackend = (t) => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    return { ok: true, json: async () => ({ ...SUCCESS, from: 'backend' }) };
  };
  t.after(() => { delete globalThis.fetch; });
  return calls;
};

test('browser engine is the default and handles the whole flow', async () => {
  const log = [];
  __setBrowserEngineLoaderForTests(async () => workingEngine(log));

  assert.equal(getLccaEngineMode(), 'browser');
  const init = await initializeLccaEngine();
  assert.equal(init.engineVersion, '1.0.0');

  const result = await calculateLcca({ project: {}, analysisPeriodYears: 50 });
  assert.equal(result.status, 'success');
  await validateLcca({ project: {}, analysisPeriodYears: 50 });

  assert.deepEqual(log, ['init', 'calculate', 'validate']);
  assert.equal(getLccaEngineMode(), 'browser');
});

test('a broken browser engine falls back to the backend for the session', async (t) => {
  const backendCalls = stubBackend(t);
  __setBrowserEngineLoaderForTests(async () => brokenEngine());

  const statuses = [];
  const result = await calculateLcca({
    project: { name: 'p' },
    analysisPeriodYears: 50,
    onStatus: (message) => statuses.push(message),
  });

  assert.equal(result.from, 'backend');
  assert.equal(getLccaEngineMode(), 'backend', 'mode sticks to backend after the fallback');
  assert.ok(statuses.some((message) => message.includes('switching to the calculation backend')));
  assert.equal(backendCalls[0].url, 'http://localhost:8000/api/lcca/calculate');
  assert.deepEqual(backendCalls[0].body, { project: { name: 'p' }, analysis_period_years: 50, debug: false });

  // Later calls go straight to the backend without retrying the browser engine.
  await validateLcca({ project: {}, analysisPeriodYears: 50 });
  assert.equal(backendCalls.length, 2);
});

test('an engine loader that itself fails to import also falls back', async (t) => {
  const backendCalls = stubBackend(t);
  __setBrowserEngineLoaderForTests(async () => { throw new Error('import failed'); });

  const init = await initializeLccaEngine();
  assert.equal(init.status, 'ready');
  assert.equal(getLccaEngineMode(), 'backend');

  await calculateLcca({ project: {}, analysisPeriodYears: 50 });
  assert.equal(backendCalls.length, 1);
});

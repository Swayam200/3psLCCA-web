import test from 'node:test';
import assert from 'node:assert/strict';

import {
  getEngineUrl,
  getPyodideUrl,
  initializeCdnEngine,
  isCdnEngineReady,
  getCdnEngineState,
  resetCdnEngine,
} from '../src/lib/lccaEngine/cdnEngine.js';

/**
 * Minimal DOM stub: records which script URLs were requested and fires
 * load/error depending on `failUrls`.
 */
const installFakeDom = ({ failUrls = [] } = {}) => {
  const requested = [];
  const scripts = [];

  globalThis.document = {
    querySelector: (selector) => scripts.find(
      (script) => selector === `script[data-lcca-src="${script.dataset.lccaSrc}"]`,
    ) || null,
    createElement: () => {
      const listeners = {};
      return {
        dataset: {},
        addEventListener: (type, handler) => {
          listeners[type] = handler;
        },
        _fire: (type) => listeners[type]?.(),
      };
    },
    head: {
      appendChild: (script) => {
        scripts.push(script);
        requested.push(script.src);
        setImmediate(() => script._fire(failUrls.includes(script.src) ? 'error' : 'load'));
      },
    },
  };

  return { requested };
};

const installFakeEngine = ({ initError } = {}) => {
  let ready = false;
  globalThis.ThreePsLccaCore = {
    init: async (onStatus) => {
      onStatus?.('Booting Pyodide runtime...');
      if (initError) throw new Error(initError);
      ready = true;
      return { pyodideFake: true };
    },
    getState: () => ({
      stage: ready ? 'ready' : 'idle',
      packageVersion: '1.0.0',
      pyodideVersion: '314.0.2',
    }),
    isReady: () => ready,
  };
};

const cleanup = () => {
  resetCdnEngine();
  delete globalThis.document;
  delete globalThis.ThreePsLccaCore;
};

test('engine URLs default to the published upstream release', () => {
  assert.match(getEngineUrl(), /^https:\/\/3pslcca\.github\.io\/3psLCCA-core\/release\/v\d+\.\d+\.\d+\/3pslccacore\.js$/);
  assert.match(getPyodideUrl(), /^https:\/\/cdn\.jsdelivr\.net\/pyodide\/v[\d.]+\/full\/pyodide\.js$/);
});

test('initialising loads pyodide then the engine, and reports versions', async (t) => {
  t.after(cleanup);
  const { requested } = installFakeDom();
  installFakeEngine();

  const stages = [];
  const result = await initializeCdnEngine((message) => stages.push(message));

  assert.deepEqual(requested, [getPyodideUrl(), getEngineUrl()]);
  assert.equal(result.status, 'ready');
  assert.equal(result.engineVersion, '1.0.0');
  assert.equal(result.pyodideVersion, '314.0.2');
  assert.ok(stages.includes('Booting Pyodide runtime...'), 'engine stage messages reach the caller');
  assert.equal(isCdnEngineReady(), true);
  assert.equal(getCdnEngineState().stage, 'ready');
});

test('initialising twice reuses the first load', async (t) => {
  t.after(cleanup);
  const { requested } = installFakeDom();
  installFakeEngine();

  await initializeCdnEngine();
  await initializeCdnEngine();

  assert.equal(requested.length, 2, 'scripts are injected only once');
});

test('a failed script load is reported and can be retried', async (t) => {
  t.after(cleanup);
  installFakeDom({ failUrls: [getEngineUrl()] });
  installFakeEngine();

  await assert.rejects(
    () => initializeCdnEngine(),
    /Failed to load .*3pslccacore\.js/,
  );

  // The failure must not be cached: a retry (now with the CDN reachable)
  // has to be able to succeed.
  const { requested } = installFakeDom();
  const result = await initializeCdnEngine();
  assert.equal(result.status, 'ready');
  assert.deepEqual(requested, [getPyodideUrl(), getEngineUrl()]);
});

test('an engine that fails to initialise surfaces the error and can be retried', async (t) => {
  t.after(cleanup);
  installFakeDom();
  installFakeEngine({ initError: 'micropip failed to install the wheel' });

  await assert.rejects(() => initializeCdnEngine(), /micropip failed to install the wheel/);
  assert.equal(isCdnEngineReady(), false);

  installFakeEngine();
  const result = await initializeCdnEngine();
  assert.equal(result.status, 'ready');
});

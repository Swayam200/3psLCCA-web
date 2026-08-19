/**
 * SwiftLaTeX report compilation Web Worker.
 *
 * Receives a LaTeX document string via postMessage, compiles it to PDF using
 * the SwiftLaTeX PdfTeX WebAssembly engine, and returns the PDF bytes.
 *
 * The engine and its compiled format are built once and kept for the
 * worker's lifetime: repeat compiles skip the ~5 s format stage entirely,
 * and because the engine also retains the cross-reference files
 * (.aux/.toc/.lof/.lot) from the previous run, repeat reports usually
 * converge in a single compile pass (see the rerun-until-stable loop).
 *
 * Messages:
 *   { type: 'prepare', swiftlatexBase?, texliveEndpoint? }
 *     → warms the engine + format; replies { type: 'prepared' } (errors are
 *       silent — a later compile surfaces them properly).
 *   { type: 'compile-latex', tex, assets?, passes?, swiftlatexBase?, ... }
 *     → { type: 'success', pdf, ... } | { type: 'error', ... }
 *
 * TeX Live assets are fetched from the static vendor directory under the
 * configured texliveEndpoint — no external server or CDN is required.
 */
/* global importScripts, PdfTeXEngine */

const DEFAULT_SWIFTLATEX_BASE = './vendor/swiftlatex/';
const REMOTE_TEXLIVE_ENDPOINT = 'https://texlive2.swiftlatex.com/';

const post = (type, payload = {}) => {
  self.postMessage({ type, ...payload });
};

const configureTexliveEndpoint = (engine, endpoint) => {
  if (!endpoint || !engine.latexWorker) return;
  engine.latexWorker.postMessage({ cmd: 'settexliveurl', url: endpoint });
};

const writeAssets = (engine, assets = {}) => {
  for (const [fileName, content] of Object.entries(assets)) {
    engine.writeMemFSFile(fileName, content);
  }
};

const hasFatalLatexError = (log = '') => (
  /! (LaTeX|Font) Error:/.test(log)
  || /Fatal error occurred/.test(log)
  || /Emergency stop/.test(log)
  || /Undefined control sequence/.test(log)
  || /not loadable: Metric \(TFM\) file not found/.test(log)
);

const resolveEndpoints = (data = {}) => {
  const swiftlatexBase = data.swiftlatexBase || DEFAULT_SWIFTLATEX_BASE;
  const swiftlatexBaseUrl = new URL(swiftlatexBase, self.location.href);
  const texliveMode = data.texliveMode || 'local';
  const texliveEndpoint = texliveMode === 'remote'
    ? REMOTE_TEXLIVE_ENDPOINT
    : (data.texliveEndpoint || new URL('texlive/', swiftlatexBaseUrl).href);
  return { swiftlatexBaseUrl, texliveMode, texliveEndpoint };
};

let enginePromise = null;

/** Load the wasm engine and build the LaTeX format once per worker. */
const getEngine = (data) => {
  if (!enginePromise) {
    enginePromise = (async () => {
      const { swiftlatexBaseUrl, texliveEndpoint } = resolveEndpoints(data);

      post('status', { message: 'Loading SwiftLaTeX report engine...' });
      self.SWIFTLATEX_ENGINE_PATH = new URL('swiftlatexpdftex.js', swiftlatexBaseUrl).href;
      importScripts(new URL('PdfTeXEngine.js', swiftlatexBaseUrl).href);

      const EngineClass = self.PdfTeXEngine || self.exports?.PdfTeXEngine || PdfTeXEngine;
      if (!EngineClass) {
        throw new Error('SwiftLaTeX PdfTeXEngine was not exposed by the vendored script.');
      }

      const engine = new EngineClass();
      await engine.loadEngine();
      configureTexliveEndpoint(engine, texliveEndpoint);

      post('status', { message: 'Preparing static SwiftLaTeX format...' });
      const formatResult = await engine.compileFormat();
      if (formatResult?.status !== 0 || !formatResult?.pdf) {
        const error = new Error('SwiftLaTeX format generation failed.');
        error.latexLog = formatResult?.log || 'SwiftLaTeX did not return a format-generation log.';
        throw error;
      }
      engine.writeMemFSFile('swiftlatexpdftex.fmt', formatResult.pdf);
      return engine;
    })().catch((error) => {
      enginePromise = null;
      throw error;
    });
  }
  return enginePromise;
};

const compile = async (data) => {
  const startedAt = performance.now();
  const { texliveMode, texliveEndpoint } = resolveEndpoints(data);

  try {
    if (!data.tex) {
      throw new Error('A LaTeX document is required.');
    }

    const engine = await getEngine(data);
    writeAssets(engine, data.assets);
    engine.writeMemFSFile('main.tex', data.tex);
    engine.setEngineMainFile('main.tex');

    // Rerun-until-stable, the rule latexmk uses: a pass that leaves the
    // cross-reference files (.aux/.toc/.lof/.lot) unchanged has already
    // resolved the table of contents and "Page n of m" totals. A fresh
    // document converges in two passes; with references retained from an
    // earlier run of the same project it converges in one.
    const maxPasses = Math.max(1, data.passes ?? 3);
    let result;
    let passesRun = 0;
    for (let pass = 1; pass <= maxPasses; pass += 1) {
      post('status', { message: `Compiling LaTeX report PDF (pass ${pass})...` });
      result = await engine.compileLaTeX();
      passesRun = pass;
      if (!result.pdf) break;
      if (result.aux !== undefined && result.aux === result.auxBefore) break;
    }

    const elapsedMs = Math.round(performance.now() - startedAt);
    if (!result.pdf || hasFatalLatexError(result.log || '')) {
      post('error', {
        status: result.status,
        log: result.log || 'No SwiftLaTeX log was returned.',
        elapsedMs,
        texliveMode,
        texliveEndpoint,
        hasPdf: Boolean(result.pdf),
      });
      return;
    }

    post('success', {
      pdf: result.pdf,
      log: result.log || '',
      elapsedMs,
      passesRun,
      texliveMode,
      texliveEndpoint,
      status: result.status,
    });
  } catch (error) {
    post('error', {
      status: -1,
      message: error?.message || String(error),
      log: error?.latexLog || '',
      stack: error?.stack || '',
      texliveMode,
      texliveEndpoint,
    });
  }
};

self.onmessage = async (event) => {
  const data = event.data || {};
  if (data.type === 'prepare') {
    // Opportunistic warm-up (engine download + format build) while the user
    // is still choosing sections; a later compile surfaces real errors.
    try {
      await getEngine(data);
    } catch {
      // Silent by design.
    }
    post('prepared');
    return;
  }
  if (data.type === 'compile-latex') {
    await compile(data);
  }
};

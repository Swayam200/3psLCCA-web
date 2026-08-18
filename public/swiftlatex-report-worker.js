/**
 * SwiftLaTeX report compilation Web Worker.
 *
 * Receives a LaTeX document string via postMessage, compiles it to PDF using
 * the SwiftLaTeX PdfTeX WebAssembly engine, and returns the PDF bytes.
 *
 * Lifecycle:
 *   1. Caller posts { type: 'compile-latex', tex, swiftlatexBase, texliveMode }
 *   2. Worker loads PdfTeXEngine.js and the Wasm binary
 *   3. Compiles the LaTeX format (preamble + packages)
 *   4. Writes main.tex + any assets to the in-memory filesystem
 *   5. Compiles LaTeX → PDF
 *   6. Posts back { type: 'success', pdf } or { type: 'error', log }
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

const closeEngine = (engine) => {
  try {
    engine?.closeWorker?.();
  } catch {
    // Best-effort cleanup only. The outer worker will be terminated by the caller.
  }
};

const hasFatalLatexError = (log = '') => (
  /! (LaTeX|Font) Error:/.test(log)
  || /Fatal error occurred/.test(log)
  || /Emergency stop/.test(log)
  || /Undefined control sequence/.test(log)
  || /not loadable: Metric \(TFM\) file not found/.test(log)
);

self.onmessage = async (event) => {
  if (event.data?.type !== 'compile-latex') return;

  const startedAt = performance.now();
  const swiftlatexBase = event.data.swiftlatexBase || DEFAULT_SWIFTLATEX_BASE;
  const swiftlatexBaseUrl = new URL(swiftlatexBase, self.location.href);
  const texliveMode = event.data.texliveMode || 'local';
  const texliveEndpoint = texliveMode === 'remote'
    ? REMOTE_TEXLIVE_ENDPOINT
    : (event.data.texliveEndpoint || new URL('texlive/', swiftlatexBaseUrl).href);
  let engine;

  try {
    if (!event.data.tex) {
      throw new Error('A LaTeX document is required.');
    }

    post('status', { message: 'Loading SwiftLaTeX report engine...' });
    self.SWIFTLATEX_ENGINE_PATH = new URL('swiftlatexpdftex.js', swiftlatexBaseUrl).href;
    importScripts(new URL('PdfTeXEngine.js', swiftlatexBaseUrl).href);

    const EngineClass = self.PdfTeXEngine || self.exports?.PdfTeXEngine || PdfTeXEngine;
    if (!EngineClass) {
      throw new Error('SwiftLaTeX PdfTeXEngine was not exposed by the vendored script.');
    }

    engine = new EngineClass();
    await engine.loadEngine();
    configureTexliveEndpoint(engine, texliveEndpoint);

    post('status', { message: 'Preparing static SwiftLaTeX format...' });
    const formatResult = await engine.compileFormat();
    if (formatResult?.status !== 0 || !formatResult?.pdf) {
      post('error', {
        status: formatResult?.status ?? 1,
        log: formatResult?.log || 'SwiftLaTeX did not return a format-generation log.',
        texliveMode,
        texliveEndpoint,
      });
      return;
    }
    engine.writeMemFSFile('swiftlatexpdftex.fmt', formatResult.pdf);

    writeAssets(engine, event.data.assets);
    engine.writeMemFSFile('main.tex', event.data.tex);
    engine.setEngineMainFile('main.tex');

    // Two passes by default, like the desktop pipeline: the first pass
    // writes the .aux/.toc into the engine's in-memory filesystem, the
    // second resolves the table of contents, cross-references and
    // "Page n of m" totals.
    const passes = Math.max(1, event.data.passes ?? 2);
    let result;
    for (let pass = 1; pass <= passes; pass += 1) {
      post('status', { message: `Compiling LaTeX report PDF (pass ${pass}/${passes})...` });
      result = await engine.compileLaTeX();
      if (!result.pdf) break;
    }
    closeEngine(engine);

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
      texliveMode,
      texliveEndpoint,
      status: result.status,
    });
  } catch (error) {
    closeEngine(engine);
    post('error', {
      status: -1,
      message: error?.message || String(error),
      stack: error?.stack || '',
      texliveMode,
      texliveEndpoint,
    });
  }
};

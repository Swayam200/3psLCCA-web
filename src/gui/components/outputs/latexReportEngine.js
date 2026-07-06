/**
 * SwiftLaTeX report engine — bridges the report model and LaTeX generator
 * with the SwiftLaTeX Web Worker that compiles the PDF in-browser.
 *
 * Architecture:
 *   projectInputs → buildReportModel() → buildDesktopStyleLatexReport() → tex string
 *   tex string → SwiftLaTeX Web Worker → PDF ArrayBuffer
 *
 * The Web Worker runs SwiftLaTeX's PdfTeX WebAssembly engine and fetches
 * TeX Live assets from the static vendor directory (no server required).
 */
import { buildDesktopStyleLatexReport } from './latexReport.js';
import { buildReportModel } from './reportModel.js';

const DEFAULT_TIMEOUT_MS = 120_000;
const DEFAULT_WORKER_NAME = 'swiftlatex-report-worker.js';
const DEFAULT_SWIFTLATEX_ASSET_ROOT = 'vendor/swiftlatex/';
const DEFAULT_REPORT_FILENAME = 'LCCA_LaTeX_Report.pdf';

/** Resolves the Vite base path (e.g. '/' or '/3pslcca/'). */
const getBasePath = () => import.meta.env?.BASE_URL || '/';

/** Joins a relative asset path onto the Vite base path. */
const joinAssetPath = (basePath, relativePath) => {
  const normalizedBase = basePath.endsWith('/') ? basePath : `${basePath}/`;
  return new URL(relativePath, new URL(normalizedBase, globalThis.location?.origin || 'http://localhost')).pathname;
};

export const buildLatexReportPayload = ({
  projectInputs,
  results = {},
  computedData = {},
  selections = {},
  calculationMetadata = {},
  fileName,
} = {}) => {
  const report = buildReportModel(projectInputs || {}, calculationMetadata);
  const tex = buildDesktopStyleLatexReport({
    report,
    results,
    computedData,
    selections,
  });

  return {
    tex,
    fileName: fileName || DEFAULT_REPORT_FILENAME,
    report,
    engine: 'swiftlatex',
  };
};

export const getSwiftLatexReportEngineConfig = (basePath = getBasePath()) => ({
  workerUrl: joinAssetPath(basePath, DEFAULT_WORKER_NAME),
  swiftlatexBase: joinAssetPath(basePath, DEFAULT_SWIFTLATEX_ASSET_ROOT),
  texliveMode: 'local',
});

export const compileLatexReportPdf = ({
  tex,
  fileName = 'LCCA_LaTeX_Report.pdf',
  assets = {},
  timeoutMs = DEFAULT_TIMEOUT_MS,
  onStatus,
  config = getSwiftLatexReportEngineConfig(),
} = {}) => new Promise((resolve, reject) => {
  if (!tex) {
    reject(new Error('A LaTeX document is required to compile a report PDF.'));
    return;
  }

  if (typeof Worker === 'undefined') {
    reject(new Error('SwiftLaTeX report compilation requires a browser Worker.'));
    return;
  }

  const worker = new Worker(config.workerUrl);
  const timeout = setTimeout(() => {
    worker.terminate();
    reject(new Error(`SwiftLaTeX report compilation timed out after ${timeoutMs} ms.`));
  }, timeoutMs);

  const cleanup = () => {
    clearTimeout(timeout);
    worker.terminate();
  };

  worker.onmessage = (event) => {
    const message = event.data || {};
    if (message.type === 'status') {
      onStatus?.(message.message);
      return;
    }

    if (message.type === 'success') {
      cleanup();
      const arrayBuffer = message.pdf instanceof ArrayBuffer
        ? message.pdf
        : new Uint8Array(message.pdf || []).buffer;
      resolve({
        arrayBuffer,
        blob: new Blob([arrayBuffer], { type: 'application/pdf' }),
        fileName,
        log: message.log || '',
        elapsedMs: message.elapsedMs,
        engine: 'swiftlatex',
        texliveMode: message.texliveMode,
      });
      return;
    }

    if (message.type === 'error') {
      cleanup();
      const error = new Error(message.message || `SwiftLaTeX report compilation failed with status ${message.status}.`);
      error.status = message.status;
      error.log = message.log || '';
      error.hasPdf = message.hasPdf;
      error.stack = message.stack || error.stack;
      reject(error);
    }
  };

  worker.onerror = (event) => {
    cleanup();
    reject(new Error(event.message || 'SwiftLaTeX report worker crashed.'));
  };

  worker.postMessage({
    type: 'compile-latex',
    tex,
    assets,
    swiftlatexBase: config.swiftlatexBase,
    texliveMode: config.texliveMode,
  });
});

export const generateLatexReportPdf = async ({
  projectInputs,
  results,
  computedData,
  selections,
  calculationMetadata,
  fileName,
  onStatus,
  timeoutMs,
} = {}) => {
  const payload = buildLatexReportPayload({
    projectInputs,
    results,
    computedData,
    selections,
    calculationMetadata,
    fileName,
  });

  return compileLatexReportPdf({
    tex: payload.tex,
    fileName: payload.fileName,
    timeoutMs,
    onStatus,
  });
};

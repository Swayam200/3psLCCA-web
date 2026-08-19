/**
 * Desktop-identical LaTeX report pipeline (see docs/report-latex-web-plan.md).
 *
 * Two lazy-loaded workers, both fully client-side:
 *   1. report-worker.js — the desktop app's own Python report modules under
 *      Pyodide turn project chunks into the .tex + plots/logos it references.
 *   2. swiftlatex-report-worker.js — a pdfTeX WebAssembly engine compiles the
 *      .tex to a real PDF (two passes, resolving TOC and page references).
 *
 * Heavy assets (~60 MB total) download on first use only and stay in the
 * browser HTTP cache. Project data never leaves the machine.
 */
import { desktopChunksForReport } from './reportChunks.js';

const baseUrl = () => {
    const base = (typeof import.meta !== 'undefined' && import.meta.env?.BASE_URL) || '/';
    return base.endsWith('/') ? base : `${base}/`;
};

/**
 * Rewrite environment-absolute asset paths in the generated .tex to the bare
 * MemFS names the compile worker writes, and pre-expand the few Unicode
 * characters the template maps via \DeclareUnicodeCharacter — the wasm
 * engine aborts on the raw bytes inside table cells while the expanded
 * macros (what inputenc produces anyway) compile fine.
 */
export const rewriteTexPaths = (tex, names) => {
    let out = tex;
    for (const name of names) {
        const esc = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        out = out.replace(new RegExp(`\\{[^{}]*[/\\\\]${esc}\\}`, 'g'), `{${name}}`);
    }
    return out
        .replace(/₂/g, '\\textsubscript{2}')
        .replace(/₹/g, 'Rs.')
        .replace(/[–—]/g, '--');
};

let texWorkerPromise = null;

/** The Pyodide worker is expensive to boot (~30 MB first use), so one
 * instance is kept for the session; repeat reports reuse it. */
const getTexWorker = () => {
    if (!texWorkerPromise) {
        // Module worker: pyodide v0.28+ no longer supports classic workers.
        texWorkerPromise = Promise.resolve(new Worker(`${baseUrl()}report-worker.js`, { type: 'module' }));
    }
    return texWorkerPromise;
};

/**
 * Map a pipeline progress message onto an overall percentage. The weights
 * reflect measured wall time: downloads and Pyodide boot dominate the first
 * run, the two compile passes dominate warm runs.
 */
const STAGE_MARKS = [
    ['Preparing project data', 2],
    ['Loading Python runtime', 5],
    ['Loading pandas', 25],
    ['Loading report modules', 45],
    ['Generating LaTeX report', 52],
    ['Loading SwiftLaTeX', 58],
    ['Preparing static SwiftLaTeX format', 62],
    ['pass 1)', 70],
    ['pass 2)', 85],
    ['pass 3)', 94],
];

export const progressPercent = (message) => {
    const hit = STAGE_MARKS.find(([needle]) => String(message || '').includes(needle));
    return hit ? hit[1] : null;
};

let latexWorker = null;
let activeCompileProgress = null;

/** The LaTeX engine worker is kept for the session: its compiled format and
 * retained cross-reference files make repeat compiles far cheaper (no
 * format rebuild; usually a single convergent pass). */
const getLatexWorker = () => {
    if (!latexWorker) {
        latexWorker = new Worker(`${baseUrl()}swiftlatex-report-worker.js`);
        latexWorker.addEventListener('message', (event) => {
            if (event.data?.type === 'status') activeCompileProgress?.(event.data.message);
        });
    }
    return latexWorker;
};

const resetLatexWorker = () => {
    try {
        latexWorker?.terminate();
    } catch {
        // Best effort.
    }
    latexWorker = null;
};

let warmedUp = false;

/**
 * Start the heavy work that doesn't need project data (Pyodide runtime +
 * packages + report runtime; TeX engine download + format build) before the
 * user hits Generate — called when the section-selection modal opens, so it
 * runs while they pick sections. Safe to call repeatedly; failures stay
 * silent (generation surfaces them properly when real).
 */
export const warmUpLatexReport = () => {
    if (warmedUp) return;
    warmedUp = true;
    try {
        getTexWorker().then((worker) => worker.postMessage({ type: 'warmup', baseUrl: baseUrl() }));
        getLatexWorker().postMessage({ type: 'prepare', swiftlatexBase: `${baseUrl()}vendor/swiftlatex/` });
    } catch {
        // Warm-up is purely opportunistic.
    }
};

const generateTex = async ({ chunks, config, onProgress }) => {
    const worker = await getTexWorker();
    return new Promise((resolve, reject) => {
        const id = Date.now();
        const onMessage = (event) => {
            const data = event.data || {};
            if (data.type === 'progress') {
                onProgress?.(data.detail || data.stage);
                return;
            }
            if (data.id !== id) return;
            worker.removeEventListener('message', onMessage);
            if (data.type === 'result') {
                resolve({ tex: data.tex, files: data.files, plotError: data.plotError });
            } else {
                reject(new Error(data.message || 'LaTeX generation failed in the report worker.'));
            }
        };
        worker.addEventListener('message', onMessage);
        worker.addEventListener('error', (event) => {
            worker.removeEventListener('message', onMessage);
            texWorkerPromise = null;
            reject(new Error(`Report worker failed to load: ${event.message || 'unknown error'}`));
        }, { once: true });
        worker.postMessage({ id, type: 'generate', baseUrl: baseUrl(), chunks, config });
    });
};

const compilePdf = async ({ tex, assets, onProgress }) => {
    const worker = getLatexWorker();
    activeCompileProgress = onProgress;
    try {
        return await new Promise((resolve, reject) => {
            const onMessage = (event) => {
                const data = event.data || {};
                if (data.type === 'success') {
                    worker.removeEventListener('message', onMessage);
                    resolve({ pdf: data.pdf, log: data.log, elapsedMs: data.elapsedMs, passesRun: data.passesRun });
                } else if (data.type === 'error') {
                    worker.removeEventListener('message', onMessage);
                    // A failed engine may hold corrupt state; next run starts fresh.
                    resetLatexWorker();
                    reject(new Error(data.message || `LaTeX compile failed (status ${data.status}).\n${(data.log || '').slice(-2000)}`));
                }
            };
            worker.addEventListener('message', onMessage);
            worker.addEventListener('error', (event) => {
                resetLatexWorker();
                reject(new Error(`LaTeX compile worker failed to load: ${event.message || 'unknown error'}`));
            }, { once: true });
            worker.postMessage({
                type: 'compile-latex',
                tex,
                assets,
                swiftlatexBase: `${baseUrl()}vendor/swiftlatex/`,
            });
        });
    } finally {
        activeCompileProgress = null;
    }
};

/**
 * Generate the desktop-identical LCCA report PDF entirely in the browser.
 *
 * @returns {{ pdf: Uint8Array, fileName: string, plotError: string, log: string }}
 */
export const generateLatexReport = async ({
    projectData,
    results,
    currency,
    selections,
    onProgress = () => {},
}) => {
    onProgress('Preparing project data…');
    const chunks = desktopChunksForReport(projectData, { results, currency });

    // The engine download + format build has no dependency on the document,
    // so it runs concurrently with the Python tex generation (idempotent if
    // the modal-open warm-up already did it).
    getLatexWorker().postMessage({ type: 'prepare', swiftlatexBase: `${baseUrl()}vendor/swiftlatex/` });

    const { tex, files, plotError } = await generateTex({
        chunks,
        config: selections && Object.keys(selections).length ? selections : null,
        onProgress,
    });

    const assets = {};
    for (const [name, bytes] of Object.entries(files || {})) {
        assets[name] = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    }

    const rewritten = rewriteTexPaths(tex, Object.keys(assets));
    const { pdf, log } = await compilePdf({ tex: rewritten, assets, onProgress });

    const bridgeName = projectData?.general_info?.project_name
        || chunks?.general_info?.project_name
        || 'LCCA';
    const fileName = `${String(bridgeName).trim().replace(/\s+/g, '_')}_Report.pdf`;

    return { pdf, fileName, plotError: plotError || '', log: log || '' };
};

/** Trigger a browser download of the generated PDF. */
export const downloadPdf = (pdf, fileName) => {
    const blob = new Blob([pdf], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
};

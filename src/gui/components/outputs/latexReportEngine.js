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
    const worker = new Worker(`${baseUrl()}swiftlatex-report-worker.js`);
    try {
        return await new Promise((resolve, reject) => {
            worker.onmessage = (event) => {
                const data = event.data || {};
                if (data.type === 'status') {
                    onProgress?.(data.message);
                } else if (data.type === 'success') {
                    resolve({ pdf: data.pdf, log: data.log, elapsedMs: data.elapsedMs });
                } else if (data.type === 'error') {
                    reject(new Error(data.message || `LaTeX compile failed (status ${data.status}).\n${(data.log || '').slice(-2000)}`));
                }
            };
            worker.onerror = (event) => reject(new Error(`LaTeX compile worker failed to load: ${event.message || 'unknown error'}`));
            worker.postMessage({
                type: 'compile-latex',
                tex,
                assets,
                passes: 2,
                swiftlatexBase: `${baseUrl()}vendor/swiftlatex/`,
            });
        });
    } finally {
        worker.terminate();
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

/**
 * Report worker: runs the desktop app's Python report modules under Pyodide
 * and returns the generated .tex plus every file it references (plots,
 * logos). Compilation to PDF is a separate stage (see the LaTeX worker).
 *
 * Loaded as a classic worker from the app; all heavy assets (Pyodide
 * runtime from the pinned CDN, wasm packages, runtime.zip) are fetched
 * lazily on first use and land in the browser HTTP cache.
 */

// Loaded as a MODULE worker: pyodide v0.28+ (our v314 CDN line) dropped
// classic-worker support, so the runtime is pulled in via dynamic import.

// Keep in step with the pyodide devDependency in package.json.
const PYODIDE_VERSION = '314.0.2';
const PYODIDE_CDN = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

let bootPromise = null;

const report = (stage, detail = '') => {
    self.postMessage({ type: 'progress', stage, detail });
};

async function boot(baseUrl) {
    if (!bootPromise) {
        bootPromise = (async () => {
            report('pyodide', 'Loading Python runtime…');
            const { loadPyodide } = await import(/* @vite-ignore */ `${PYODIDE_CDN}pyodide.mjs`);
            const pyodide = await loadPyodide({ indexURL: PYODIDE_CDN });

            report('packages', 'Loading pandas + matplotlib…');
            await pyodide.loadPackage(['pandas', 'matplotlib', 'beautifulsoup4', 'pyyaml', 'jinja2'], {
                messageCallback: () => { },
            });

            report('runtime', 'Loading report modules…');
            const response = await fetch(`${baseUrl}report/runtime.zip`);
            if (!response.ok) throw new Error(`runtime.zip fetch failed (HTTP ${response.status})`);
            const zipBuffer = await response.arrayBuffer();
            pyodide.FS.mkdirTree('/runtime');
            pyodide.unpackArchive(zipBuffer, 'zip', { extractDir: '/runtime' });

            await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, "/runtime")
import report_compat
report_compat.install()
`);
            return pyodide;
        })().catch((error) => {
            bootPromise = null;
            throw error;
        });
    }
    return bootPromise;
}

async function generate(pyodide, chunks, config) {
    report('generate', 'Generating LaTeX report…');
    pyodide.globals.set('CHUNKS_JSON', JSON.stringify(chunks));
    pyodide.globals.set('CONFIG_JSON', JSON.stringify(config ?? null));
    const resultJson = await pyodide.runPythonAsync(`
import json
import report_compat
_result = report_compat.generate_report_tex(json.loads(CHUNKS_JSON), config=json.loads(CONFIG_JSON))
json.dumps({"tex": _result["tex"], "files": _result["files"], "plot_error": _result["plot_error"]})
`);
    const result = JSON.parse(resultJson);

    const files = {};
    const transfers = [];
    for (const [name, fsPath] of Object.entries(result.files)) {
        const bytes = pyodide.FS.readFile(fsPath);
        files[name] = bytes;
        transfers.push(bytes.buffer);
    }
    return { tex: result.tex, files, plotError: result.plot_error, transfers };
}

self.onmessage = async (event) => {
    const { id, type, baseUrl, chunks, config } = event.data;
    if (type !== 'generate') return;
    try {
        const pyodide = await boot(baseUrl);
        const { tex, files, plotError, transfers } = await generate(pyodide, chunks, config);
        self.postMessage({ id, type: 'result', tex, files, plotError }, transfers);
    } catch (error) {
        self.postMessage({ id, type: 'error', message: `${error?.message || error}` });
    }
};

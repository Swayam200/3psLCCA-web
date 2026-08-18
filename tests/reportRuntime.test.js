/**
 * LaTeX report engine — parity tests around the reference project
 * M_20_2L_OF_S (Mumbai 20 m 2-lane steel bridge).
 *
 * Always run:
 *   - the web→desktop chunk mapper (reportChunks.js) reproduces the
 *     desktop chunk store for a project round-tripped through the real
 *     desktop archive (tests/fixtures/m20.3ps → import3psFile → mapper).
 *
 * Gated behind REPORT_RUNTIME_TEST=1 (npm run test:report — downloads the
 * Pyodide runtime + wasm packages, ~1 min):
 *   - the full engine: mapped chunks → vendored desktop Python under
 *     Pyodide → .tex must equal the R0 golden byte-for-byte (after
 *     normalizing environment paths).
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { import3psFile } from '../src/utils/projectImport.js';
import { desktopChunksForReport } from '../src/gui/components/outputs/reportChunks.js';

const root = join(import.meta.dirname, '..');
const fixture = (name) => join(root, 'tests', 'fixtures', name);

const desktopChunks = JSON.parse(readFileSync(fixture('m20-desktop-chunks.json'), 'utf8'));

const loadMappedChunks = async () => {
    const archive = readFileSync(fixture('m20.3ps'));
    const project = await import3psFile(archive.buffer.slice(archive.byteOffset, archive.byteOffset + archive.byteLength));
    // results/currency come from the calculation flow at report time; the
    // engine's own parity with desktop is proven by npm run verify:parity.
    return desktopChunksForReport(project, {
        results: desktopChunks.comparison_cache.results,
        currency: desktopChunks.comparison_cache.currency,
    });
};

test('mapper: desktop archive round-trips into desktop-shaped chunks', async () => {
    const mapped = await loadMappedChunks();

    assert.equal(mapped.general_info.project_name, desktopChunks.general_info.project_name);
    assert.equal(mapped.bridge_data.analysis_period, desktopChunks.bridge_data.analysis_period);

    for (const chunk of ['str_foundation', 'str_sub_structure', 'str_super_structure', 'str_misc']) {
        assert.deepEqual(Object.keys(mapped[chunk]), Object.keys(desktopChunks[chunk]), chunk);
        for (const [section, rows] of Object.entries(desktopChunks[chunk])) {
            assert.equal(mapped[chunk][section].length, rows.length, `${chunk}/${section} row count`);
            rows.forEach((expected, i) => {
                const actual = mapped[chunk][section][i];
                for (const field of ['material_name', 'quantity', 'unit', 'rate', 'rate_source', 'carbon_emission']) {
                    assert.deepEqual(actual.values[field], expected.values[field], `${chunk}/${section}[${i}].${field}`);
                }
                assert.deepEqual(actual.state.in_trash ?? false, expected.state.in_trash ?? false);
            });
        }
    }

    assert.equal(mapped.transport_data.vehicles.length, desktopChunks.transport_data.vehicles.length);
    assert.equal(mapped.machinery_emissions_data.mode, desktopChunks.machinery_emissions_data.mode);
    assert.deepEqual(mapped.social_cost_data.source, desktopChunks.social_cost_data.source);
    assert.equal(mapped.comparison_cache.is_valid, true);
    assert.equal(mapped.comparison_cache.currency, desktopChunks.comparison_cache.currency);
});

/** Environment-path normalization: plot temp suffixes, FS prefixes, temp dirs. */
const normalize = (text) => text
    .replace(/lcca_plot_([a-z_]+)_[a-z0-9_]+\.png/g, 'lcca_plot_$1.png')
    .replace(/\{[^{}]*\/(three_ps_lcca_gui|r0_out|out|report_out|tmp[a-z0-9_]*)\//g, '{$1/')
    .replace(/\{[^{}]*[/\\](3ps_lcca_agency_logo\.png)\}/g, '{$1}');

/**
 * Number-canonical form: 20 and 20.0 compare equal. Python prints floats
 * with a trailing .0 while JSON→JS→JSON collapses integral floats to ints;
 * desktop itself renders whichever it receives, so this difference is
 * environmental, not semantic.
 */
const semantic = (text) => text.replace(
    /-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?/g,
    (num) => String(Number(num)),
);

test('web-data golden is semantically identical to the desktop-store golden', () => {
    const desktop = normalize(readFileSync(fixture('m20-report.golden.tex'), 'utf8'));
    const webdata = normalize(readFileSync(fixture('m20-report-webdata.golden.tex'), 'utf8'));
    const desktopLines = desktop.split('\n');
    const webdataLines = webdata.split('\n');
    assert.equal(webdataLines.length, desktopLines.length);
    desktopLines.forEach((line, i) => {
        assert.equal(semantic(webdataLines[i]), semantic(line), `semantic diff at line ${i}`);
    });
});

test(
    'engine: mapped chunks reproduce the web-data golden tex under Pyodide',
    { skip: process.env.REPORT_RUNTIME_TEST !== '1' && 'set REPORT_RUNTIME_TEST=1 (npm run test:report)' },
    async () => {
        const { loadPyodide } = await import('pyodide');
        const mapped = await loadMappedChunks();

        const pyodide = await loadPyodide();
        await pyodide.loadPackage(['pandas', 'matplotlib', 'beautifulsoup4', 'pyyaml', 'jinja2'], { messageCallback: () => { } });

        const zipBuffer = readFileSync(join(root, 'public', 'report', 'runtime.zip'));
        pyodide.FS.mkdirTree('/runtime');
        pyodide.unpackArchive(new Uint8Array(zipBuffer), 'zip', { extractDir: '/runtime' });

        pyodide.globals.set('CHUNKS_JSON', JSON.stringify(mapped));
        const tex = await pyodide.runPythonAsync(`
import json, sys
sys.path.insert(0, "/runtime")
import report_compat
report_compat.generate_report_tex(json.loads(CHUNKS_JSON))["tex"]
`);

        const golden = normalize(readFileSync(fixture('m20-report-webdata.golden.tex'), 'utf8'));
        const actual = normalize(tex);
        if (actual !== golden) {
            const goldenLines = golden.split('\n');
            const actualLines = actual.split('\n');
            for (let i = 0; i < Math.max(goldenLines.length, actualLines.length); i += 1) {
                if (goldenLines[i] !== actualLines[i]) {
                    assert.fail(`tex differs at line ${i}:\n  golden: ${goldenLines[i]}\n  actual: ${actualLines[i]}`);
                }
            }
        }
        assert.equal(actual, golden);
    },
);

import test from 'node:test';
import assert from 'node:assert/strict';

import { rewriteTexPaths } from '../src/gui/components/outputs/latexReportEngine.js';

test('rewriteTexPaths: absolute asset paths become bare MemFS names', () => {
    const tex = [
        '\\includegraphics[width=2cm]{/report_out/lcca_plot_pillar_bars_ab12cd34.png}',
        '\\includegraphics{/runtime/three_ps_lcca_gui/gui/assets/logo/3pslcca_header.png}',
        '\\includegraphics{C:\\temp\\3ps_lcca_agency_logo.png}',
    ].join('\n');
    const names = [
        'lcca_plot_pillar_bars_ab12cd34.png',
        '3pslcca_header.png',
        '3ps_lcca_agency_logo.png',
    ];
    const out = rewriteTexPaths(tex, names);
    assert.match(out, /\{lcca_plot_pillar_bars_ab12cd34\.png\}/);
    assert.match(out, /\{3pslcca_header\.png\}/);
    assert.match(out, /\{3ps_lcca_agency_logo\.png\}/);
    assert.doesNotMatch(out, /report_out|runtime\/|C:\\/);
});

test('rewriteTexPaths: template unicode is pre-expanded for the wasm engine', () => {
    const out = rewriteTexPaths('kgCO₂e — ₹1,000 – 2,000', []);
    assert.equal(out, 'kgCO\\textsubscript{2}e -- Rs.1,000 -- 2,000');
});

test('rewriteTexPaths: leaves already-bare names and other braces alone', () => {
    const tex = '\\includegraphics{plot.png} \\textbf{Total}';
    assert.equal(rewriteTexPaths(tex, ['plot.png']), tex);
});

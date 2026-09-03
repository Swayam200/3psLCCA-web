#!/usr/bin/env node
/**
 * Print the HTML report of the M_20_2L_OF_S reference project to PDF the way
 * a user would (browser "Save as PDF"), using headless Chromium.
 *
 *   npm run dev            # in another terminal (or pass --url)
 *   node scripts/print-report-sample.mjs [--url http://localhost:5173] [--out report-samples]
 *
 * The project is loaded exactly like the LaTeX golden test does (desktop
 * archive → import3psFile) with the desktop's own calculation results, so the
 * PDF can be compared page by page with the LaTeX report.
 */
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chromium } from 'playwright';
import { import3psFile } from '../src/utils/projectImport.js';

const args = Object.fromEntries(process.argv.slice(2).map((a, i, all) => (a.startsWith('--') ? [a.slice(2), all[i + 1]] : [])).filter(Boolean));
const baseUrl = (args.url || 'http://localhost:5173').replace(/\/$/, '');
const outDir = resolve(args.out || 'report-samples');
mkdirSync(outDir, { recursive: true });

const root = resolve(import.meta.dirname, '..');
const fixture = (name) => join(root, 'tests', 'fixtures', name);
const desktopChunks = JSON.parse(readFileSync(fixture('m20-desktop-chunks.json'), 'utf8'));
const archive = readFileSync(fixture('m20.3ps'));
const project = await import3psFile(archive.buffer.slice(archive.byteOffset, archive.byteOffset + archive.byteLength));

const projectId = 'm20-html-report-sample';
project.id = projectId;
project.outputs_data = {
    results: desktopChunks.comparison_cache.results,
    analysis_period_years: desktopChunks.comparison_cache.analysis_period,
    calculated_at: new Date().toISOString(),
    source: 'desktop-reference',
    engine: { source: 'desktop-reference', coreVersion: 'desktop golden' },
};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
page.on('pageerror', (error) => console.error('[page error]', error.message));
page.on('console', (message) => { if (message.type() === 'error') console.error('[console]', message.text()); });

// Seed a guest session + the project in storage, then open the report route.
await page.goto(`${baseUrl}/`);
await page.evaluate(({ id, data, name }) => {
    localStorage.setItem(`project_data_${id}`, JSON.stringify({ data, sync_status: 'synced' }));
    localStorage.setItem('recentProjects', JSON.stringify([{ id, name, date: new Date().toLocaleDateString() }]));
    localStorage.setItem('3pslcca.guestSession', JSON.stringify({ name: 'Report Sample', savedAt: new Date().toISOString() }));
    sessionStorage.setItem('isGuest', 'true');
}, { id: projectId, data: project, name: project.name || 'M_20_2L_OF_S' });

const t0 = Date.now();
await page.goto(`${baseUrl}/project/${projectId}/report`, { waitUntil: 'networkidle' });
await page.waitForSelector('[data-testid="lcca-html-report"]', { timeout: 60_000 });
await page.evaluate(() => document.fonts.ready);
const renderMs = Date.now() - t0;

const stats = await page.evaluate(() => ({
    tables: document.querySelectorAll('.lcca-report figure.table').length,
    figures: document.querySelectorAll('.lcca-report figure.fig').length,
    equations: document.querySelectorAll('.lcca-report .katex').length,
    words: document.querySelector('.lcca-report').innerText.split(/\s+/).length,
}));

await page.emulateMedia({ media: 'print' });
const t1 = Date.now();
const pdf = await page.pdf({ format: 'A4', printBackground: true, preferCSSPageSize: true });
const pdfMs = Date.now() - t1;

const pdfPath = join(outDir, 'M_20_2L_OF_S_HTML_Report.pdf');
writeFileSync(pdfPath, pdf);
const pages = (pdf.toString('latin1').match(/\/Type\s*\/Page[^s]/g) || []).length;

await page.emulateMedia({ media: 'screen' });
await page.screenshot({ path: join(outDir, 'report-screen-top.png'), fullPage: false });

await browser.close();

console.log(JSON.stringify({
    pdf: pdfPath,
    pages,
    pdfBytes: pdf.length,
    renderMs,
    pdfMs,
    ...stats,
}, null, 2));

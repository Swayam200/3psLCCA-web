#!/usr/bin/env node
/**
 * Print the HTML report of the M_20_2L_OF_S reference project to PDF the way
 * a user would (page preview → browser "Save as PDF"), using headless Chromium.
 *
 *   npm run dev            # in another terminal (or pass --url)
 *   node scripts/print-report-sample.mjs [--url http://localhost:5173] [--out report-samples]
 *
 * The project is loaded exactly like the LaTeX golden test does (desktop
 * archive → import3psFile) with the desktop's own calculation results, so the
 * PDF can be compared page by page with the LaTeX report.
 *
 * Exits non-zero if pagination fails or the contents list has no page numbers.
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
const problems = [];
page.on('pageerror', (error) => problems.push(`page error: ${error.message}`));
page.on('console', (message) => { if (message.type() === 'error') problems.push(`console: ${message.text()}`); });

// Seed a guest session + the project in storage, then open the report route.
await page.goto(`${baseUrl}/`);
await page.evaluate(({ id, data, name }) => {
    localStorage.setItem(`project_data_${id}`, JSON.stringify({ data, sync_status: 'synced' }));
    localStorage.setItem('recentProjects', JSON.stringify([{ id, name, date: new Date().toLocaleDateString() }]));
    localStorage.setItem('3pslcca.guestSession', JSON.stringify({ name: 'Report Sample', savedAt: new Date().toISOString() }));
    sessionStorage.setItem('isGuest', 'true');
}, { id: projectId, data: project, name: project.name || 'M_20_2L_OF_S' });

// 1. Continuous view: how fast the report is readable.
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

// 2. Page preview (Paged.js): what actually prints.
const t1 = Date.now();
await page.goto(`${baseUrl}/project/${projectId}/report?paged=1`, { waitUntil: 'networkidle' });
await page.waitForSelector('.lcca-report-shell[data-paged-ready="true"]', { timeout: 120_000 });
const pagedMs = Date.now() - t1;

const paged = await page.evaluate(() => {
    const pages = document.querySelectorAll('.pagedjs_page');
    // Named pages carry a pagedjs_<name>_page class (and, in newer builds, data-page-name).
    const named = [...pages].map((p) => p.getAttribute('data-page-name')
        || (p.className.match(/pagedjs_(?!page\b|named_page\b|first_page\b|right_page\b|left_page\b)([\w-]+?)_page/) || [])[1]
        || 'default');
    // Contents-list numbers are written into the links by pagedPreview.js.
    const tocNumber = (selector) => {
        const text = document.querySelector(`.pagedjs_pages ${selector} .pg a`)?.textContent.trim();
        return text ? Number(text) : null;
    };
    // Margin-box text is CSS generated content (::after on the content box).
    const marginText = (pageIndex, box) => {
        const el = pages[pageIndex]?.querySelector(`.pagedjs_margin-${box} .pagedjs_margin-content`);
        return el ? getComputedStyle(el, '::after').content.replace(/^"|"$/g, '') : null;
    };
    // Printed page number of each page box (set by pagedPreview.js).
    const numbering = [...pages].map((p) => p.dataset.reportPage || '?').join(' ');
    const landscapeTable = document.querySelector('.pagedjs_pages .landscape-page table');
    const landscape = landscapeTable ? {
        tableWidth: Math.round(landscapeTable.getBoundingClientRect().width),
        areaWidth: Math.round(landscapeTable.closest('.pagedjs_page_content').getBoundingClientRect().width),
        sheetWidth: Math.round(landscapeTable.closest('.pagedjs_page').querySelector('.pagedjs_sheet').getBoundingClientRect().width),
    } : null;
    const rect = (selector) => { const r = document.querySelector(selector)?.getBoundingClientRect(); return r ? [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)] : null; };
    const screen = { viewport: window.innerWidth, toolbar: rect('.lcca-report-toolbar'), firstPage: rect('.pagedjs_page'), pagesBox: rect('.pagedjs_pages') };
    return {
        pageBoxes: pages.length,
        coverPages: named.filter((n) => n === 'cover').length,
        frontmatterPages: named.filter((n) => n === 'frontmatter').length,
        landscapePages: named.filter((n) => n === 'landscape-page').length,
        numbering,
        tocIntroductionPage: tocNumber('.toc li.l1:nth-child(1)'),
        tocResultsPage: tocNumber('.toc li.l1:nth-last-child(4)'),
        page4Header: marginText(3, 'top-left'),
        page4Footer: marginText(3, 'bottom-center'),
        landscape,
        screen,
    };
});

// What the user sees on screen before printing.
await page.screenshot({ path: join(outDir, 'report-paged-top.png'), fullPage: false });

await page.emulateMedia({ media: 'print' });
// The landscape appendix box must carry its own named page for the browser
// to print it on a landscape sheet.
const landscapePrint = await page.evaluate(() => {
    const el = document.querySelector('.pagedjs_landscape-page_page');
    return el ? { namedPage: getComputedStyle(el).page, boxWidth: el.offsetWidth, boxHeight: el.offsetHeight } : null;
});
const t2 = Date.now();
const pdf = await page.pdf({ printBackground: true, preferCSSPageSize: true });
const pdfMs = Date.now() - t2;

const pdfPath = join(outDir, 'M_20_2L_OF_S_HTML_Report.pdf');
writeFileSync(pdfPath, pdf);
const pdfText = pdf.toString('latin1');
const pdfPages = (pdfText.match(/\/Type\s*\/Page[^s]/g) || []).length;
const landscapeSheets = [...pdfText.matchAll(/\/MediaBox\s*\[([^\]]+)\]/g)]
    .map((m) => m[1].trim().split(/\s+/).map(Number))
    .filter(([, , w, h]) => w > h).length;
await browser.close();

const result = { pdf: pdfPath, pdfPages, landscapeSheets, pdfBytes: pdf.length, renderMs, pagedMs, pdfMs, ...stats, ...paged, landscapePrint, problems };
console.log(JSON.stringify(result, null, 2));

// The preview must keep its screen chrome: toolbar visible, pages centred.
if (!(paged.screen.toolbar?.[3] > 0)) problems.push('toolbar hidden in page preview');
if (!(paged.screen.firstPage?.[0] > 0)) problems.push('page boxes not centred in page preview');

if (problems.length || !paged.tocIntroductionPage || paged.pageBoxes !== pdfPages || landscapeSheets !== paged.landscapePages) {
    console.error('Report print check FAILED');
    process.exit(1);
}

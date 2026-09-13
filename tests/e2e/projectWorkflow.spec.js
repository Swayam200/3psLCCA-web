import { test, expect } from 'playwright/test';
import { readFileSync } from 'node:fs';
import { import3psFile } from '../../src/utils/projectImport.js';

const fixture = name => new URL(`../fixtures/${name}`, import.meta.url);
const baseProject = JSON.parse(readFileSync(fixture('global-project.json'), 'utf8'));
const desktop = JSON.parse(readFileSync(fixture('m20-desktop-chunks.json'), 'utf8'));

async function seed(page, project = baseProject, id = 'smoke-project') {
    await page.goto('./');
    await page.evaluate(({ project, id }) => {
        localStorage.setItem('3pslcca.guestSession', JSON.stringify({ name: 'Test Guest', savedAt: '2026-01-01T00:00:00Z' }));
        localStorage.setItem(`project_data_${id}`, JSON.stringify({ data: project, sync_status: 'synced' }));
        localStorage.setItem('recentProjects', JSON.stringify([{ id, name: project.name || 'Smoke Bridge', date: '2026-01-01' }]));
        sessionStorage.setItem('isGuest', 'true');
    }, { project, id });
    await page.goto(`project/${id}/General%20Information`);
}

test.beforeEach(async ({ page }) => {
    // A browser smoke run must never reach Appwrite, model providers or a CDN.
    await page.route('**/*', route => {
        const url = new URL(route.request().url());
        return ['127.0.0.1', 'localhost'].includes(url.hostname) ? route.continue() : route.abort();
    });
});

test('protected links lead to login and guest access survives reload', async ({ page }) => {
    await page.goto('project/missing/Results');
    await expect(page).toHaveURL(/\/login$/);
    await page.getByRole('button', { name: 'Continue as Guest' }).click();
    await page.getByPlaceholder('e.g. John Doe').fill('Test Guest');
    await page.getByRole('dialog').getByRole('button', { name: /continue|start|proceed/i }).click();
    await expect(page).toHaveURL(/\/3psLCCA-web\/$/);
    await page.reload();
    await expect(page).toHaveURL(/\/3psLCCA-web\/$/);
    await expect(page.getByPlaceholder('Search projects...')).toBeVisible();
});

test('renaming through the workspace persists across reload', async ({ page }) => {
    await seed(page);
    await page.getByRole('button', { name: 'File', exact: true }).click();
    await page.getByText('Rename', { exact: true }).click();
    await page.getByPlaceholder('Enter new project name').fill('Persisted Test Bridge');
    await page.getByRole('button', { name: 'OK', exact: true }).click();
    await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('project_data_smoke-project')).data.name)).toBe('Persisted Test Bridge');
    await page.reload();
    await expect(page.locator('#project_name')).toHaveValue('Persisted Test Bridge');
});

test('project creation from the workspace validates and opens the new project', async ({ page }) => {
    await seed(page);
    await page.getByRole('button', { name: 'File', exact: true }).click();
    await page.getByText('New Project', { exact: true }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: /create/i }).click();
    await expect(dialog.getByText('Please enter a Project Name.')).toBeVisible();
    await dialog.getByPlaceholder('e.g. Highway 5 Bridge Replacement').fill('Created Test Bridge');
    await dialog.locator('select').nth(0).selectOption({ index: 1 });
    await dialog.locator('select').nth(1).selectOption('INR');
    await dialog.getByRole('button', { name: /create/i }).click();
    await expect(page).toHaveURL(/project\/new_project_\d+\/General/);
    await expect(page.locator('#project_name')).toHaveValue('Created Test Bridge');
});

test('legacy carbon routes still open their corresponding pages', async ({ page }) => {
    await seed(page);
    const buttons = (await page.getByRole('button').allTextContents()).map(text => text.trim());
    const positions = ['Social Cost of Carbon', 'Material Emissions', 'Transportation Emissions', 'Machinery/Equipment Emissions', 'Traffic Rerouting Emissions'].map(name => buttons.indexOf(name));
    expect(positions.every(index => index >= 0)).toBe(true);
    expect(positions).toEqual([...positions].sort((a, b) => a - b));
    for (const [route, text] of [['Carbon Emission Data', 'Social Cost'], ['Machinery Emissions', 'Machinery'], ['Traffic Diversion Emissions', 'Traffic']]) {
        await page.goto(`project/smoke-project/${encodeURIComponent(route)}`);
        await expect(page.getByText(new RegExp(text)).first()).toBeVisible();
        await expect(page.locator('input, select, textarea').first()).toBeVisible();
    }
});

test('missing report projects show a recoverable message', async ({ page }) => {
    await seed(page);
    await page.goto('project/absent/report');
    await expect(page.getByText('Project not found')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Back to projects' })).toBeVisible();
});

test('the reference report renders and paginates into a printable PDF', async ({ page }, testInfo) => {
    const resourceFailures = [];
    page.on('response', response => {
        if (response.status() >= 400) resourceFailures.push({ status: response.status(), url: response.url().slice(0, 180) });
    });
    const archive = readFileSync(fixture('m20.3ps'));
    const project = await import3psFile(archive.buffer.slice(archive.byteOffset, archive.byteOffset + archive.byteLength));
    project.outputs_data = { results: desktop.comparison_cache.results, analysis_period_years: desktop.comparison_cache.analysis_period, calculated_at: '2026-01-01T00:00:00Z', source: 'desktop-reference', engine: { source: 'desktop-reference', coreVersion: 'fixture' } };
    await seed(page, project);
    await page.goto('project/smoke-project/report?paged=0');
    const report = page.getByTestId('lcca-html-report');
    await expect(report).toBeVisible();
    await expect(report).toContainText(project.general_info.project_name);
    await expect(report.locator('table').first()).toBeVisible();
    await expect(report).not.toContainText('NaN');
    await page.getByRole('button', { name: 'Page preview / Print' }).click();
    await expect(page.locator('[data-paged-ready="true"]')).toBeVisible({ timeout: 30_000 });
    await expect(page.getByRole('button', { name: 'Print / Save as PDF' })).toBeEnabled();
    expect(await page.locator('.pagedjs_page').count()).toBeGreaterThan(1);
    const pdfPath = testInfo.outputPath('reference-report.pdf');
    const pdf = await page.pdf({ path: pdfPath, format: 'A4', printBackground: true, preferCSSPageSize: true });
    expect(pdf.subarray(0, 5).toString()).toBe('%PDF-');
    expect(pdf.byteLength).toBeGreaterThan(20_000);
    await testInfo.attach('reference-report', { path: pdfPath, contentType: 'application/pdf' });
    await page.screenshot({ path: testInfo.outputPath('report-preview.png') });
    if (resourceFailures.length) await testInfo.attach('resource-failures', { body: JSON.stringify(resourceFailures, null, 2), contentType: 'application/json' });
});

test('a successful calculation persists results and locks inputs', async ({ page }) => {
    let request;
    await page.route('**/mock-api/api/lcca/calculate', route => {
        request = route.request().postDataJSON();
        return route.fulfill({ json: { status: 'success', results: desktop.comparison_cache.results, computed: {}, validation: { errors: [], warnings: [] } } });
    });
    await seed(page);
    await page.getByRole('button', { name: 'Calculate', exact: true }).click();
    await page.getByRole('button', { name: 'Proceed with Calculation ▸' }).click();
    await expect(page.getByText(/Calculated with: FastAPI backend/)).toBeVisible();
    expect(request.project.bridge_data).toBeTruthy();
    expect(request.analysis_period_years).toBeGreaterThan(0);
    await expect(page.getByRole('button', { name: 'Unlock project' })).toBeVisible();
    await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('project_data_smoke-project')).data.outputs_data?.source)).toBe('backend');
});

test('a calculation validation error stays visible and leaves inputs editable', async ({ page }) => {
    await page.route('**/mock-api/api/lcca/calculate', route => route.fulfill({ json: { status: 'error', results: {}, validation: { errors: ['Test validation: analysis period is required.'], warnings: [] } } }));
    await seed(page);
    await page.getByRole('button', { name: 'Calculate', exact: true }).click();
    await page.getByRole('button', { name: 'Proceed with Calculation ▸' }).click();
    await expect(page.getByText('Test validation: analysis period is required.', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Lock project', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Proceed with Calculation ▸' })).toBeEnabled();
});

test('export downloads a usable project archive', async ({ page }) => {
    await seed(page);
    await page.locator('#project_name').fill('Exported Bridge');
    await page.locator('#project_name').blur();
    await page.getByRole('button', { name: 'File', exact: true }).click();
    const downloaded = page.waitForEvent('download');
    await page.getByText('Export...', { exact: true }).click();
    const download = await downloaded;
    expect(download.suggestedFilename()).toMatch(/\.3ps$/);
    const bytes = readFileSync(await download.path());
    const restored = await import3psFile(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
    expect(restored.general_info.project_name).toBe('Exported Bridge');
});

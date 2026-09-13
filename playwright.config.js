import { defineConfig, devices } from 'playwright/test';

export default defineConfig({
    testDir: './tests/e2e',
    fullyParallel: true,
    forbidOnly: Boolean(process.env.CI),
    retries: 0,
    workers: process.env.CI ? 2 : undefined,
    timeout: 30_000,
    expect: { timeout: 10_000 },
    reporter: [['list'], ['html', { open: 'never' }]],
    use: {
        baseURL: 'http://127.0.0.1:4175/3psLCCA-web/',
        trace: 'retain-on-failure',
        screenshot: 'only-on-failure',
    },
    projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
    webServer: {
        command: 'node scripts/serve-e2e.mjs',
        url: 'http://127.0.0.1:4175/3psLCCA-web/',
        reuseExistingServer: false,
        timeout: 120_000,
    },
});

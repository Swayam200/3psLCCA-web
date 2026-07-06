import { defineConfig } from '@playwright/test'
import process from 'node:process'

const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:4173'
export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  use: {
    baseURL,
    browserName: 'chromium',
    headless: true,
  },
  webServer: {
    command: process.env.PLAYWRIGHT_SERVER_COMMAND || 'python3 -m http.server 4173 --directory dist',
    url: `${baseURL}/wasm-smoke.html`,
    reuseExistingServer: true,
    timeout: 30_000,
  },
})

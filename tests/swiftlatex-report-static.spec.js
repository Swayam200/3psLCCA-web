import { expect, test } from '@playwright/test'

test('static dist compiles the real 3psLCCA report through SwiftLaTeX WebAssembly', async ({ page }) => {
  test.setTimeout(120_000)

  const requestedUrls = []
  page.on('request', (request) => requestedUrls.push(request.url()))

  await page.goto('./swiftlatex-report-smoke.html')
  await expect(page.locator('#status')).toHaveAttribute('data-status', 'success', {
    timeout: 120_000,
  })
  await expect(page.locator('#result')).toContainText('"source": "wasm"')
  await expect(page.locator('#result')).toContainText('"reportEngine": "swiftlatex"')
  await expect(page.locator('#result')).toContainText('"texliveMode": "local"')
  await expect(page.locator('#result')).toContainText('"texHasWasmProvenance": true')
  await expect(page.locator('#result')).toContainText('"texHasLccaResults": true')

  const pageOrigin = new URL(page.url()).origin
  expect(requestedUrls.some((url) => url.includes(':8000'))).toBe(false)
  expect(requestedUrls.some((url) => url.includes('swiftlatex.com'))).toBe(false)
  expect(requestedUrls.every((url) => url.startsWith(pageOrigin))).toBe(true)
})

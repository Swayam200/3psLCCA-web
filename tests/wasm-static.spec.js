import { expect, test } from '@playwright/test'

test('static dist runs the Python core in WebAssembly with native parity', async ({ page }) => {
  const requestedUrls = []
  page.on('request', (request) => requestedUrls.push(request.url()))

  await page.goto('./wasm-smoke.html')
  await expect(page.locator('#status')).toHaveAttribute('data-status', 'success', {
    timeout: 60_000,
  })
  await expect(page.locator('#status')).toContainText('native parity')
  await expect(page.locator('#result')).toContainText('"nativeParity": true')
  await expect(page.locator('#result')).toContainText('"indiaParity": true')
  await expect(page.locator('#result')).toContainText('"repeatStable": true')
  await expect(page.locator('#result')).toContainText('"source": "wasm"')

  const pageOrigin = new URL(page.url()).origin
  expect(requestedUrls.some((url) => url.includes(':8000'))).toBe(false)
  expect(requestedUrls.every((url) => url.startsWith(pageOrigin))).toBe(true)
})

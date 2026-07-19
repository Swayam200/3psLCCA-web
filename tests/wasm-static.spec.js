import { expect, test } from '@playwright/test'

const CDN_HOSTS = ['cdn.jsdelivr.net', 'swayam200.github.io']
const CDN_URL_PATTERN = /^https:\/\/(cdn\.jsdelivr\.net|swayam200\.github\.io)\//

const expectNativeParity = async (page) => {
  await expect(page.locator('#status')).toHaveAttribute('data-status', 'success', {
    timeout: 120_000,
  })
  await expect(page.locator('#status')).toContainText('native parity')
  await expect(page.locator('#result')).toContainText('"nativeParity": true')
  await expect(page.locator('#result')).toContainText('"indiaParity": true')
  await expect(page.locator('#result')).toContainText('"repeatStable": true')
  await expect(page.locator('#result')).toContainText('"source": "wasm"')
}

test('CDN-first: engine runs with native parity using only allow-listed origins', async ({ page }) => {
  const requestedUrls = []
  page.on('request', (request) => requestedUrls.push(request.url()))

  await page.goto('./wasm-smoke.html')
  await expectNativeParity(page)

  const pageOrigin = new URL(page.url()).origin
  expect(requestedUrls.some((url) => url.includes(':8000'))).toBe(false)
  const allowedOrigin = (url) => url.startsWith(pageOrigin)
    || CDN_HOSTS.includes(new URL(url).hostname)
  expect(requestedUrls.every(allowedOrigin)).toBe(true)
})

test('bundled fallback: engine stays fully static when CDN origins are unreachable', async ({ page }) => {
  await page.route(CDN_URL_PATTERN, (route) => route.abort())

  const successfulUrls = []
  page.on('response', (response) => {
    if (response.ok()) successfulUrls.push(response.url())
  })

  await page.goto('./wasm-smoke.html')
  await expectNativeParity(page)

  // The engine must report that both assets came from the bundled copies.
  await expect(page.locator('#result')).toContainText('"pyodide": "bundled"')
  await expect(page.locator('#result')).toContainText('"wheel": "bundled"')

  const pageOrigin = new URL(page.url()).origin
  expect(successfulUrls.some((url) => url.includes(':8000'))).toBe(false)
  expect(successfulUrls.every((url) => url.startsWith(pageOrigin))).toBe(true)
})

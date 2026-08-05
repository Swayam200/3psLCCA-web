/**
 * LCCA calculation API.
 *
 * Two interchangeable engines produce identical responses:
 *
 *  - "browser": the published 3psLCCA-core engine (Pyodide via CDN) with the
 *    shared web->core adapter loaded into it. No server needed.
 *  - "backend": the FastAPI backend (backend/), reached over HTTP.
 *
 * Default behaviour is browser-first: if the CDN engine cannot load or
 * initialise (offline, CDN outage), the app falls back to the backend for the
 * rest of the session. VITE_LCCA_ENGINE=browser|backend pins one engine and
 * disables the fallback.
 */
const LCCA_API_BASE = (import.meta.env?.VITE_LCCA_API_URL || 'http://localhost:8000').replace(/\/$/, '')
const FORCED_ENGINE = String(import.meta.env?.VITE_LCCA_ENGINE || '').toLowerCase()

let mode = FORCED_ENGINE === 'backend' ? 'backend' : 'browser'

// Test seam: node's test runner cannot import browserEngine.js (it uses
// Vite-only `?raw` imports), so the loader is injectable.
let loadBrowserEngine = () => import('./lccaEngine/browserEngine.js')
export const __setBrowserEngineLoaderForTests = (loader) => {
  loadBrowserEngine = loader
  mode = FORCED_ENGINE === 'backend' ? 'backend' : 'browser'
}

const requestJson = async (path, payload) => {
  let response
  try {
    response = await fetch(`${LCCA_API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch {
    throw new Error(
      `Could not reach the calculation backend at ${LCCA_API_BASE}. `
      + 'Make sure it is running (see docs/backend-setup.md).',
    )
  }

  if (!response.ok) {
    throw new Error(`Calculation backend request failed with HTTP ${response.status}.`)
  }
  return response.json()
}

const backendRequest = (path, request) => requestJson(path, {
  project: request?.project ?? {},
  analysis_period_years: request?.analysisPeriodYears ?? 50,
  debug: false,
})

const fallBackToBackend = (error, onStatus) => {
  if (FORCED_ENGINE === 'browser') throw error
  console.warn(`[lccaApi] In-browser engine unavailable (${error?.message}); using the backend.`)
  onStatus?.('In-browser engine unavailable; switching to the calculation backend...')
  mode = 'backend'
}

/**
 * Prepare whichever engine will run the next calculation.
 * @param {(message: string) => void} [onStatus] progress messages (browser
 *   engine start-up stages; the backend is ready immediately).
 */
export const initializeLccaEngine = async (onStatus) => {
  if (mode === 'browser') {
    try {
      const engine = await loadBrowserEngine()
      return await engine.initializeBrowserEngine(onStatus)
    } catch (error) {
      fallBackToBackend(error, onStatus)
    }
  }
  return { status: 'ready' }
}

const run = async (method, browserCall, backendPath, request) => {
  if (mode === 'browser') {
    try {
      const engine = await loadBrowserEngine()
      return await engine[browserCall](request)
    } catch (error) {
      // The bridge returns calculation/validation problems as JSON, so a
      // throw here means the engine itself is broken - fall back.
      fallBackToBackend(error, request?.onStatus)
    }
  }
  return backendRequest(backendPath, request)
}

export const calculateLcca = (request) => run('calculate', 'calculateLcca', '/api/lcca/calculate', request)
export const validateLcca = (request) => run('validate', 'validateLcca', '/api/lcca/validate', request)

export const getLccaEngineMode = () => mode
export const getLccaEngineStatus = async () => ({ state: 'ready', mode })
export const getLccaEngineDescription = async () => (
  mode === 'browser'
    ? 'in-browser 3psLCCA-core engine (CDN)'
    : `calculation backend (${LCCA_API_BASE})`
)
export const terminateLccaEngine = () => {}

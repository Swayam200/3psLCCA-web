/**
 * Browser calculation engine loader.
 *
 * Loads the official 3psLCCA-core browser build published by the upstream
 * project at https://3pslcca.github.io/3psLCCA-core/ . That script boots
 * Pyodide, installs the versioned `three_ps_lcca_core` wheel, and exposes
 * `window.ThreePsLccaCore`.
 *
 * This module only handles *loading and initialising* the engine. Turning an
 * app project into the core engine's input schema happens elsewhere.
 *
 * Configuration (both optional):
 *   VITE_LCCA_ENGINE_URL   URL of a specific 3pslccacore.js release
 *   VITE_LCCA_PYODIDE_URL  URL of the matching pyodide.js
 */

const DEFAULT_ENGINE_URL = 'https://3pslcca.github.io/3psLCCA-core/release/v1.0.2/3pslccacore.js'
// Subresource-integrity hash published on the release page for the URL above;
// the browser refuses to run the script if the fetched bytes don't match.
const DEFAULT_ENGINE_SRI = 'sha256-riQ+g+lkFBbz1VzpMSbp5YozEAjy92QYwmzpuETwiPg='
const DEFAULT_PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v314.0.2/full/pyodide.js'
const SCRIPT_TIMEOUT_MS = 30_000

export const getEngineUrl = () => import.meta.env?.VITE_LCCA_ENGINE_URL || DEFAULT_ENGINE_URL
export const getPyodideUrl = () => import.meta.env?.VITE_LCCA_PYODIDE_URL || DEFAULT_PYODIDE_URL
// Integrity only applies to the URL it was computed for: a custom engine URL
// needs its own hash (VITE_LCCA_ENGINE_SRI) or runs without the check.
export const getEngineIntegrity = () => {
  if (import.meta.env?.VITE_LCCA_ENGINE_SRI) return import.meta.env.VITE_LCCA_ENGINE_SRI
  return getEngineUrl() === DEFAULT_ENGINE_URL ? DEFAULT_ENGINE_SRI : undefined
}

let enginePromise
let pyodideRuntime

/** Inject a classic <script> tag once, resolving when it has executed. */
const loadScript = (url, { integrity } = {}) => new Promise((resolve, reject) => {
  const existing = document.querySelector(`script[data-lcca-src="${url}"]`)
  if (existing) {
    if (existing.dataset.lccaLoaded === 'true') {
      resolve()
      return
    }
    existing.addEventListener('load', () => resolve())
    existing.addEventListener('error', () => reject(new Error(`Failed to load ${url}`)))
    return
  }

  const script = document.createElement('script')
  script.src = url
  script.async = true
  script.dataset.lccaSrc = url
  if (integrity) {
    script.integrity = integrity
    script.crossOrigin = 'anonymous'
  }

  const timer = setTimeout(
    () => reject(new Error(`Timed out after ${SCRIPT_TIMEOUT_MS / 1000}s loading ${url}`)),
    SCRIPT_TIMEOUT_MS,
  )
  script.addEventListener('load', () => {
    clearTimeout(timer)
    script.dataset.lccaLoaded = 'true'
    resolve()
  })
  script.addEventListener('error', () => {
    clearTimeout(timer)
    reject(new Error(`Failed to load ${url}`))
  })

  document.head.appendChild(script)
})

/**
 * Load and initialise the browser engine.
 *
 * @param {(message: string) => void} [onStatus] progress callback; receives
 *   the engine's own stage messages ("Booting Pyodide runtime...", etc).
 * @returns {Promise<{status: string, engineVersion: string|null, pyodideVersion: string|null}>}
 */
export const initializeCdnEngine = (onStatus = () => {}) => {
  if (!enginePromise) {
    enginePromise = (async () => {
      if (typeof document === 'undefined') {
        throw new Error('The browser calculation engine needs a DOM; it cannot run here.')
      }

      onStatus('Loading Pyodide runtime...')
      await loadScript(getPyodideUrl())

      onStatus('Loading 3psLCCA calculation engine...')
      await loadScript(getEngineUrl(), { integrity: getEngineIntegrity() })

      const engine = globalThis.ThreePsLccaCore
      if (!engine) {
        throw new Error('The calculation engine script loaded but did not register ThreePsLccaCore.')
      }

      pyodideRuntime = await engine.init(onStatus)
      const state = engine.getState()
      return {
        status: 'ready',
        engineVersion: state.packageVersion || null,
        pyodideVersion: state.pyodideVersion || null,
      }
    })()
  }

  return enginePromise.catch((error) => {
    // Allow a later retry (e.g. after the network comes back).
    enginePromise = undefined
    pyodideRuntime = undefined
    throw error
  })
}

/** The Pyodide runtime the engine booted, once initialised. */
export const getPyodideRuntime = () => pyodideRuntime

/** Progress snapshot, safe to call before or during initialisation. */
export const getCdnEngineState = () => {
  const engine = globalThis.ThreePsLccaCore
  if (!engine) return { stage: enginePromise ? 'loading-scripts' : 'idle' }
  return engine.getState()
}

export const isCdnEngineReady = () => Boolean(globalThis.ThreePsLccaCore?.isReady?.())

/** Test seam: forget the cached engine so the next call re-initialises. */
export const resetCdnEngine = () => {
  enginePromise = undefined
  pyodideRuntime = undefined
}

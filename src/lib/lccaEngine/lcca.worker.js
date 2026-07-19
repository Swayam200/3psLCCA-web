import adapterSource from '../../wasm/python/web_to_core.py?raw'
import bridgeSource from '../../wasm/python/bridge.py?raw'
import wpiDatabase from '../../data/wpi_db.json'

let pyodide
let bridgeReady

const appBaseUrl = new URL(import.meta.env.BASE_URL, self.location.href)
const assetUrl = (path) => new URL(path, appBaseUrl).href

const DEFAULT_WHEEL_CDN = 'https://swayam200.github.io/3psLCCA-core/wasm-demo/'
const CDN_TIMEOUT_MS = 10_000

// undefined -> use the default CDN; empty string -> CDN disabled (bundled-only).
const resolveCdnBase = (configured, fallback) => {
  if (configured === undefined) return fallback
  const trimmed = String(configured).trim()
  if (!trimmed) return ''
  return trimmed.endsWith('/') ? trimmed : `${trimmed}/`
}

const withTimeout = (promise, label) => Promise.race([
  promise,
  new Promise((_, reject) => setTimeout(
    () => reject(new Error(`${label} timed out after ${CDN_TIMEOUT_MS / 1000}s.`)),
    CDN_TIMEOUT_MS,
  )),
])

const sha256Hex = async (buffer) => {
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

const fetchVerifiedWheel = async (url, expectedSha256, { timeout = false } = {}) => {
  const download = fetch(url).then(async (response) => {
    if (!response.ok) {
      throw new Error(`Wheel download failed (${response.status}) from ${url}.`)
    }
    return response.arrayBuffer()
  })
  const buffer = await (timeout ? withTimeout(download, `Wheel download from ${url}`) : download)
  const actualSha256 = await sha256Hex(buffer)
  if (actualSha256 !== expectedSha256) {
    throw new Error(`Wheel checksum mismatch from ${url}.`)
  }
  return buffer
}

const loadPyodideRuntime = async (cdnBase) => {
  if (cdnBase) {
    try {
      const { loadPyodide } = await withTimeout(
        import(/* @vite-ignore */ `${cdnBase}pyodide.mjs`),
        `Pyodide download from ${cdnBase}`,
      )
      return { runtime: await loadPyodide({ indexURL: cdnBase }), source: 'cdn' }
    } catch (error) {
      console.warn(`[lcca-wasm] CDN Pyodide load failed (${error.message}); using the bundled runtime.`)
    }
  }
  const { loadPyodide } = await import(/* @vite-ignore */ assetUrl('pyodide/pyodide.mjs'))
  return { runtime: await loadPyodide({ indexURL: assetUrl('pyodide/') }), source: 'bundled' }
}

const installCoreWheel = async (manifest, cdnBase) => {
  if (cdnBase) {
    try {
      const buffer = await fetchVerifiedWheel(`${cdnBase}${manifest.wheel}`, manifest.sha256, { timeout: true })
      await pyodide.unpackArchive(buffer, 'wheel')
      return 'cdn'
    } catch (error) {
      console.warn(`[lcca-wasm] CDN wheel load failed (${error.message}); using the bundled wheel.`)
    }
  }
  const buffer = await fetchVerifiedWheel(assetUrl(`lcca-wasm/${manifest.wheel}`), manifest.sha256)
  await pyodide.unpackArchive(buffer, 'wheel')
  return 'bundled'
}

const postStatus = (state) => self.postMessage({ type: 'status', state })

const initialize = async (options = {}) => {
  if (bridgeReady) return bridgeReady

  bridgeReady = (async () => {
    postStatus('loading-runtime')
    const manifestResponse = await fetch(assetUrl('lcca-wasm/manifest.json'))
    if (!manifestResponse.ok) {
      throw new Error(`Unable to load the LCCA Wasm manifest (${manifestResponse.status}).`)
    }
    const manifest = await manifestResponse.json()

    const cdnDisabled = Boolean(options.disableCdn)
    const pyodideCdn = cdnDisabled ? '' : resolveCdnBase(
      import.meta.env.VITE_LCCA_PYODIDE_CDN,
      `https://cdn.jsdelivr.net/pyodide/v${manifest.pyodideVersion}/full/`,
    )
    const wheelCdn = cdnDisabled ? '' : resolveCdnBase(
      import.meta.env.VITE_LCCA_WHEEL_CDN,
      DEFAULT_WHEEL_CDN,
    )

    const { runtime, source: pyodideSource } = await loadPyodideRuntime(pyodideCdn)
    pyodide = runtime

    postStatus('loading-core')
    const wheelSource = await installCoreWheel(manifest, wheelCdn)

    pyodide.globals.set('_lcca_adapter_source', adapterSource)
    pyodide.globals.set('_lcca_bridge_source', bridgeSource)
    pyodide.globals.set('_lcca_wpi_database_json', JSON.stringify(wpiDatabase))
    await pyodide.runPythonAsync(`
import sys
import types

lcca_web_adapter = types.ModuleType("lcca_web_adapter")
lcca_web_adapter.__file__ = "lcca_web_adapter.py"
sys.modules["lcca_web_adapter"] = lcca_web_adapter
exec(compile(_lcca_adapter_source, "lcca_web_adapter.py", "exec"), lcca_web_adapter.__dict__)

lcca_web_bridge = types.ModuleType("lcca_web_bridge")
lcca_web_bridge.__file__ = "lcca_web_bridge.py"
sys.modules["lcca_web_bridge"] = lcca_web_bridge
exec(compile(_lcca_bridge_source, "lcca_web_bridge.py", "exec"), lcca_web_bridge.__dict__)
lcca_web_bridge.initialize(_lcca_wpi_database_json)

del _lcca_adapter_source
del _lcca_bridge_source
del _lcca_wpi_database_json
`)
    postStatus('ready')
    return {
      status: 'ready',
      coreVersion: manifest.coreVersion,
      pyodideVersion: manifest.pyodideVersion,
      assetSources: { pyodide: pyodideSource, wheel: wheelSource },
    }
  })()

  try {
    return await bridgeReady
  } catch (error) {
    bridgeReady = undefined
    pyodide = undefined
    postStatus('failed')
    throw error
  }
}

const callBridge = async (method, payload) => {
  await initialize()
  pyodide.globals.set('_lcca_request_json', JSON.stringify({
    project: payload.project,
    analysis_period_years: payload.analysisPeriodYears,
  }))
  try {
    const response = await pyodide.runPythonAsync(
      `lcca_web_bridge.${method}(_lcca_request_json)`,
    )
    return JSON.parse(response)
  } finally {
    pyodide.globals.delete('_lcca_request_json')
  }
}

self.addEventListener('message', async (event) => {
  const { id, type, payload } = event.data
  try {
    let result
    if (type === 'initialize') result = await initialize(payload)
    else if (type === 'calculate') result = await callBridge('calculate', payload)
    else if (type === 'validate') result = await callBridge('validate', payload)
    else throw new Error(`Unsupported LCCA worker request: ${type}`)
    self.postMessage({ id, type: 'result', result })
  } catch (error) {
    self.postMessage({
      id,
      type: 'error',
      error: {
        name: error?.name || 'Error',
        message: error?.message || String(error),
        stack: error?.stack || '',
      },
    })
  }
})

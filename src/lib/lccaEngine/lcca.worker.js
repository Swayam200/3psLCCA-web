import adapterSource from '../../wasm/python/web_to_core.py?raw'
import bridgeSource from '../../wasm/python/bridge.py?raw'
import wpiDatabase from '../../data/wpi_db.json'

let pyodide
let bridgeReady

const appBaseUrl = new URL(import.meta.env.BASE_URL, self.location.href)
const assetUrl = (path) => new URL(path, appBaseUrl).href

const postStatus = (state) => self.postMessage({ type: 'status', state })

const initialize = async () => {
  if (bridgeReady) return bridgeReady

  bridgeReady = (async () => {
    postStatus('loading-runtime')
    const { loadPyodide } = await import(/* @vite-ignore */ assetUrl('pyodide/pyodide.mjs'))
    pyodide = await loadPyodide({ indexURL: assetUrl('pyodide/') })

    postStatus('loading-core')
    const manifestResponse = await fetch(assetUrl('lcca-wasm/manifest.json'))
    if (!manifestResponse.ok) {
      throw new Error(`Unable to load the LCCA Wasm manifest (${manifestResponse.status}).`)
    }
    const manifest = await manifestResponse.json()
    await pyodide.loadPackage(assetUrl(`lcca-wasm/${manifest.wheel}`))

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
    if (type === 'initialize') result = await initialize()
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

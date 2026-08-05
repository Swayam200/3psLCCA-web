/**
 * Browser calculation engine.
 *
 * Runs LCCA calculations entirely in the browser: the published
 * 3psLCCA-core engine boots Pyodide and installs the core wheel (cdnEngine),
 * and this module loads the *same* web->core adapter the FastAPI backend uses
 * into that runtime. Requests and responses therefore match the backend's
 * contract exactly, so callers cannot tell the two apart.
 */
import adapterSource from '../../../backend/app/adapters/web_to_core.py?raw'
import bridgeSource from './bridge.py?raw'
import wpiDatabase from '../../data/wpi_db.json'
import { getPyodideRuntime, initializeCdnEngine, resetCdnEngine } from './cdnEngine.js'

const INSTALL_BRIDGE = `
import sys
import types

_module = types.ModuleType("lcca_web_bridge")
_module.__file__ = "lcca_web_bridge.py"
sys.modules["lcca_web_bridge"] = _module
exec(compile(_lcca_bridge_source, "lcca_web_bridge.py", "exec"), _module.__dict__)
del _module
`

const START_BRIDGE = `
import lcca_web_bridge
lcca_web_bridge.initialize(_lcca_adapter_source, _lcca_wpi_json)
`

let readyPromise

/** Boot the engine and load the adapter into it (idempotent). */
export const initializeBrowserEngine = (onStatus = () => {}) => {
  if (!readyPromise) {
    readyPromise = (async () => {
      const engineInfo = await initializeCdnEngine(onStatus)
      const pyodide = getPyodideRuntime()
      if (!pyodide) {
        throw new Error('The calculation engine started but exposed no Python runtime.')
      }

      onStatus('Loading the 3psLCCA project adapter...')
      pyodide.globals.set('_lcca_bridge_source', bridgeSource)
      try {
        await pyodide.runPythonAsync(INSTALL_BRIDGE)
      } finally {
        pyodide.globals.delete('_lcca_bridge_source')
      }

      pyodide.globals.set('_lcca_adapter_source', adapterSource)
      pyodide.globals.set('_lcca_wpi_json', JSON.stringify(wpiDatabase))
      try {
        await pyodide.runPythonAsync(START_BRIDGE)
      } finally {
        pyodide.globals.delete('_lcca_adapter_source')
        pyodide.globals.delete('_lcca_wpi_json')
      }

      onStatus('Ready.')
      return { status: 'ready', ...engineInfo }
    })()
  }

  return readyPromise.catch((error) => {
    readyPromise = undefined
    throw error
  })
}

const callBridge = async (method, request) => {
  await initializeBrowserEngine(request?.onStatus)
  const pyodide = getPyodideRuntime()

  pyodide.globals.set('_lcca_request_json', JSON.stringify({
    project: request?.project ?? {},
    analysis_period_years: request?.analysisPeriodYears ?? 50,
    debug: false,
  }))
  try {
    const response = await pyodide.runPythonAsync(`lcca_web_bridge.${method}(_lcca_request_json)`)
    return JSON.parse(response)
  } finally {
    pyodide.globals.delete('_lcca_request_json')
  }
}

export const calculateLcca = (request) => callBridge('calculate', request)
export const validateLcca = (request) => callBridge('validate', request)

/** Test seam: drop the cached runtime so the next call re-initialises. */
export const resetBrowserEngine = () => {
  readyPromise = undefined
  resetCdnEngine()
}

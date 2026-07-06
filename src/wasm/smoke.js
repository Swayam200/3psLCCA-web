import {
  calculateLcca,
  getLccaEngineStatus,
  initializeLccaEngine,
} from '../lib/lccaApi.js'
import project from '../../tests/fixtures/global-project.json'

const statusElement = document.querySelector('#status')
const resultElement = document.querySelector('#result')

const compareValues = (nativeValue, wasmValue, path = 'result') => {
  if (typeof nativeValue === 'number' && typeof wasmValue === 'number') {
    const difference = Math.abs(nativeValue - wasmValue)
    const tolerance = Math.max(1e-6, 1e-9 * Math.max(Math.abs(nativeValue), Math.abs(wasmValue)))
    if (difference > tolerance) {
      throw new Error(`Numeric parity failed at ${path}: ${nativeValue} != ${wasmValue}`)
    }
    return
  }
  if (Array.isArray(nativeValue) && Array.isArray(wasmValue)) {
    if (nativeValue.length !== wasmValue.length) {
      throw new Error(`Array length mismatch at ${path}.`)
    }
    nativeValue.forEach((value, index) => compareValues(value, wasmValue[index], `${path}[${index}]`))
    return
  }
  if (nativeValue && wasmValue && typeof nativeValue === 'object' && typeof wasmValue === 'object') {
    const nativeKeys = Object.keys(nativeValue).sort()
    const wasmKeys = Object.keys(wasmValue).sort()
    if (JSON.stringify(nativeKeys) !== JSON.stringify(wasmKeys)) {
      throw new Error(`Object structure mismatch at ${path}.`)
    }
    nativeKeys.forEach((key) => compareValues(nativeValue[key], wasmValue[key], `${path}.${key}`))
    return
  }
  if (nativeValue !== wasmValue) {
    throw new Error(`Value mismatch at ${path}: ${nativeValue} != ${wasmValue}`)
  }
}

try {
  const initialized = await initializeLccaEngine()
  const response = await calculateLcca({
    project,
    analysisPeriodYears: 50,
  })
  if (response.status !== 'success') {
    throw new Error(response.validation?.errors?.join(' ') || 'Calculation failed.')
  }
  const baseUrl = new URL(import.meta.env.BASE_URL, window.location.href)
  const nativeReference = await fetch(new URL('lcca-wasm/reference-global.json', baseUrl))
    .then((result) => result.json())
  compareValues(nativeReference, response)
  const repeatResponse = await calculateLcca({ project, analysisPeriodYears: 50 })
  compareValues(response, repeatResponse, 'repeatGlobalResult')

  const [indiaProject, indiaReference] = await Promise.all([
    fetch(new URL('lcca-wasm/project-india.json', baseUrl)).then((result) => result.json()),
    fetch(new URL('lcca-wasm/reference-india.json', baseUrl)).then((result) => result.json()),
  ])
  const indiaResponse = await calculateLcca({
    project: indiaProject,
    analysisPeriodYears: 50,
  })
  compareValues(indiaReference, indiaResponse, 'indiaResult')

  statusElement.dataset.status = 'success'
  statusElement.textContent = 'WebAssembly calculation completed successfully with native parity.'
  resultElement.textContent = JSON.stringify({
    initialized,
    engine: await getLccaEngineStatus(),
    initialRoadUserCost: response.results.initial_stage.social.initial_road_user_cost,
    nativeParity: true,
    indiaParity: true,
    repeatStable: true,
    source: 'wasm',
  }, null, 2)
} catch (error) {
  statusElement.dataset.status = 'error'
  statusElement.textContent = `WebAssembly calculation failed: ${error.message}`
  resultElement.textContent = error.stack || String(error)
}

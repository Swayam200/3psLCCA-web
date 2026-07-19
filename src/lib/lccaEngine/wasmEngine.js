let worker
let nextRequestId = 1
let initializePromise
let status = { state: 'idle', mode: 'wasm' }
// After a failed initialization, retry without CDN sources so a flaky CDN
// cannot wedge the engine in a fail-retry loop.
let disableCdn = false
const pending = new Map()

const rejectPending = (error) => {
  for (const { reject } of pending.values()) reject(error)
  pending.clear()
}

const resetWorker = (error) => {
  worker?.terminate()
  worker = undefined
  initializePromise = undefined
  status = { state: 'failed', mode: 'wasm', error: error?.message || String(error) }
  rejectPending(error)
}

const ensureWorker = () => {
  if (worker) return worker

  worker = new Worker(new URL('./lcca.worker.js', import.meta.url), { type: 'module' })
  worker.addEventListener('message', (event) => {
    const message = event.data
    if (message.type === 'status') {
      status = { state: message.state, mode: 'wasm' }
      return
    }
    const request = pending.get(message.id)
    if (!request) return
    pending.delete(message.id)
    if (message.type === 'error') {
      const error = new Error(message.error.message)
      error.name = message.error.name
      error.stack = message.error.stack || error.stack
      request.reject(error)
    } else {
      request.resolve(message.result)
    }
  })
  worker.addEventListener('error', (event) => {
    resetWorker(new Error(event.message || 'The LCCA WebAssembly worker stopped unexpectedly.'))
  })
  return worker
}

const request = (type, payload = {}) => new Promise((resolve, reject) => {
  const id = nextRequestId++
  pending.set(id, { resolve, reject })
  ensureWorker().postMessage({ id, type, payload })
})

export const initializeLccaEngine = () => {
  if (!initializePromise) {
    initializePromise = request('initialize', { disableCdn }).then((result) => {
      status = { state: 'ready', mode: 'wasm', ...result }
      return result
    }).catch((error) => {
      disableCdn = true
      resetWorker(error)
      throw error
    })
  }
  return initializePromise
}

const run = async (type, payload) => {
  await initializeLccaEngine()
  status = { ...status, state: 'calculating' }
  try {
    return await request(type, payload)
  } catch (error) {
    resetWorker(error)
    throw error
  } finally {
    if (worker) status = { ...status, state: 'ready' }
  }
}

export const calculateLcca = (payload) => run('calculate', payload)
export const validateLcca = (payload) => run('validate', payload)
export const getLccaEngineStatus = () => ({ ...status })
export const terminateLccaEngine = () => {
  if (worker) worker.terminate()
  worker = undefined
  initializePromise = undefined
  status = { state: 'idle', mode: 'wasm' }
  rejectPending(new Error('The LCCA WebAssembly engine was terminated.'))
}
export const getLccaEngineDescription = () => 'browser WebAssembly'

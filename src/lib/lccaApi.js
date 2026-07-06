const configuredMode = String(import.meta.env.VITE_LCCA_ENGINE || 'wasm').toLowerCase()
const mode = import.meta.env.DEV && configuredMode === 'backend' ? 'backend' : 'wasm'
const engine = mode === 'backend'
    ? import('./lccaEngine/backendEngine.js')
    : import('./lccaEngine/wasmEngine.js')

export const initializeLccaEngine = async () => (await engine).initializeLccaEngine()
export const calculateLcca = async (request) => (await engine).calculateLcca(request)
export const validateLcca = async (request) => (await engine).validateLcca(request)
export const getLccaEngineStatus = async () => (await engine).getLccaEngineStatus()
export const terminateLccaEngine = async () => (await engine).terminateLccaEngine()
export const getLccaEngineDescription = async () => (await engine).getLccaEngineDescription()
export const getLccaEngineMode = () => mode

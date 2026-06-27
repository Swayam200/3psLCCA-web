const LCCA_API_BASE = (import.meta.env.VITE_LCCA_API_URL || 'http://localhost:8000').replace(/\/$/, '')

const requestJson = async (path, payload) => {
  const response = await fetch(`${LCCA_API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    throw new Error(`Backend request failed with HTTP ${response.status}.`)
  }
  return response.json()
}

export const initializeLccaEngine = async () => ({ status: 'ready' })
export const calculateLcca = (request) => requestJson('/api/lcca/calculate', {
  project: request.project,
  analysis_period_years: request.analysisPeriodYears,
  debug: false,
})
export const validateLcca = (request) => requestJson('/api/lcca/validate', {
  project: request.project,
  analysis_period_years: request.analysisPeriodYears,
  debug: false,
})
export const getLccaEngineStatus = () => ({ state: 'ready', mode: 'backend' })
export const terminateLccaEngine = () => {}
export const getLccaEngineDescription = () => `development backend (${LCCA_API_BASE})`

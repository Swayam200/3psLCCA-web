/**
 * LCCA calculation API client.
 *
 * Calculations run on the FastAPI backend (see backend/README.md), which
 * wraps the `three_ps_lcca_core` Python engine. Configure the backend URL
 * with VITE_LCCA_API_URL (defaults to http://localhost:8000).
 */
const LCCA_API_BASE = (import.meta.env.VITE_LCCA_API_URL || 'http://localhost:8000').replace(/\/$/, '')

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
export const getLccaEngineStatus = async () => ({ state: 'ready', mode: 'backend' })
export const terminateLccaEngine = () => {}
export const getLccaEngineDescription = async () => `calculation backend (${LCCA_API_BASE})`
export const getLccaEngineMode = () => 'backend'

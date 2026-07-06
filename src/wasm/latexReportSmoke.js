import { calculateLcca, getLccaEngineStatus } from '../lib/lccaApi.js'
import { buildCalculationProjectInputs } from '../utils/projectDerivations.js'
import {
  buildLatexReportPayload,
  compileLatexReportPdf,
} from '../gui/components/outputs/latexReportEngine.js'
import { SECTION_KEYS } from '../gui/components/outputs/reportSections.js'
import project from '../../tests/fixtures/global-project.json'

const statusElement = document.querySelector('#status')
const resultElement = document.querySelector('#result')

const setStatus = (status, message) => {
  statusElement.dataset.status = status
  statusElement.textContent = message
}

const allSectionsSelected = () => Object.fromEntries(
  Object.values(SECTION_KEYS).map((key) => [key, true]),
)

const appendLog = (lines, message) => {
  lines.push(message)
  resultElement.textContent = JSON.stringify({ progress: lines }, null, 2)
}

try {
  const progress = []
  appendLog(progress, 'Calculating fixture through Browser WebAssembly...')

  const response = await calculateLcca({
    project,
    analysisPeriodYears: 50,
  })
  if (response.status !== 'success') {
    throw new Error(response.validation?.errors?.join(' ') || 'Wasm calculation failed.')
  }

  appendLog(progress, 'Building desktop-style LaTeX report payload...')
  const payload = buildLatexReportPayload({
    projectInputs: buildCalculationProjectInputs(project),
    results: response.results,
    computedData: response.computedData || response.computed_data || {},
    selections: allSectionsSelected(),
    calculationMetadata: {
      source: 'wasm',
      coreVersion: response.coreVersion || response.core_version || 'unknown',
      pyodideVersion: response.pyodideVersion || response.pyodide_version || '314.0.0',
      calculated_at: new Date('2026-06-24T00:00:00.000Z').toISOString(),
    },
    fileName: 'swiftlatex-real-report-smoke.pdf',
  })

  appendLog(progress, 'Compiling generated report through SwiftLaTeX worker...')
  const compiled = await compileLatexReportPdf({
    tex: payload.tex,
    fileName: payload.fileName,
    timeoutMs: 120_000,
    onStatus: (message) => appendLog(progress, message),
  })

  const engineStatus = await getLccaEngineStatus()
  const result = {
    source: 'wasm',
    calculationEngine: engineStatus.engine,
    reportEngine: compiled.engine,
    texliveMode: compiled.texliveMode,
    pdfBytes: compiled.arrayBuffer.byteLength,
    texHasWasmProvenance: payload.tex.includes('Calculation engine & wasm'),
    texHasLccaResults: payload.tex.includes('Life Cycle Cost Analysis Results'),
    swiftlatexLogHasOutput: /Output written on main\.pdf/.test(compiled.log),
  }

  if (result.pdfBytes <= 0 || !result.texHasWasmProvenance || !result.texHasLccaResults) {
    throw new Error('SwiftLaTeX report smoke test compiled, but the result proof was incomplete.')
  }

  setStatus('success', 'Real 3psLCCA report compiled successfully through Browser WebAssembly + SwiftLaTeX.')
  resultElement.textContent = JSON.stringify(result, null, 2)
} catch (error) {
  setStatus('error', `SwiftLaTeX real report smoke test failed: ${error.message}`)
  resultElement.textContent = JSON.stringify({
    message: error.message,
    hasPdf: error.hasPdf,
    stack: error.stack,
    log: error.log,
  }, null, 2)
}

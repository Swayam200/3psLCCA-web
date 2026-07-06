import test from 'node:test'
import assert from 'node:assert/strict'

import { buildCalculationProjectInputs } from '../src/utils/projectDerivations.js'
import { computeAllSummaries } from '../src/gui/components/outputs/lifecycleSummary.js'
import { generateFullReport } from '../src/gui/components/outputs/reportGenerator.js'
import { SECTION_KEYS } from '../src/gui/components/outputs/reportSections.js'
import projectFixture from './fixtures/global-project.json' with { type: 'json' }

const results = {
  initial_stage: {
    economic: { initial_construction_cost: 300_000, time_cost_of_loan: 10_000 },
    environmental: { initial_material_carbon_emission_cost: 54 },
    social: { initial_road_user_cost: 25_000 },
  },
  use_stage: { economic: {}, environmental: {}, social: {} },
  reconstruction: { economic: {}, environmental: {}, social: {} },
  end_of_life: {
    economic: { total_demolition_and_disposal_costs: 30_000, total_scrap_value: 5_000 },
    environmental: {},
    social: {},
  },
}

test('report PDF contains canonical project sections and Wasm provenance', async () => {
  const project = structuredClone(projectFixture)
  project.general_info = {
    project_name: 'PDF Regression Bridge',
    project_code: 'PDF-01',
    project_currency: 'INR',
  }
  project.bridge_data = { ...project.bridge_data, span: 120, num_lanes: 2 }
  const selections = Object.fromEntries(Object.values(SECTION_KEYS).map((key) => [key, true]))

  const generated = await generateFullReport(
    buildCalculationProjectInputs(project),
    results,
    computeAllSummaries(results),
    () => {},
    [],
    null,
    selections,
    {
      source: 'wasm',
      coreVersion: 'test-core',
      pyodideVersion: '314.0.0',
      calculated_at: '2026-06-24T00:00:00Z',
    },
    { save: false, returnArrayBuffer: true },
  )

  const pdfText = Buffer.from(generated.arrayBuffer).toString('latin1')
  assert.ok(generated.arrayBuffer.byteLength > 20_000)
  assert.match(pdfText, /PDF Regression Bridge/)
  assert.match(pdfText, /Construction Data/)
  assert.match(pdfText, /Calculation engine: wasm/)
})

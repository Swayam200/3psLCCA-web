import test from 'node:test'
import assert from 'node:assert/strict'

import { buildCalculationProjectInputs } from '../src/utils/projectDerivations.js'
import { buildReportModel } from '../src/gui/components/outputs/reportModel.js'
import project from './fixtures/global-project.json' with { type: 'json' }

test('report model connects canonical web data to desktop-equivalent sections', () => {
  const populated = structuredClone(project)
  populated.general_info = {
    project_name: 'Report Bridge',
    project_code: 'RB-01',
    project_description: 'A fully linked report fixture.',
    project_currency: 'INR',
  }
  populated.bridge_data = {
    ...populated.bridge_data,
    span: 120,
    carriageway_width: 7.5,
    num_lanes: 2,
  }
  populated.transport_data = {
    vehicles: [{
      vehicle: { name: 'Truck', capacity: 10, gross_weight: 16, empty_weight: 6, emission_factor: 1.2 },
      route: { origin: 'Depot', distance_km: 5 },
      materials: [{ uuid: 'foundation_data-foundation-1', kg_factor: 1 }],
    }],
  }

  const model = buildReportModel(buildCalculationProjectInputs(populated), {
    source: 'backend',
    coreVersion: 'test-core',
  })

  assert.equal(model.project.name, 'Report Bridge')
  assert.ok(model.bridgeRows.some(([label, value]) => label === 'Total span' && value === '120 m'))
  assert.equal(model.constructionRows.length, 2)
  assert.equal(model.constructionRows[0].material, 'Pile foundation')
  assert.ok(model.materialIncluded.length > 0)
  assert.equal(model.transportRows[0].vehicle, 'Truck')
  assert.equal(model.calculation.source, 'backend')
})

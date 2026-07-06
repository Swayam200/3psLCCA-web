import test from 'node:test';
import assert from 'node:assert/strict';

import { buildCalculationProjectInputs } from '../src/utils/projectDerivations.js';
import { computeAllSummaries } from '../src/gui/components/outputs/lifecycleSummary.js';
import { generateReport } from '../src/gui/components/outputs/reportEngine.js';
import { SECTION_KEYS } from '../src/gui/components/outputs/reportSections.js';
import projectFixture from './fixtures/global-project.json' with { type: 'json' };

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
};

test('report engine can explicitly use the jsPDF fallback without browser APIs', async () => {
  const project = structuredClone(projectFixture);
  project.general_info = {
    project_name: 'Report Engine Bridge',
    project_code: 'REP-01',
    project_currency: 'INR',
  };

  const selections = Object.fromEntries(Object.values(SECTION_KEYS).map((key) => [key, true]));
  const logs = [];

  const generated = await generateReport({
    projectInputs: buildCalculationProjectInputs(project),
    results,
    computedData: computeAllSummaries(results),
    addLog: (message) => logs.push(message),
    selections,
    calculationMetadata: {
      source: 'wasm',
      coreVersion: 'test-core',
      pyodideVersion: '314.0.0',
      calculated_at: '2026-06-24T00:00:00Z',
    },
    preferredEngine: 'jspdf',
    options: { save: false, returnArrayBuffer: true },
  });

  assert.equal(generated.engine, 'jspdf');
  assert.equal(generated.fallbackUsed, false);
  assert.equal(generated.fileName, 'Report_Engine_Bridge_Report.pdf');
  assert.ok(generated.arrayBuffer.byteLength > 20_000);
  assert.ok(logs.some((message) => message.includes('generated successfully')));
});

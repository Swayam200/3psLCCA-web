import test from 'node:test';
import assert from 'node:assert/strict';

import { buildCalculationProjectInputs } from '../src/utils/projectDerivations.js';
import { buildReportModel } from '../src/gui/components/outputs/reportModel.js';
import {
  buildDesktopStyleLatexReport,
  DESKTOP_REQUIRED_LATEX_PACKAGES,
  STATIC_SWIFTLATEX_PACKAGES,
} from '../src/gui/components/outputs/latexReport.js';
import { SECTION_KEYS } from '../src/gui/components/outputs/reportSections.js';
import projectFixture from './fixtures/global-project.json' with { type: 'json' };

test('desktop-equivalent LaTeX report uses the static SwiftLaTeX package profile and Wasm provenance', () => {
  const project = structuredClone(projectFixture);
  project.general_info = {
    project_name: 'LaTeX Regression Bridge',
    project_code: 'TEX-01',
    project_currency: 'INR',
    project_country: 'India',
  };

  const report = buildReportModel(
    buildCalculationProjectInputs(project),
    {
      source: 'wasm',
      coreVersion: 'test-core',
      pyodideVersion: '314.0.0',
      calculated_at: '2026-06-24T00:00:00Z',
    },
  );
  const selections = Object.fromEntries(Object.values(SECTION_KEYS).map((key) => [key, true]));
  const tex = buildDesktopStyleLatexReport({
    report,
    results: {
      initial_stage: {
        economic: { initial_construction_cost: 1000 },
      },
      reconstruction: {
        Note: 'Not applicable in this fixture.',
      },
    },
    computedData: {},
    selections,
  });

  for (const [packageName] of STATIC_SWIFTLATEX_PACKAGES) {
    assert.match(tex, new RegExp(`\\\\usepackage(?:\\[[^\\]]+\\])?\\{${packageName}\\}`));
  }

  for (const [packageName] of DESKTOP_REQUIRED_LATEX_PACKAGES) {
    assert.equal(typeof packageName, 'string');
  }

  assert.doesNotMatch(tex, /\\usepackage(?:\[[^\]]+\])?\{geometry\}/);
  assert.doesNotMatch(tex, /\\titleformat/);
  assert.doesNotMatch(tex, /LastPage/);

  assert.match(tex, /Bridge Life Cycle Cost Analysis Report/);
  assert.match(tex, /Prepared using:/);
  assert.match(tex, /LaTeX Regression Bridge/);
  assert.match(tex, /\\tableofcontents/);
  assert.match(tex, /Introduction to LCCA/);
  assert.match(tex, /Bridge geometry and description/);
  assert.match(tex, /Financial inputs/);
  assert.match(tex, /Life Cycle Cost Analysis Results/);
  assert.match(tex, /Appendix A: Assumptions/);
  assert.match(tex, /Appendix B: Calculation methodology/);
  assert.match(tex, /Appendix C: Miscellaneous data/);
  assert.match(tex, /Calculation engine & wasm/);
  assert.match(tex, /Pyodide version & 314\.0\.0/);
  assert.doesNotMatch(tex, /NaN/);
});

test('desktop-style LaTeX escapes user-entered special characters', () => {
  const report = buildReportModel({
    general_info: {
      project_name: 'A&B_50% Bridge',
      project_code: 'P#1',
      project_currency: 'INR',
    },
    bridge_data: {
      bridge_name: 'A&B_50% Bridge',
      location: 'North #1',
    },
  }, { source: 'wasm' });

  const tex = buildDesktopStyleLatexReport({
    report,
    selections: Object.fromEntries(Object.values(SECTION_KEYS).map((key) => [key, true])),
  });

  assert.match(tex, /A\\&B\\_50\\% Bridge/);
  assert.match(tex, /P\\#1/);
  assert.doesNotMatch(tex, /A&B_50% Bridge/);
});

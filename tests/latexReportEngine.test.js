import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { buildCalculationProjectInputs } from '../src/utils/projectDerivations.js';
import {
  buildLatexReportPayload,
  getSwiftLatexReportEngineConfig,
} from '../src/gui/components/outputs/latexReportEngine.js';
import { SECTION_KEYS } from '../src/gui/components/outputs/reportSections.js';
import projectFixture from './fixtures/global-project.json' with { type: 'json' };

const root = resolve(import.meta.dirname, '..');

test('LaTeX report engine builds a real report payload without invoking jsPDF', () => {
  const project = structuredClone(projectFixture);
  project.general_info = {
    project_name: 'Swift Report Bridge',
    project_code: 'SWIFT-01',
    project_currency: 'INR',
    project_country: 'India',
  };

  const payload = buildLatexReportPayload({
    projectInputs: buildCalculationProjectInputs(project),
    calculationMetadata: {
      source: 'wasm',
      coreVersion: 'test-core',
      pyodideVersion: '314.0.0',
      calculated_at: '2026-06-24T00:00:00Z',
    },
    selections: Object.fromEntries(Object.values(SECTION_KEYS).map((key) => [key, true])),
    results: {
      initial_stage: {
        economic: { initial_construction_cost: 1000 },
      },
    },
  });

  assert.equal(payload.engine, 'swiftlatex');
  assert.equal(payload.fileName, 'LCCA_LaTeX_Report.pdf');
  assert.match(payload.tex, /\\documentclass\[12pt,a4paper\]\{article\}/);
  assert.match(payload.tex, /Swift Report Bridge/);
  assert.match(payload.tex, /Calculation engine & wasm/);
  assert.doesNotMatch(payload.tex, /jsPDF/);
});

test('SwiftLaTeX report engine resolves static worker and local TeX assets', () => {
  const config = getSwiftLatexReportEngineConfig('/subdir/');

  assert.equal(config.workerUrl, '/subdir/swiftlatex-report-worker.js');
  assert.equal(config.swiftlatexBase, '/subdir/vendor/swiftlatex/');
  assert.equal(config.texliveMode, 'local');
});

test('SwiftLaTeX report worker is isolated from backend and compiles caller-provided TeX', () => {
  const worker = readFileSync(resolve(root, 'public/swiftlatex-report-worker.js'), 'utf8');

  assert.match(worker, /compile-latex/);
  assert.match(worker, /event\.data\.tex/);
  assert.match(worker, /new URL\('texlive\/', swiftlatexBaseUrl\)\.href/);
  assert.match(worker, /engine\.writeMemFSFile\('main\.tex', event\.data\.tex\)/);
  assert.doesNotMatch(worker, /FastAPI|backend|fetch\('/);
});

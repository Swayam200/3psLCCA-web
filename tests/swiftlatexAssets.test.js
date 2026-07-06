import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const vendorRoot = resolve(root, 'public/vendor/swiftlatex');

test('SwiftLaTeX POC vendors the minimal static browser engine assets', () => {
  const expectedFiles = [
    'PdfTeXEngine.js',
    'swiftlatexpdftex.js',
    'swiftlatexpdftex.wasm',
    'swiftlatexpdftex.fmt',
    'LICENSE',
    'README.md',
  ];

  for (const file of expectedFiles) {
    const path = resolve(vendorRoot, file);
    assert.equal(existsSync(path), true, `${file} should exist`);
    assert.ok(statSync(path).size > 0, `${file} should not be empty`);
  }

  const engineWrapper = readFileSync(resolve(vendorRoot, 'PdfTeXEngine.js'), 'utf8');
  assert.match(engineWrapper, /SWIFTLATEX_ENGINE_PATH/);

  const license = readFileSync(resolve(vendorRoot, 'LICENSE'), 'utf8');
  assert.match(license, /GNU AFFERO GENERAL PUBLIC LICENSE/);
});

test('SwiftLaTeX smoke page defaults to local/static TeXLive mode', () => {
  const page = readFileSync(resolve(root, 'public/swiftlatex-smoke.html'), 'utf8');
  const worker = readFileSync(resolve(root, 'public/swiftlatex-smoke-worker.js'), 'utf8');

  assert.match(page, /Local\/static only/);
  assert.match(page, /Remote SwiftLaTeX endpoint/);
  assert.match(worker, /texliveMode === 'remote'/);
  assert.match(worker, /new URL\('texlive\/', swiftlatexBaseUrl\)\.href/);
});

#!/usr/bin/env node
/**
 * Engine parity verifier.
 *
 * Proves that the in-browser calculation path (the published 3psLCCA-core
 * wheel running under Pyodide/WebAssembly, through src/lib/lccaEngine/
 * bridge.py and the shared adapter) produces the same numbers as the native
 * CPython backend, for both a global-mode and an India-mode project.
 *
 *   npm run verify:parity
 *
 * Needs network access (downloads the published wheel named inside the
 * release's 3pslccacore.js) and the backend venv (backend/.venv) for the
 * native reference. Exits non-zero on any mismatch.
 */
import { execFileSync } from 'node:child_process'
import { readFileSync, existsSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

const FIXTURES = [
  { name: 'global-mode project', path: 'tests/fixtures/global-project.json' },
  { name: 'india-mode project', path: 'tests/fixtures/india-project.json' },
]
const ANALYSIS_PERIOD_YEARS = 50
const REL_TOLERANCE = 1e-9
const ABS_TOLERANCE = 1e-6

// --- 1. The wheel under test: exactly what the published release ships. ---
const { getEngineUrl } = await import('../src/lib/lccaEngine/cdnEngine.js')
const engineUrl = getEngineUrl()
console.log(`engine release:  ${engineUrl}`)

const engineSource = await (await fetch(engineUrl)).text()
const wheelMatch = engineSource.match(/RELEASE_WHEEL_URL = "([^"]+\.whl)"/)
if (!wheelMatch) {
  console.error('Could not find RELEASE_WHEEL_URL inside the published engine script.')
  process.exit(1)
}
const wheelUrl = wheelMatch[1]
console.log(`published wheel: ${wheelUrl}`)

// --- 2. WebAssembly side: the wheel under Pyodide + the app's bridge. ---
const { loadPyodide } = await import('pyodide')
const pyodide = await loadPyodide()
console.log(`pyodide:         ${pyodide.version} (node)`)

await pyodide.loadPackage('micropip')
const micropip = pyodide.pyimport('micropip')
await micropip.install(wheelUrl)

pyodide.globals.set('_bridge_source', read('src/lib/lccaEngine/bridge.py'))
await pyodide.runPythonAsync(`
import sys, types
_m = types.ModuleType("lcca_web_bridge")
_m.__file__ = "lcca_web_bridge.py"
sys.modules["lcca_web_bridge"] = _m
exec(compile(_bridge_source, "lcca_web_bridge.py", "exec"), _m.__dict__)
`)
pyodide.globals.set('_adapter_source', read('backend/app/adapters/web_to_core.py'))
pyodide.globals.set('_wpi_json', read('src/data/wpi_db.json'))
await pyodide.runPythonAsync(`
import lcca_web_bridge
lcca_web_bridge.initialize(_adapter_source, _wpi_json)
`)

const wasmCalculate = async (project) => {
  pyodide.globals.set('_request_json', JSON.stringify({
    project,
    analysis_period_years: ANALYSIS_PERIOD_YEARS,
    debug: false,
  }))
  return JSON.parse(await pyodide.runPythonAsync('lcca_web_bridge.calculate(_request_json)'))
}

// --- 3. Native reference: the backend venv's CPython + the same adapter. ---
const nativePython = resolve(repoRoot, 'backend/.venv/bin/python')
if (!existsSync(nativePython)) {
  console.error(`Backend venv not found at ${nativePython} (see docs/backend-setup.md).`)
  process.exit(1)
}
const nativeCalculate = (fixturePath) => JSON.parse(execFileSync(nativePython, ['-c', `
import json, sys
sys.path.insert(0, 'backend')
from app.adapters.web_to_core import AdapterValidationError, calculate_project
project = json.load(open(${JSON.stringify(fixturePath)}))
try:
    out = {"status": "success", **calculate_project(project, ${ANALYSIS_PERIOD_YEARS}, debug=False)}
except AdapterValidationError as exc:
    out = {"status": "error", "results": {}, "computed": {},
           "validation": {"errors": exc.errors, "warnings": exc.warnings}}
print(json.dumps(out, allow_nan=False))
`], { cwd: repoRoot, encoding: 'utf8' }))

// --- 4. Compare. -----------------------------------------------------------
const diffs = []
const compare = (a, b, path) => {
  if (typeof a === 'number' && typeof b === 'number') {
    const tolerance = Math.max(ABS_TOLERANCE, REL_TOLERANCE * Math.max(Math.abs(a), Math.abs(b)))
    if (Math.abs(a - b) > tolerance) diffs.push(`${path}: wasm=${a} native=${b}`)
    return
  }
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) { diffs.push(`${path}: length ${a.length} vs ${b.length}`); return }
    a.forEach((item, index) => compare(item, b[index], `${path}[${index}]`))
    return
  }
  if (a && b && typeof a === 'object' && typeof b === 'object') {
    const keysA = Object.keys(a).sort()
    const keysB = Object.keys(b).sort()
    if (JSON.stringify(keysA) !== JSON.stringify(keysB)) {
      diffs.push(`${path}: keys [${keysA}] vs [${keysB}]`)
      return
    }
    keysA.forEach((key) => compare(a[key], b[key], `${path}.${key}`))
    return
  }
  if (a !== b) diffs.push(`${path}: ${JSON.stringify(a)} vs ${JSON.stringify(b)}`)
}

let failed = false
for (const fixture of FIXTURES) {
  const project = JSON.parse(read(fixture.path))
  const wasm = await wasmCalculate(project)
  const native = nativeCalculate(fixture.path)

  const before = diffs.length
  compare(wasm, native, 'response')
  const problems = diffs.length - before

  const ruc = wasm.results?.initial_stage?.social?.initial_road_user_cost
  if (wasm.status !== 'success') {
    console.error(`FAIL  ${fixture.name}: wasm status=${wasm.status}`)
    failed = true
  } else if (problems > 0) {
    console.error(`FAIL  ${fixture.name}: ${problems} field(s) differ`)
    failed = true
  } else {
    console.log(`PASS  ${fixture.name} (initial RUC ${ruc})`)
  }
}

if (diffs.length > 0) {
  console.error('\nDifferences:')
  for (const diff of diffs.slice(0, 20)) console.error(`  ${diff}`)
}
process.exit(failed ? 1 : 0)

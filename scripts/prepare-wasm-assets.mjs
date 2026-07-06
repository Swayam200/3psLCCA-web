import { createHash } from 'node:crypto'
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from 'node:fs'
import { resolve } from 'node:path'
import { spawnSync } from 'node:child_process'

const projectRoot = resolve(import.meta.dirname, '..')
const possiblePaths = [
  process.env.LCCA_CORE_PATH,
  '../3psLCCA-gui-python-venv/3psLCCA-core',
  '../3psLCCA-gui Pip/3psLCCA-gui/3psLCCA-core',
  '../3psLCCA-core',
].filter(Boolean)

let coreRoot = null
for (const p of possiblePaths) {
  const resolvedPath = resolve(projectRoot, p)
  if (existsSync(resolvedPath)) {
    coreRoot = resolvedPath
    break
  }
}

if (!coreRoot) {
  throw new Error(`ERROR: Could not find 3psLCCA-core in any of the possible paths: ${possiblePaths.join(', ')}`)
}
const generatedRoot = resolve(projectRoot, '.wasm-assets')
const outputRoot = resolve(generatedRoot, 'lcca-wasm')
const wheelBuildRoot = resolve(generatedRoot, 'wheel-build')
const backendPython = resolve(projectRoot, 'backend/.venv/bin/python')
const python = process.env.LCCA_PYTHON || (
  process.platform !== 'win32' && existsSync(backendPython) ? backendPython : (process.platform === 'win32' ? 'python' : 'python3')
)

rmSync(generatedRoot, { recursive: true, force: true })
mkdirSync(outputRoot, { recursive: true })
mkdirSync(wheelBuildRoot, { recursive: true })

const build = spawnSync(
  python,
  ['-m', 'build', '--wheel', '--no-isolation', '--outdir', wheelBuildRoot, coreRoot],
  { cwd: projectRoot, encoding: 'utf8', env: process.env },
)

if (build.status !== 0) {
  process.stderr.write(build.stdout || '')
  process.stderr.write(build.stderr || '')
  throw new Error(
    `Unable to build 3psLCCA-core with ${python}. Install Python 3.12+, build, and setuptools-scm.`,
  )
}

const wheels = readdirSync(wheelBuildRoot).filter((name) => name.endsWith('.whl'))
if (wheels.length !== 1) {
  throw new Error(`Expected exactly one core wheel, found ${wheels.length}.`)
}

const wheel = wheels[0]
const wheelBytes = readFileSync(resolve(wheelBuildRoot, wheel))
const checksum = createHash('sha256').update(wheelBytes).digest('hex')
copyFileSync(resolve(wheelBuildRoot, wheel), resolve(outputRoot, wheel))

const reference = spawnSync(
  python,
  [
    resolve(projectRoot, 'scripts/generate-native-reference.py'),
    coreRoot,
    resolve(projectRoot, 'tests/fixtures/global-project.json'),
    resolve(projectRoot, 'src/data/wpi_db.json'),
    resolve(outputRoot, 'reference-global.json'),
    resolve(outputRoot, 'project-india.json'),
    resolve(outputRoot, 'reference-india.json'),
  ],
  { cwd: projectRoot, encoding: 'utf8', env: process.env },
)
if (reference.status !== 0) {
  process.stderr.write(reference.stdout || '')
  process.stderr.write(reference.stderr || '')
  throw new Error('Unable to generate the native CPython reference calculation.')
}

const pyodidePackage = JSON.parse(
  readFileSync(resolve(projectRoot, 'node_modules/pyodide/package.json'), 'utf8'),
)
const versionMatch = wheel.match(/^three_ps_lcca_core-(.+)-py3-none-any\.whl$/)

writeFileSync(
  resolve(outputRoot, 'manifest.json'),
  `${JSON.stringify({
    wheel,
    sha256: checksum,
    coreVersion: versionMatch?.[1] || 'unknown',
    pyodideVersion: pyodidePackage.version,
  }, null, 2)}\n`,
)

process.stdout.write(`Prepared ${wheel} for Pyodide ${pyodidePackage.version}.\n`)

import { readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { spawnSync } from 'node:child_process';

const root = resolve(import.meta.dirname, '..');
const suite = process.argv[2] || 'all';
const extraArgs = process.argv.slice(3);
const suites = {
    unit: ['unit'],
    integration: ['integration'],
    build: ['build'],
    all: ['unit', 'integration', 'build'],
    coverage: ['unit', 'integration', 'build'],
    report: ['integration/reportRuntime.test.js'],
};
if (!(suite in suites)) throw new Error(`Unknown suite: ${suite}`);

function run(args, env = process.env) {
    const result = spawnSync(process.execPath, args, { cwd: root, env, stdio: 'inherit' });
    if (result.error) throw result.error;
    if (result.status !== 0) process.exit(result.status ?? 1);
}

function collect(directory) {
    return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
        const path = join(directory, entry.name);
        return entry.isDirectory() ? collect(path) : entry.name.endsWith('.test.js') ? [path] : [];
    }).sort();
}

// Every entry point works on a fresh checkout, including an isolated report run.
run(['scripts/build-cscc-db.mjs']);
run(['scripts/build-report-runtime.mjs']);
const files = suites[suite].flatMap((name) => name.endsWith('.js') ? [join(root, 'tests', name)] : collect(join(root, 'tests', name)));
const coverageArgs = suite === 'coverage' ? ['--experimental-test-coverage', '--test-coverage-include=src/**'] : [];
run(['--test', ...coverageArgs, ...extraArgs, ...files], suite === 'report' ? { ...process.env, REPORT_RUNTIME_TEST: '1' } : process.env);
if (['all', 'coverage', 'integration'].includes(suite)) {
    run(['node_modules/vitest/vitest.mjs', 'run', ...(suite === 'coverage' ? ['--coverage'] : []), ...(suite === 'integration' ? ['tests/integration'] : [])]);
}

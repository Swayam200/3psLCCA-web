import { spawn } from 'node:child_process';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const env = { ...process.env, PORT: '4176', GEMINI_API_KEY: '', ANTHROPIC_API_KEY: '', AI_PROVIDER: '' };
const server = spawn(process.execPath, ['--import', './tests/helpers/demo-offline.mjs', 'ai-demo/server.js'], { cwd: root, env, stdio: ['ignore', 'pipe', 'pipe'] });
let serverError = '';
server.stderr.on('data', chunk => { serverError += chunk; });
try {
    await new Promise((resolveReady, reject) => {
        const timeout = setTimeout(() => reject(new Error('Demo test server did not start within 10 seconds.')), 10_000);
        const finish = callback => { clearTimeout(timeout); callback(); };
        server.once('error', error => finish(() => reject(error)));
        server.once('exit', code => finish(() => reject(new Error(`Demo test server exited (${code}): ${serverError}`))));
        server.stdout.on('data', chunk => {
            if (String(chunk).includes('3psLCCA AI demo')) finish(resolveReady);
        });
    });
    const child = spawn(process.execPath, ['--test', ...process.argv.slice(2), 'ai-demo/test.js'], { cwd: root, env, stdio: 'inherit' });
    const result = await new Promise((resolveExit, reject) => {
        child.once('error', reject);
        child.once('exit', code => resolveExit(code ?? 1));
    });
    process.exitCode = result;
} finally {
    server.kill();
}

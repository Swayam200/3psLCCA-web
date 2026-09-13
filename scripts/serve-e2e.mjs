import { build, preview } from 'vite';
import { spawnSync } from 'node:child_process';
import { resolve, join } from 'node:path';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';

const root = resolve(import.meta.dirname, '..');
for (const script of ['scripts/build-cscc-db.mjs', 'scripts/build-report-runtime.mjs']) {
    const result = spawnSync(process.execPath, [script], { cwd: root, stdio: 'inherit' });
    if (result.error) throw result.error;
    if (result.status !== 0) process.exit(result.status ?? 1);
}
// A dedicated server ignores local .env files and external-service settings.
// The app still runs its normal routing, forms, storage and report components.
const envKeys = ['VITE_APPWRITE_ENDPOINT', 'VITE_APPWRITE_PROJECT_ID', 'VITE_APPWRITE_DATABASE_ID', 'VITE_APPWRITE_COLLECTION_ID', 'VITE_AI_ENABLED', 'VITE_LCCA_ENGINE_URL', 'VITE_LCCA_ENGINE_SRI', 'VITE_LCCA_PYODIDE_URL'];
const define = Object.fromEntries(envKeys.map(key => [`import.meta.env.${key}`, JSON.stringify('')]));
define['import.meta.env.VITE_LCCA_ENGINE'] = JSON.stringify('backend');
define['import.meta.env.VITE_LCCA_API_URL'] = JSON.stringify('http://127.0.0.1:4175/mock-api');
const outDir = mkdtempSync(join(tmpdir(), '3pslcca-e2e-'));
const config = { root, envDir: false, base: '/3psLCCA-web/', define, build: { outDir, emptyOutDir: true } };
await build(config);
const server = await preview({ ...config, preview: { host: '127.0.0.1', port: 4175, strictPort: true } });
for (const signal of ['SIGINT', 'SIGTERM']) {
    process.once(signal, () => {
        server.httpServer.close(() => {
            rmSync(outDir, { recursive: true, force: true });
            process.exit(0);
        });
        server.httpServer.closeAllConnections();
    });
}

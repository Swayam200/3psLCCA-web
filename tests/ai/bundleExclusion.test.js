/**
 * The build-flag guarantee, enforced.
 *
 * With VITE_AI_ENABLED unset, the production bundle must contain no trace of
 * the AI package — not "the panel is hidden", but "the code does not ship".
 * With the flag set, the AI code must exist only in lazy chunks, never in the
 * entry bundle, so even flag-on users pay nothing until they open the panel.
 *
 * The mechanism under test: consumers gate their dynamic import() on an
 * INLINE `import.meta.env.VITE_AI_ENABLED === 'true'` comparison, which Vite
 * folds to a literal at build time, letting Rollup drop the dead branch.
 *
 * Sentinels: the storage keys ('3pslcca.ai') live in settings.js and reach
 * every bundle that includes the package; 'anthropic-version' lives in the
 * Claude provider.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readdirSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const SENTINELS = ['3pslcca.ai', 'anthropic-version'];

const buildAndScan = (env) => {
    const outDir = mkdtempSync(path.join(tmpdir(), 'lcca-ai-bundle-'));
    try {
        execFileSync('npx', ['vite', 'build', '--outDir', outDir], {
            env: { ...process.env, ...env },
            stdio: 'pipe',
            timeout: 180_000,
        });
        const assets = path.join(outDir, 'assets');
        const files = readdirSync(assets).filter((f) => f.endsWith('.js'));
        return files.map((file) => ({
            file,
            content: readFileSync(path.join(assets, file), 'utf8'),
        }));
    } finally {
        rmSync(outDir, { recursive: true, force: true });
    }
};

test('flag OFF: no AI code anywhere in the bundle', () => {
    const files = buildAndScan({ VITE_AI_ENABLED: '' });
    for (const { file, content } of files) {
        for (const sentinel of SENTINELS) {
            assert.ok(!content.includes(sentinel), `${sentinel} leaked into ${file}`);
        }
    }
});

test('flag ON: AI code exists, but only in lazy chunks — never the entry', () => {
    const files = buildAndScan({ VITE_AI_ENABLED: 'true' });
    const entry = files.find(({ file }) => file.startsWith('index-'));
    assert.ok(entry, 'entry bundle not found');
    for (const sentinel of SENTINELS) {
        assert.ok(!entry.content.includes(sentinel), `${sentinel} leaked into the entry bundle`);
    }
    const aiChunks = files.filter(({ content }) => content.includes('3pslcca.ai'));
    assert.ok(aiChunks.length >= 1, 'AI chunk missing from a flag-on build');
});

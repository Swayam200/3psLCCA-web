/**
 * Packs vendor/report-runtime + report-runtime/report_compat.py into
 * public/report/runtime.zip — the archive the browser report worker
 * unpacks into Pyodide's filesystem. Runs as predev/prebuild; output is
 * gitignored. Skips when up to date.
 */
import { createRequire } from 'node:module';
import { mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import process from 'node:process';

const require = createRequire(import.meta.url);
const JSZip = require('jszip');

const root = process.cwd();
const outDir = join(root, 'public', 'report');
const outPath = join(outDir, 'runtime.zip');

const sources = [
    [join(root, 'vendor', 'report-runtime'), ''],
    [join(root, 'report-runtime'), ''],
];

const collect = (dir, prefix, list) => {
    for (const entry of readdirSync(dir)) {
        const path = join(dir, entry);
        const st = statSync(path);
        if (st.isDirectory()) collect(path, prefix, list);
        else list.push({ path, rel: prefix + relative(sources.find(([s]) => path.startsWith(s))[0], path), mtime: st.mtimeMs });
    }
};

const files = [];
for (const [dir, prefix] of sources) collect(dir, prefix, files);

let outMtime = 0;
try {
    outMtime = statSync(outPath).mtimeMs;
} catch { /* absent */ }
const newest = Math.max(...files.map((f) => f.mtime), statSync(process.argv[1]).mtimeMs);
if (outMtime > newest && !process.argv.includes('--force')) {
    process.exit(0);
}

const zip = new JSZip();
for (const file of files.sort((a, b) => a.rel.localeCompare(b.rel))) {
    // Fixed date keeps the archive deterministic for caching.
    zip.file(file.rel, readFileSync(file.path), { date: new Date('2020-01-01T00:00:00Z') });
}
mkdirSync(outDir, { recursive: true });
const buffer = await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE', compressionOptions: { level: 9 } });
writeFileSync(outPath, buffer);
console.log(`report runtime: packed ${files.length} files → public/report/runtime.zip (${(buffer.length / 1048576).toFixed(1)} MB)`);

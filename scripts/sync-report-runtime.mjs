/**
 * Syncs the desktop report code into vendor/report-runtime/ (committed).
 *
 * The web report engine runs the desktop app's own Python report modules
 * (docs/report-latex-web-plan.md). This script copies the pure-Python
 * subtree of `three_ps_lcca_gui` — plus the two pure-Python deps not in
 * Pyodide's distribution (pylatex, ordered_set) and the few binary assets
 * the report references — from a local desktop checkout into the repo.
 *
 * Run manually whenever desktop's report code changes:
 *   node scripts/sync-report-runtime.mjs [--desktop <path>] [--site <path>]
 * Then review the diff and commit. The golden parity test
 * (npm run test:report) is the guard that a refresh didn't change output
 * unexpectedly.
 */
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { execSync } from 'node:child_process';
import { join, relative } from 'node:path';
import process from 'node:process';

const args = process.argv.slice(2);
const argValue = (flag, fallback) => {
    const idx = args.indexOf(flag);
    return idx >= 0 && args[idx + 1] ? args[idx + 1] : fallback;
};

const DESKTOP = argValue('--desktop', join(process.env.HOME || '', 'Developer', '3psLCCA-Desktop'));
const SITE_PACKAGES = argValue('--site', '/opt/miniconda3/envs/3pslcca/lib/python3.12/site-packages');
const SRC = join(DESKTOP, 'src', 'three_ps_lcca_gui');
const OUT = join(process.cwd(), 'vendor', 'report-runtime');

if (!existsSync(SRC)) {
    console.error(`desktop package not found at ${SRC} — pass --desktop <repo path>`);
    process.exit(1);
}

// Directories that are irrelevant to report generation and/or heavy.
const EXCLUDE_DIRS = new Set([
    '__pycache__',
    'cscc-database-2018-master', // 40 MB SCC db — web has its own per-country JSON pipeline
    'report-env',                // a bundled virtualenv
    'build',
    'material_database',         // SOR catalogs (~2.7 MB) — search concern, not report
    'doc_build',                 // built docs bundle inside doc_handler
]);

const copyPyTree = (from, to) => {
    let files = 0;
    const walk = (dir) => {
        for (const entry of readdirSync(dir)) {
            const path = join(dir, entry);
            const st = statSync(path);
            if (st.isDirectory()) {
                if (!EXCLUDE_DIRS.has(entry)) walk(path);
            } else if (entry.endsWith('.py') || entry.endsWith('.json')) {
                const dest = join(to, relative(from, path));
                mkdirSync(join(dest, '..'), { recursive: true });
                cpSync(path, dest);
                files += 1;
            }
        }
    };
    walk(from);
    return files;
};

rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });

const counts = {};
counts.three_ps_lcca_gui = copyPyTree(SRC, join(OUT, 'three_ps_lcca_gui'));
counts.pylatex = copyPyTree(join(SITE_PACKAGES, 'pylatex'), join(OUT, 'pylatex'));
counts.ordered_set = copyPyTree(join(SITE_PACKAGES, 'ordered_set'), join(OUT, 'ordered_set'));

// Binary assets the report references at run time.
const ASSETS = [
    'gui/assets/logo/3pslcca_header.png',            // page header logo
    'code_to_latex/pdf_generation_v3/images/image_1.png', // title-page artwork
    // The four Ubuntu faces plot_utils.register_fonts() loads — report plots
    // render text in Ubuntu, so these are output-relevant (unlike the rest
    // of the Qt theme assets, which stay unvendored).
    'gui/assets/themes/Ubuntu_font/Ubuntu-Light.ttf',
    'gui/assets/themes/Ubuntu_font/Ubuntu-Regular.ttf',
    'gui/assets/themes/Ubuntu_font/Ubuntu-Medium.ttf',
    'gui/assets/themes/Ubuntu_font/Ubuntu-Bold.ttf',
];
for (const rel of ASSETS) {
    const from = join(SRC, rel);
    if (existsSync(from)) {
        const dest = join(OUT, 'three_ps_lcca_gui', rel);
        mkdirSync(join(dest, '..'), { recursive: true });
        cpSync(from, dest);
        counts[rel] = 1;
    } else {
        console.warn(`asset missing in desktop checkout: ${rel}`);
    }
}
// Note: gui/assets/themes is deliberately NOT vendored — it holds Qt UI
// fonts/stylesheets. Plot colors resolve through the Python fallback theme
// tokens (proven byte-identical to the GUI's plots in the R0 spike).

let desktopCommit = 'unknown';
try {
    desktopCommit = execSync('git rev-parse HEAD', { cwd: DESKTOP, encoding: 'utf8' }).trim();
} catch { /* not a git checkout */ }

writeFileSync(join(OUT, 'RUNTIME_MANIFEST.json'), JSON.stringify({
    synced_at: new Date().toISOString(),
    desktop_repo: DESKTOP,
    desktop_commit: desktopCommit,
    files: counts,
}, null, 2));

console.log('synced vendor/report-runtime:', JSON.stringify(counts));

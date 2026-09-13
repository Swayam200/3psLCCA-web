import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

export const repoRoot = resolve(import.meta.dirname, '..');

export function getPython() {
    const python = process.env.LCCA_PYTHON || resolve(repoRoot, process.platform === 'win32' ? 'backend/.venv/Scripts/python.exe' : 'backend/.venv/bin/python');
    if (!process.env.LCCA_PYTHON && !existsSync(python)) {
        throw new Error('Backend environment not found. Follow tests/README.md or set LCCA_PYTHON to its Python executable.');
    }
    const check = spawnSync(python, ['-c', 'import three_ps_lcca_core'], { cwd: repoRoot, encoding: 'utf8' });
    if (check.error || check.status !== 0) {
        throw new Error(`Cannot import the core engine with ${python}. Install backend/requirements.txt (see tests/README.md).\n${check.error?.message || check.stderr}`);
    }
    return python;
}

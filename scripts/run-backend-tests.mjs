import { spawnSync } from 'node:child_process';
import { getPython, repoRoot } from './python-runtime.mjs';

const result = spawnSync(getPython(), ['-m', 'pytest', '-c', 'backend/pytest.ini', 'backend/tests', '-q', ...process.argv.slice(2)], { cwd: repoRoot, stdio: 'inherit' });
if (result.error) throw result.error;
process.exit(result.status ?? 1);

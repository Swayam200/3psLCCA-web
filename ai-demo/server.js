/**
 * 3psLCCA AI demo — zero-dependency Node HTTP server.
 *
 *   node server.js                                  → mock provider (offline)
 *   AI_PROVIDER=gemini GEMINI_API_KEY=... node server.js
 *   AI_PROVIDER=claude ANTHROPIC_API_KEY=... node server.js
 *
 * Serves the static UI from public/ and a small REST API over an in-memory
 * project. Nothing persists across restarts — this is a demo, not a service.
 */

import http from 'node:http';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
    getProject, getAuditLog, getSectionKeys, getSectionLabels, parameterSpecs,
    createMaterial, updateMaterial, deleteMaterial, restoreMaterial,
    setParameter, undoLast, resetProject, ValidationError,
} from './lib/store.js';
import { calculate } from './lib/lcca.js';
import { runPrompt, providerStatus, resolveSettings } from './lib/ai/index.js';
import { TOOLS } from './lib/ai/tools.js';
import { redact } from './lib/ai/redact.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT) || 4173;
const PUBLIC_DIR = path.join(__dirname, 'public');

const MIME = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.json': 'application/json; charset=utf-8',
};

const sendJson = (res, status, payload) => {
    const body = JSON.stringify(payload, null, 2);
    res.writeHead(status, {
        'Content-Type': 'application/json; charset=utf-8',
        'Content-Length': Buffer.byteLength(body),
        'Cache-Control': 'no-store',
    });
    res.end(body);
};

const readBody = (req) => new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (chunk) => {
        size += chunk.length;
        if (size > 1_000_000) { reject(new ValidationError('Request body too large.')); req.destroy(); return; }
        chunks.push(chunk);
    });
    req.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8');
        if (!raw) return resolve({});
        try { resolve(JSON.parse(raw)); } catch { reject(new ValidationError('Body is not valid JSON.')); }
    });
    req.on('error', reject);
});

// ---------------------------------------------------------------- keys -----
/**
 * A key pasted into the browser arrives in this header, is used for exactly one
 * upstream call, and is never written to disk, to a log, or to a response.
 */
const KEY_HEADER = 'x-provider-key';

const isLocalRequest = (req) => {
    const addr = req.socket.remoteAddress || '';
    return addr === '127.0.0.1' || addr === '::1' || addr === '::ffff:127.0.0.1';
};

/**
 * Guard against the worst way this demo could be misused: someone deploys it to
 * a public host, and it becomes an open proxy that accepts strangers' API keys.
 * Client-supplied keys are refused unless the request came from this machine.
 * Set ALLOW_REMOTE_KEYS=true to override deliberately.
 */
const clientKeyFrom = (req) => {
    const key = req.headers[KEY_HEADER];
    if (!key) return null;
    if (!isLocalRequest(req) && process.env.ALLOW_REMOTE_KEYS !== 'true') {
        throw new ValidationError(
            'This server only accepts a browser-supplied API key from localhost. '
            + 'Set ALLOW_REMOTE_KEYS=true to override (not recommended).',
        );
    }
    return String(key);
};

const settingsFrom = (req, body = {}) => ({
    provider: body.settings?.provider,
    mode: body.settings?.mode,
    model: body.settings?.model,
    apiKey: clientKeyFrom(req),
});

/** The full state the UI re-renders from after every mutation. */
const projectView = (settings) => {
    const project = getProject();
    return {
        project,
        sections: getSectionKeys().map((key) => ({
            key,
            label: getSectionLabels()[key],
            rows: project[key],
        })),
        parameters: parameterSpecs().map((spec) => ({
            ...spec,
            value: project.financial_data[spec.name],
        })),
        results: calculate(project),
        audit: getAuditLog().slice(0, 25),
        ai: providerStatus(settings),
    };
};

async function handleApi(req, res, url) {
    const { pathname } = url;
    const method = req.method;

    if (method === 'GET' && pathname === '/api/state') return sendJson(res, 200, projectView());

    // POST, not GET: the settings (and the key header) describe what to report
    // on, and a GET with a credential header is easier to leak via proxies.
    if (method === 'POST' && pathname === '/api/ai/status') {
        const settings = settingsFrom(req, await readBody(req));
        return sendJson(res, 200, {
            ...providerStatus(settings),
            tools: TOOLS.map((t) => ({ name: t.name, description: t.description })),
        });
    }

    /**
     * Validate a pasted key with one cheap real call, so the user finds out
     * here rather than on their first real prompt.
     */
    if (method === 'POST' && pathname === '/api/ai/test') {
        const settings = settingsFrom(req, await readBody(req));
        const resolved = resolveSettings(settings);
        if (!resolved.apiKey) {
            return sendJson(res, 200, { ok: false, error: 'No API key supplied.' });
        }
        try {
            const { generate } = await import(`./lib/ai/${resolved.provider}.js`);
            await generate('Reply using the answer tool with the word: ready.', {
                apiKey: resolved.apiKey,
                model: resolved.model,
            });
            return sendJson(res, 200, {
                ok: true,
                provider: resolved.provider,
                model: resolved.model,
            });
        } catch (error) {
            return sendJson(res, 200, {
                ok: false,
                error: redact(error.message, resolved.apiKey),
            });
        }
    }

    // ---- CRUD -------------------------------------------------------------
    const createMatch = pathname.match(/^\/api\/sections\/([\w]+)\/materials$/);
    if (method === 'POST' && createMatch) {
        const row = createMaterial(createMatch[1], await readBody(req), 'user');
        return sendJson(res, 201, { row, ...projectView() });
    }

    const rowMatch = pathname.match(/^\/api\/materials\/([\w-]+)$/);
    if (rowMatch) {
        const id = rowMatch[1];
        if (method === 'PATCH') {
            const row = updateMaterial({ id }, await readBody(req), 'user');
            return sendJson(res, 200, { row, ...projectView() });
        }
        if (method === 'DELETE') {
            const row = deleteMaterial({ id }, 'user');
            return sendJson(res, 200, { row, ...projectView() });
        }
    }

    const restoreMatch = pathname.match(/^\/api\/materials\/([\w-]+)\/restore$/);
    if (method === 'POST' && restoreMatch) {
        const row = restoreMaterial(restoreMatch[1], 'user');
        return sendJson(res, 200, { row, ...projectView() });
    }

    if (method === 'PATCH' && pathname === '/api/parameters') {
        const body = await readBody(req);
        const result = setParameter(body.name, body.value, 'user');
        return sendJson(res, 200, { result, ...projectView() });
    }

    if (method === 'POST' && pathname === '/api/calculate') {
        return sendJson(res, 200, calculate(getProject()));
    }

    if (method === 'POST' && pathname === '/api/undo') {
        const entry = undoLast();
        return sendJson(res, 200, { undone: entry, ...projectView() });
    }

    if (method === 'POST' && pathname === '/api/reset') {
        resetProject();
        return sendJson(res, 200, projectView());
    }

    // ---- AI ---------------------------------------------------------------
    if (method === 'POST' && pathname === '/api/ai/command') {
        const body = await readBody(req);
        const prompt = String(body.prompt || '').trim();
        if (!prompt) throw new ValidationError('"prompt" is required.');
        const settings = settingsFrom(req, body);
        const outcome = await runPrompt(prompt, settings);
        return sendJson(res, 200, { ...outcome, ...projectView(settings) });
    }

    return sendJson(res, 404, { error: `No route for ${method} ${pathname}` });
}

async function serveStatic(res, pathname) {
    const relative = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
    const filePath = path.join(PUBLIC_DIR, relative);
    // Never serve outside public/.
    if (!filePath.startsWith(PUBLIC_DIR)) {
        res.writeHead(403).end('Forbidden');
        return;
    }
    try {
        const content = await readFile(filePath);
        res.writeHead(200, {
            'Content-Type': MIME[path.extname(filePath)] || 'application/octet-stream',
            'Cache-Control': 'no-store',
        });
        res.end(content);
    } catch {
        res.writeHead(404, { 'Content-Type': 'text/plain' }).end('Not found');
    }
}

const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://${req.headers.host}`);
    try {
        if (url.pathname.startsWith('/api/')) return await handleApi(req, res, url);
        return await serveStatic(res, url.pathname);
    } catch (error) {
        const status = error instanceof ValidationError ? 400 : 500;
        // Redact before logging: an upstream failure can carry the key in its
        // message, and a server log is exactly where it must not land.
        if (status === 500) console.error(redact(error.stack || error.message));
        return sendJson(res, status, { error: redact(error.message) });
    }
});

server.listen(PORT, () => {
    const status = providerStatus();
    console.log(`\n  3psLCCA AI demo → http://localhost:${PORT}`);
    console.log(`  Mode: ${status.modeLabel}`);
    console.log(status.hasKey
        ? `  Key: loaded from ${status.keySource} (${status.keyFingerprint}) · ${status.providerLabel}`
        : '  Key: none — running on rules. Paste one in Settings (⚙), or set '
          + 'GEMINI_API_KEY / ANTHROPIC_API_KEY.');
    console.log('');
});

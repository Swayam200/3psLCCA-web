/**
 * Proxy provider — for deployments that keep API keys server-side.
 *
 * 3psLCCA-web ships as a static site, so out of the box the only way to use a
 * model is bring-your-own-key. An organisation that wants keys held centrally
 * instead points Settings → AI Assistant → "Proxy URL" at an endpoint it
 * runs, and the browser never sees a key at all.
 *
 * The contract the endpoint must implement (one route, JSON in/out):
 *
 *   POST <proxyUrl>
 *   {
 *     "prompt":   "<user's question>",
 *     "system":   "<system prompt>",          // built client-side
 *     "tools":    [ …tool declarations… ],     // JSON Schema, tools/schema.js
 *     "provider": "gemini" | "claude",         // advisory — the proxy may ignore it
 *     "model":    "<model id or empty>"
 *   }
 *   → 200 { "calls": [{ "name": "...", "args": { … } }], "usage": {…}?, "model": "…"? }
 *   → 4xx/5xx { "error": "<message safe to show the user>" }
 *
 * The proxy holds the key, calls its provider of choice, and maps the response
 * to the calls array. A reference implementation ships in Phase 4
 * (docs/ai-integration-plan.md); it is ~50 lines of FastAPI or a worker.
 */

const trimSlash = (url) => String(url || '').replace(/\/+$/, '');

export async function generate(prompt, { proxyUrl, provider, model, system, tools } = {}) {
    if (!proxyUrl) throw new Error('No proxy URL configured.');

    let response;
    try {
        response = await fetch(trimSlash(proxyUrl), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ prompt, system, tools, provider, model: model || '' }),
        });
    } catch {
        throw new Error(`Could not reach the AI proxy at ${trimSlash(proxyUrl)}.`);
    }

    let data = null;
    try { data = await response.json(); } catch { /* handled below */ }

    if (!response.ok) {
        throw new Error(data?.error || `AI proxy request failed with HTTP ${response.status}.`);
    }
    if (!Array.isArray(data?.calls)) {
        throw new Error('The AI proxy responded without a "calls" array — check its implementation.');
    }
    return { calls: data.calls, usage: data.usage || null, model: data.model || model || 'proxy' };
}

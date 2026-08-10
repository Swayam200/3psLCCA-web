/**
 * Provider router + the request pipeline.
 *
 * The pipeline is the thing worth copying into the real app:
 *
 *   prompt
 *     → resolve route            (rules? model? one then the other?)
 *     → generate()               (the ONLY non-deterministic step)
 *     → executeCalls()           (validated, funnels through the same CRUD as the UI)
 *     → calculate()              (deterministic engine, before and after)
 *     → { applied, rejected, before, after, delta, route }
 *
 * The model proposes; the application disposes. Numbers on screen are always
 * produced by the engine, never quoted by the model — which is what keeps a
 * hallucination from becoming a wrong cost estimate.
 */

import * as mock from './mock.js';
import * as gemini from './gemini.js';
import * as claude from './claude.js';
import { executeCalls } from './tools.js';
import { getProject } from '../store.js';
import { calculate } from '../lcca.js';
import { redact, fingerprint } from './redact.js';

const MODELS = { gemini, claude };

export const MODES = {
    rules: {
        label: 'Rules only',
        blurb: 'Offline regex engine. Free, instant, understands a fixed set of phrasings.',
        needsKey: false,
    },
    model: {
        label: 'Model only',
        blurb: 'Every prompt goes to the API. Most capable, costs a call each time.',
        needsKey: true,
    },
    'rules-first': {
        label: 'Rules → model fallback',
        blurb: 'Try the rules; call the API only for phrasings they cannot parse. Cheapest useful mix.',
        needsKey: true,
    },
    'model-first': {
        label: 'Model → rules fallback',
        blurb: 'Use the API, but fall back to the rules if it errors or is rate-limited. Most resilient.',
        needsKey: true,
    },
};

export const PROVIDERS = {
    gemini: { label: 'Google Gemini', defaultModel: gemini.DEFAULT_MODEL, envVar: 'GEMINI_API_KEY' },
    claude: { label: 'Anthropic Claude', defaultModel: claude.DEFAULT_MODEL, envVar: 'ANTHROPIC_API_KEY' },
};

/**
 * Work out what this request should actually do.
 *
 * Precedence for the key: the one pasted into Settings (per-request, never
 * stored server-side) beats the server's environment variable. That way one
 * running server can serve several people using their own keys, and the demo
 * still works with no browser configuration if the operator set an env var.
 */
export function resolveSettings(settings = {}) {
    const provider = PROVIDERS[settings.provider] ? settings.provider : 'gemini';
    const requestedMode = MODES[settings.mode] ? settings.mode : null;

    const clientKey = typeof settings.apiKey === 'string' && settings.apiKey.trim()
        ? settings.apiKey.trim()
        : null;
    const envKeyValue = MODELS[provider].envKey();
    const apiKey = clientKey || envKeyValue;

    // Default the mode from what is actually available rather than assuming.
    const mode = requestedMode
        || (process.env.AI_PROVIDER && apiKey ? 'model' : 'rules');

    const wantsModel = MODES[mode].needsKey;
    const usable = Boolean(apiKey);

    return {
        provider,
        mode,
        // A mode that needs a key but has none degrades to rules rather than
        // failing — the demo must never become unusable because of a config gap.
        effectiveMode: wantsModel && !usable ? 'rules' : mode,
        degraded: wantsModel && !usable,
        apiKey,
        keySource: clientKey ? 'settings' : envKeyValue ? 'environment' : null,
        model: settings.model || MODELS[provider].defaultModel(),
    };
}

/** Public, key-free description of the current configuration. */
export function providerStatus(settings = {}) {
    const r = resolveSettings(settings);
    return {
        provider: r.provider,
        providerLabel: PROVIDERS[r.provider].label,
        mode: r.mode,
        effectiveMode: r.effectiveMode,
        modeLabel: MODES[r.mode].label,
        degraded: r.degraded,
        degradedReason: r.degraded
            ? `"${MODES[r.mode].label}" needs an API key — add one in Settings. Running on rules only.`
            : null,
        model: r.model,
        hasKey: Boolean(r.apiKey),
        keySource: r.keySource,
        // Never the key itself. At most the last four characters, and only so a
        // user with several keys can tell which one is loaded.
        keyFingerprint: fingerprint(r.apiKey),
        modes: Object.entries(MODES).map(([id, m]) => ({ id, ...m })),
        providers: Object.entries(PROVIDERS).map(([id, p]) => ({ id, ...p })),
    };
}

const callModel = (provider, prompt, resolved) =>
    MODELS[provider].generate(prompt, { apiKey: resolved.apiKey, model: resolved.model });

/**
 * Run one prompt through the resolved route.
 *
 * `route` records what was actually tried, in order, so the UI can be honest
 * about it: "the rules could not parse that, so it went to Gemini" is much more
 * useful to a user deciding whether to trust the result than a silent fallback.
 */
async function generateVia(prompt, resolved) {
    const route = [];
    const mode = resolved.effectiveMode;

    if (mode === 'rules') {
        const result = await mock.generate(prompt);
        route.push({ step: 'rules', outcome: result.unparsed ? 'unparsed' : 'ok' });
        return { ...result, route, usedProvider: 'rules' };
    }

    if (mode === 'model') {
        const result = await callModel(resolved.provider, prompt, resolved);
        route.push({ step: resolved.provider, outcome: 'ok' });
        return { ...result, route, usedProvider: resolved.provider };
    }

    if (mode === 'rules-first') {
        const rules = await mock.generate(prompt);
        if (!rules.unparsed) {
            route.push({ step: 'rules', outcome: 'ok' });
            return { ...rules, route, usedProvider: 'rules' };
        }
        route.push({ step: 'rules', outcome: 'unparsed' });
        try {
            const result = await callModel(resolved.provider, prompt, resolved);
            route.push({ step: resolved.provider, outcome: 'ok' });
            return { ...result, route, usedProvider: resolved.provider };
        } catch (error) {
            // Both legs failed. Surface the rules' "I don't understand" rather
            // than a raw API error, but keep the API error visible too.
            route.push({ step: resolved.provider, outcome: 'error', error: redact(error.message, resolved.apiKey) });
            return { ...rules, route, usedProvider: 'rules' };
        }
    }

    // model-first
    try {
        const result = await callModel(resolved.provider, prompt, resolved);
        route.push({ step: resolved.provider, outcome: 'ok' });
        return { ...result, route, usedProvider: resolved.provider };
    } catch (error) {
        route.push({ step: resolved.provider, outcome: 'error', error: redact(error.message, resolved.apiKey) });
        const rules = await mock.generate(prompt);
        route.push({ step: 'rules', outcome: rules.unparsed ? 'unparsed' : 'ok' });
        return { ...rules, route, usedProvider: 'rules' };
    }
}

export async function runPrompt(prompt, settings = {}) {
    const resolved = resolveSettings(settings);
    const before = calculate(getProject());

    const startedAt = Date.now();
    let generated;
    try {
        generated = await generateVia(prompt, resolved);
    } catch (error) {
        return {
            status: 'error',
            // redact defensively: provider errors can echo the request back.
            error: redact(error.message, resolved.apiKey),
            mode: resolved.mode,
            effectiveMode: resolved.effectiveMode,
            provider: resolved.provider,
            route: [{ step: resolved.effectiveMode, outcome: 'error' }],
            applied: [],
            rejected: [],
            before,
            after: before,
            delta: { total_npv: 0, construction_cost: 0, embodied_carbon_t: 0 },
        };
    }
    const latencyMs = Date.now() - startedAt;

    const { applied, rejected } = executeCalls(generated.calls || []);
    const after = calculate(getProject());

    return {
        status: 'success',
        mode: resolved.mode,
        effectiveMode: resolved.effectiveMode,
        degraded: resolved.degraded,
        provider: generated.usedProvider,
        model: generated.usedProvider === 'rules' ? 'rule engine (offline)' : generated.model,
        route: generated.route,
        latencyMs,
        usage: generated.usage || null,
        calls: generated.calls,
        applied,
        rejected,
        before,
        after,
        delta: {
            total_npv: after.totals.total_npv - before.totals.total_npv,
            construction_cost: after.totals.construction_cost - before.totals.construction_cost,
            embodied_carbon_t: after.totals.embodied_carbon_t - before.totals.embodied_carbon_t,
        },
    };
}

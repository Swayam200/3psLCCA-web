/**
 * The mode router and request pipeline.
 *
 *   prompt
 *     → resolve(prefs, key)      which route is actually possible right now
 *     → generateVia()            local tiers and/or a model, per mode
 *     → executeCalls()           tools/schema.js — read-only in Phase 1
 *     → outcome                  { applied, rejected, route, … }
 *
 * CONFIDENCE CONTRACT
 * Every provider may return `confidence` in [0, 1] and/or `unparsed: true`:
 *   - rules:   deterministic — 1.0 on a pattern hit, 0 + unparsed otherwise
 *   - encoder: cosine similarity of the best intent match
 *   - gemma / cloud models: undefined (no calibrated confidence exists;
 *     pretending otherwise would be theatre)
 * The cascade mode falls through a stage when it is unparsed OR its
 * confidence is below the stage threshold. The route records every hop with
 * its confidence so the UI can show exactly who answered and how sure it was.
 *
 * The local cascade (rules → encoder → FunctionGemma) needs no API key and
 * never leaves the browser. The cloud modes are kept, deliberately, as the
 * comparison baseline — switching modes on the same prompt is the experiment.
 */

import { redact } from './redact.js';
import { loadPrefs, loadKey } from './settings.js';
import { getProvider, providerMeta, proxy, rules } from './providers/registry.js';
import * as localEncoder from './providers/localEncoder.js';
import * as functionGemma from './providers/functionGemma.js';
import { TOOLS, systemPrompt, executeCalls } from './tools/schema.js';
import { fingerprint } from './redact.js';

export const MODES = {
    rules: {
        label: 'Rules only',
        blurb: 'Offline pattern engine. Free, instant, never leaves this browser. Understands a fixed set of question phrasings.',
        needsModel: false,
    },
    cascade: {
        label: 'Local cascade (rules → encoder → Gemma)',
        blurb: 'Fully local and free: exact rules first, then a ~34 MB retrieval matcher, then (optional, experimental) a ~200 MB generative model. Each tier hands over when its confidence is too low. No API key, nothing leaves this browser.',
        needsModel: false,
    },
    model: {
        label: 'Model only',
        blurb: 'Every question goes to the configured cloud provider. Most capable; each question is an API call.',
        needsModel: true,
    },
    'rules-first': {
        label: 'Rules → cloud fallback',
        blurb: 'Try the offline rules; call the cloud model only for questions they cannot parse. The cheapest useful mix of local and cloud.',
        needsModel: true,
    },
    'model-first': {
        label: 'Cloud → rules fallback',
        blurb: 'Use the cloud model, but fall back to the offline rules if it errors or is unreachable. The most resilient cloud mode.',
        needsModel: true,
    },
};

/**
 * Work out what a request can actually do with the current settings. A mode
 * that needs a cloud model but has neither a key nor a proxy URL degrades to
 * rules rather than failing — the assistant must never be dead because of a
 * configuration gap. (The cascade needs neither, so it never degrades.)
 */
export function resolve(prefs = loadPrefs(), apiKey = loadKey()) {
    const mode = MODES[prefs.mode] ? prefs.mode : 'rules';
    const provider = getProvider(prefs.provider);
    const proxyUrl = String(prefs.proxyUrl || '').trim();
    const key = String(apiKey || '').trim();

    const needsModel = MODES[mode].needsModel;
    const modelUsable = Boolean(proxyUrl || key);

    return {
        mode,
        effectiveMode: needsModel && !modelUsable ? 'rules' : mode,
        degraded: needsModel && !modelUsable,
        providerId: providerMeta().some((p) => p.id === prefs.provider) ? prefs.provider : 'gemini',
        providerLabel: provider.label,
        model: String(prefs.model || '').trim() || provider.module.DEFAULT_MODEL || '',
        apiKey: key || null,
        proxyUrl: proxyUrl || null,
        via: proxyUrl ? 'proxy' : 'direct',
        local: {
            encoder: prefs.local?.encoder !== false,
            gemma: Boolean(prefs.local?.gemma),
            encoderThreshold: Number.isFinite(prefs.local?.encoderThreshold)
                ? prefs.local.encoderThreshold
                : localEncoder.DEFAULT_ENCODER_THRESHOLD,
        },
    };
}

/** Public, key-free description of the current configuration for the UI. */
export function providerStatus(prefs = loadPrefs(), apiKey = loadKey()) {
    const r = resolve(prefs, apiKey);
    return {
        enabled: Boolean(prefs.enabled),
        mode: r.mode,
        effectiveMode: r.effectiveMode,
        modeLabel: MODES[r.mode].label,
        degraded: r.degraded,
        degradedReason: r.degraded
            ? `"${MODES[r.mode].label}" needs an API key or a proxy URL — configure one in Settings → AI Assistant, or switch to the free local cascade. Running on the offline rules.`
            : null,
        provider: r.providerId,
        providerLabel: r.providerLabel,
        model: r.effectiveMode === 'rules' ? 'offline rules engine'
            : r.effectiveMode === 'cascade' ? 'local cascade' : r.model,
        via: r.via,
        hasKey: Boolean(r.apiKey),
        keyFingerprint: fingerprint(r.apiKey),
        local: {
            ...r.local,
            encoderReady: localEncoder.isEncoderReady(),
            gemmaReady: functionGemma.isGemmaReady(),
            encoderModel: localEncoder.ENCODER_MODEL_ID,
            encoderDownloadMb: localEncoder.ENCODER_DOWNLOAD_MB,
            gemmaModel: functionGemma.GEMMA_MODEL_ID,
            gemmaDownloadMb: functionGemma.GEMMA_DOWNLOAD_MB,
        },
        modes: Object.entries(MODES).map(([id, m]) => ({ id, ...m })),
        providers: providerMeta(),
    };
}

const callModel = (prompt, resolved, system) => {
    const options = {
        apiKey: resolved.apiKey,
        model: resolved.model,
        system,
        tools: TOOLS,
        provider: resolved.providerId,
        proxyUrl: resolved.proxyUrl,
    };
    return resolved.via === 'proxy'
        ? proxy.generate(prompt, options)
        : getProvider(resolved.providerId).module.generate(prompt, options);
};

const modelStep = (resolved) => (resolved.via === 'proxy' ? 'proxy' : resolved.providerId);

/**
 * Build the local cascade's stage list from the resolved settings. Each stage:
 * { step, run(prompt, context), threshold } — a stage's answer is accepted when
 * it is not unparsed and its confidence (when it has one) meets the threshold.
 */
const cascadeStages = (resolved) => {
    const stages = [
        { step: 'rules', threshold: 1, run: (p, c) => rules.generate(p, { context: c }) },
    ];
    if (resolved.local.encoder) {
        stages.push({
            step: 'encoder',
            threshold: resolved.local.encoderThreshold,
            run: (p, c) => localEncoder.generate(p, {
                context: c,
                threshold: resolved.local.encoderThreshold,
            }),
        });
    }
    if (resolved.local.gemma) {
        stages.push({
            step: 'gemma',
            threshold: 0, // generative: no calibrated confidence, accept any parsed call
            run: (p, c) => functionGemma.generate(p, { context: c }),
        });
    }
    return stages;
};

async function runCascade(prompt, resolved, context, stagesOverride) {
    const stages = stagesOverride || cascadeStages(resolved);
    const route = [];
    let lastResult = null;

    for (const stage of stages) {
        let result;
        try {
            result = await stage.run(prompt, context);
        } catch (error) {
            route.push({
                step: stage.step,
                outcome: 'error',
                error: redact(error.message, resolved.apiKey),
            });
            continue;
        }

        const confidence = result.confidence;
        const confident = confidence === undefined || confidence >= stage.threshold;

        if (!result.unparsed && confident) {
            route.push({ step: stage.step, outcome: 'ok', confidence });
            return { ...result, route, usedProvider: stage.step };
        }

        route.push({
            step: stage.step,
            outcome: result.unparsed ? 'unparsed' : 'low-confidence',
            confidence,
        });
        lastResult = result;
    }

    // Every tier declined or failed. Surface the last tier's own "I won't
    // guess" answer — refusal over guesswork, visibly routed.
    return {
        ...(lastResult || await rules.generate(prompt, { context })),
        route,
        usedProvider: route.at(-1)?.step || 'rules',
    };
}

async function generateVia(prompt, resolved, context, stagesOverride) {
    const route = [];
    const system = systemPrompt(context);
    const mode = resolved.effectiveMode;

    if (mode === 'rules') {
        const result = await rules.generate(prompt, { context });
        route.push({
            step: 'rules',
            outcome: result.unparsed ? 'unparsed' : 'ok',
            confidence: result.confidence,
        });
        return { ...result, route, usedProvider: 'rules' };
    }

    if (mode === 'cascade') {
        return runCascade(prompt, resolved, context, stagesOverride);
    }

    if (mode === 'model') {
        const result = await callModel(prompt, resolved, system);
        route.push({ step: modelStep(resolved), outcome: 'ok' });
        return { ...result, route, usedProvider: modelStep(resolved) };
    }

    if (mode === 'rules-first') {
        const local = await rules.generate(prompt, { context });
        if (!local.unparsed) {
            route.push({ step: 'rules', outcome: 'ok', confidence: local.confidence });
            return { ...local, route, usedProvider: 'rules' };
        }
        route.push({ step: 'rules', outcome: 'unparsed', confidence: local.confidence });
        try {
            const result = await callModel(prompt, resolved, system);
            route.push({ step: modelStep(resolved), outcome: 'ok' });
            return { ...result, route, usedProvider: modelStep(resolved) };
        } catch (error) {
            route.push({
                step: modelStep(resolved),
                outcome: 'error',
                error: redact(error.message, resolved.apiKey),
            });
            return { ...local, route, usedProvider: 'rules' };
        }
    }

    // model-first
    try {
        const result = await callModel(prompt, resolved, system);
        route.push({ step: modelStep(resolved), outcome: 'ok' });
        return { ...result, route, usedProvider: modelStep(resolved) };
    } catch (error) {
        route.push({
            step: modelStep(resolved),
            outcome: 'error',
            error: redact(error.message, resolved.apiKey),
        });
        const local = await rules.generate(prompt, { context });
        route.push({
            step: 'rules',
            outcome: local.unparsed ? 'unparsed' : 'ok',
            confidence: local.confidence,
        });
        return { ...local, route, usedProvider: 'rules' };
    }
}

const modelNameFor = (generated, resolved) => {
    switch (generated.usedProvider) {
        case 'rules': return 'offline rules engine';
        case 'encoder': return localEncoder.ENCODER_MODEL_ID;
        case 'gemma': return functionGemma.GEMMA_MODEL_ID;
        default: return generated.model || resolved.model;
    }
};

/**
 * Run one prompt. `context` comes from tools/context.js; prefs/key/stages are
 * injectable for tests.
 */
export async function runPrompt(prompt, { context, prefs, apiKey, stages } = {}) {
    const resolved = resolve(prefs ?? loadPrefs(), apiKey ?? loadKey());
    const startedAt = Date.now();

    let generated;
    try {
        generated = await generateVia(prompt, resolved, context, stages);
    } catch (error) {
        return {
            status: 'error',
            error: redact(error.message, resolved.apiKey),
            mode: resolved.mode,
            effectiveMode: resolved.effectiveMode,
            degraded: resolved.degraded,
            provider: modelStep(resolved),
            route: [{ step: modelStep(resolved), outcome: 'error' }],
            applied: [],
            rejected: [],
            latencyMs: Date.now() - startedAt,
        };
    }

    const { applied, rejected } = executeCalls(generated.calls);
    return {
        status: 'success',
        mode: resolved.mode,
        effectiveMode: resolved.effectiveMode,
        degraded: resolved.degraded,
        provider: generated.usedProvider,
        model: modelNameFor(generated, resolved),
        confidence: generated.confidence,
        intent: generated.intent,
        route: generated.route,
        usage: generated.usage || null,
        applied,
        rejected,
        latencyMs: Date.now() - startedAt,
    };
}

/**
 * AI assistant settings, including the user's API key.
 *
 * All key handling lives in this one file on purpose: auditing what happens to
 * a pasted key means reading this file and nothing else.
 *
 * WHAT THIS IS AND IS NOT
 * 3psLCCA-web deploys as a static site with no server of ours behind it, so
 * there is no place to hold a key for the user. The supported patterns are:
 *   1. bring-your-own-key, kept in this browser under the user's own policy
 *      (this file), or
 *   2. a proxy URL pointing at an endpoint the deploying organisation runs,
 *      which holds the key server-side (see providers/proxy.js) — the right
 *      choice for institutional deployments.
 *
 * A key saved here sits in browser storage IN PLAIN TEXT, readable by any
 * script on this origin. That is inherent to browser-held keys, not a gap in
 * this implementation — the settings UI says so to the user in as many words.
 *
 * These settings NEVER sync to Appwrite or into project files. They are
 * per-browser by design; a key must not ride along with a shared project.
 *
 * Storage choices, in order of how much risk they carry:
 *   'none'    — memory only. Gone on refresh.
 *   'session' — sessionStorage. Gone when the tab closes. The default.
 *   'local'   — localStorage. Survives restarts. Convenient; riskiest.
 */

import { ENCODER_MODEL_ID, DEFAULT_ENCODER_THRESHOLD } from './providers/localEncoder.js';

const PREFS_KEY = '3pslcca.ai.prefs';   // non-secret: mode, provider, model, policy…
const SECRET_KEY = '3pslcca.ai.key';    // the secret itself, in the chosen store

export const DEFAULT_PREFS = {
    enabled: false,          // runtime toggle, on top of the VITE_AI_ENABLED build flag
    provider: 'gemini',      // which model provider when a mode needs one
    mode: 'rules',           // rules | cascade | model | rules-first | model-first
    model: '',               // '' = provider default
    storage: 'session',      // where the key is kept: local | session | none
    proxyUrl: '',            // optional org proxy endpoint; '' = call providers directly
    local: {                 // the free, in-browser cascade tiers (mode: 'cascade')
        encoder: true,             // Tier 1: ~34 MB retrieval-embedding matcher (downloads on first use)
        gemma: false,              // Tier 3: ~200 MB FunctionGemma — experimental, explicit opt-in
        encoderThreshold: DEFAULT_ENCODER_THRESHOLD, // confidence gate, CALIBRATED TO THE MODEL
        encoderModel: ENCODER_MODEL_ID,              // stamp — see loadPrefs migration
    },
};

// Held in memory while the page is open regardless of storage choice, so
// 'none' works without touching any persistent store at all.
let memoryKey = '';

const safeParse = (raw) => {
    try { return raw ? JSON.parse(raw) : null; } catch { return null; }
};

/** Storage access that survives SSR, tests, and private-mode Safari. */
const store = (kind) => {
    try {
        if (typeof window === 'undefined') return null;
        return kind === 'local' ? window.localStorage
            : kind === 'session' ? window.sessionStorage
                : null;
    } catch { return null; }
};

export function loadPrefs() {
    const saved = safeParse(store('local')?.getItem(PREFS_KEY)) || {};
    const savedLocal = { ...(saved.local || {}) };

    // Threshold migration: similarity thresholds are calibrated to a specific
    // embedding model (MiniLM cosines cluster ~0.2–0.7, E5's ~0.7–1.0). A
    // stored threshold from a different encoder model would either mute the
    // tier entirely or let everything through — discard it and take the
    // current model's calibrated default.
    if (savedLocal.encoderModel !== DEFAULT_PREFS.local.encoderModel) {
        delete savedLocal.encoderThreshold;
        delete savedLocal.encoderModel;
    }

    // `local` is the one nested block — merge it so old saved prefs pick up
    // newly added defaults instead of wiping them.
    return {
        ...DEFAULT_PREFS,
        ...saved,
        local: { ...DEFAULT_PREFS.local, ...savedLocal },
    };
}

export function savePrefs(patch) {
    const current = loadPrefs();
    const next = {
        ...current,
        ...patch,
        local: { ...current.local, ...(patch?.local || {}) },
    };
    try { store('local')?.setItem(PREFS_KEY, JSON.stringify(next)); } catch { /* non-fatal */ }
    return next;
}

/** Read the key from wherever it was last kept. */
export function loadKey() {
    if (memoryKey) return memoryKey;
    for (const kind of ['session', 'local']) {
        const found = store(kind)?.getItem(SECRET_KEY);
        if (found) { memoryKey = found; return found; }
    }
    return '';
}

/**
 * Write the key to exactly one place and clear it from the others, so changing
 * the storage policy never silently leaves a copy behind in the old store.
 */
export function saveKey(key, storage) {
    memoryKey = key || '';
    for (const kind of ['session', 'local']) {
        try { store(kind)?.removeItem(SECRET_KEY); } catch { /* non-fatal */ }
    }
    if (key && storage !== 'none') {
        try { store(storage)?.setItem(SECRET_KEY, key); } catch { /* non-fatal */ }
    }
}

export function clearKey() {
    memoryKey = '';
    for (const kind of ['session', 'local']) {
        try { store(kind)?.removeItem(SECRET_KEY); } catch { /* non-fatal */ }
    }
}

export const maskKey = (key) => (!key ? '' : key.length <= 4 ? '••••' : `••••${key.slice(-4)}`);

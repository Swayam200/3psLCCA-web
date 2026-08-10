/**
 * Client-side settings, including the API key.
 *
 * All key handling lives in this one file on purpose: if you want to audit what
 * happens to a pasted key, this is the only browser file you have to read.
 *
 * WHAT THIS IS AND IS NOT
 * This is the right pattern for a *local developer tool* where the user brings
 * their own key. It is the wrong pattern for a deployed product: there the key
 * belongs on the server and the browser should never see one. The demo does it
 * this way so you can try Gemini or Claude without editing a shell profile —
 * and the UI says so plainly rather than pretending it is production-shaped.
 *
 * Storage choices, in order of how much risk they carry:
 *   'none'    — memory only. Gone on refresh. Nothing persisted anywhere.
 *   'session' — sessionStorage. Gone when the tab closes. Not shared to other tabs.
 *   'local'   — localStorage. Survives restarts. Plain text, readable by any
 *               script on this origin. The convenient one; also the riskiest.
 */

const PREFS_KEY = '3pslcca.ai.prefs';   // non-secret: provider, mode, model, storage choice
const SECRET_KEY = '3pslcca.ai.key';    // the secret itself, in the chosen store

const DEFAULTS = {
    provider: 'gemini',
    mode: 'rules',
    model: '',
    storage: 'session',
};

// The key is held here while the page is open regardless of storage choice, so
// 'none' works without touching any persistent store at all.
let memoryKey = '';

const safeParse = (raw) => {
    try { return raw ? JSON.parse(raw) : null; } catch { return null; }
};

/** localStorage throws in private-mode Safari and when disabled by policy. */
const store = (kind) => {
    try {
        return kind === 'local' ? window.localStorage
            : kind === 'session' ? window.sessionStorage
                : null;
    } catch { return null; }
};

export function loadPrefs() {
    const saved = safeParse(store('local')?.getItem(PREFS_KEY)) || {};
    return { ...DEFAULTS, ...saved };
}

export function savePrefs(prefs) {
    try { store('local')?.setItem(PREFS_KEY, JSON.stringify(prefs)); } catch { /* non-fatal */ }
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
 * the storage choice never silently leaves a copy behind in the old store.
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

/**
 * Headers for a request that may carry the key.
 *
 * The key travels in a header rather than the JSON body so that it is trivially
 * separable from the payload — nothing that gets logged, echoed, or replayed as
 * a request body will contain it.
 */
export function authHeaders() {
    const key = loadKey();
    return key ? { 'x-provider-key': key } : {};
}

/** The non-secret half, safe to put in a request body. */
export function settingsPayload(prefs) {
    return { provider: prefs.provider, mode: prefs.mode, model: prefs.model || undefined };
}

export const maskKey = (key) => (!key ? '' : key.length <= 4 ? '••••' : `••••${key.slice(-4)}`);

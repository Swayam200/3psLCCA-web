/**
 * Report preferences — which report the Results page offers.
 *
 * Two report paths exist:
 *   • "html"  — the standard report: an instant web page, printed to PDF by
 *               the browser (page preview with page numbers). Works on any
 *               laptop; nothing to download.
 *   • "latex" — the desktop-identical PDF: the desktop app's own LaTeX
 *               pipeline running in the browser (Python runtime + TeX, about
 *               60 MB downloaded once, 10–20 s per report, a lot of memory).
 *
 * The standard report is always available. The desktop PDF is an advanced
 * option that is switched off by default; a user can enable it and, if they
 * want, make it the primary button. Preferences are per browser
 * (localStorage), separate from the theme/user settings blob so neither can
 * overwrite the other.
 */

export const STORAGE_KEY = '3pslcca.reportPreferences';
export const CHANGE_EVENT = '3pslcca:reportpreferences';

/** Machines at or below this much memory struggle with the LaTeX pipeline. */
export const LOW_MEMORY_GB = 4;

export const REPORT_HTML = 'html';
export const REPORT_LATEX = 'latex';

export const DEFAULT_PREFERENCES = Object.freeze({
    /** Show the desktop-identical PDF (LaTeX) option under Advanced. */
    desktopPdfEnabled: false,
    /** Which report the main button produces: 'html' | 'latex'. */
    primaryReport: REPORT_HTML,
});

const safeStorage = (storage) => {
    if (storage) return storage;
    try { return globalThis.localStorage || null; } catch { return null; }
};

const normalize = (raw) => {
    const prefs = { ...DEFAULT_PREFERENCES, ...(raw && typeof raw === 'object' ? raw : {}) };
    prefs.desktopPdfEnabled = prefs.desktopPdfEnabled === true;
    prefs.primaryReport = prefs.primaryReport === REPORT_LATEX ? REPORT_LATEX : REPORT_HTML;
    // The desktop PDF can only be primary while it is enabled.
    if (!prefs.desktopPdfEnabled) prefs.primaryReport = REPORT_HTML;
    return prefs;
};

/** @returns {{ desktopPdfEnabled: boolean, primaryReport: 'html'|'latex' }} */
export const readReportPreferences = (storage) => {
    const store = safeStorage(storage);
    if (!store) return { ...DEFAULT_PREFERENCES };
    try {
        return normalize(JSON.parse(store.getItem(STORAGE_KEY) || 'null'));
    } catch {
        return { ...DEFAULT_PREFERENCES };
    }
};

/**
 * Merge `partial` into the saved preferences, persist, and notify listeners
 * (the Settings tab and the Results page stay in sync).
 */
export const writeReportPreferences = (partial, storage, target = globalThis) => {
    const next = normalize({ ...readReportPreferences(storage), ...partial });
    const store = safeStorage(storage);
    try { store?.setItem(STORAGE_KEY, JSON.stringify(next)); } catch { /* private mode */ }
    try { target?.dispatchEvent?.(new Event(CHANGE_EVENT)); } catch { /* no DOM */ }
    return next;
};

/** Which report the main button should produce given the preferences. */
export const effectivePrimaryReport = (prefs) => (
    prefs?.desktopPdfEnabled && prefs.primaryReport === REPORT_LATEX ? REPORT_LATEX : REPORT_HTML
);

/**
 * Device memory in GB as reported by the browser (Chromium only; it rounds
 * to 0.25/0.5/1/2/4/8 and caps at 8). null when unknown (Firefox, Safari).
 */
export const deviceMemoryGb = (nav = globalThis.navigator) => {
    const value = nav?.deviceMemory;
    return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : null;
};

/** True when the browser reports LOW_MEMORY_GB or less; unknown counts as not low. */
export const isLowMemoryDevice = (nav = globalThis.navigator) => {
    const gb = deviceMemoryGb(nav);
    return gb !== null && gb <= LOW_MEMORY_GB;
};

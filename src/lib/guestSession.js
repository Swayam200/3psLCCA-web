/**
 * Persistent guest identity. Guest logins used to live only in
 * sessionStorage, so closing the tab sent a returning guest — projects and
 * all — back to the auth page. A small localStorage marker lets the app
 * resume the guest directly on the home page; logging out (Settings/profile)
 * clears it. Appwrite-account users are unaffected: their sessions are
 * checked against Appwrite as before.
 *
 * Storage access is guarded so the module stays importable under node:test.
 */
const KEY = '3pslcca.guestSession';

const storage = () => (typeof localStorage === 'undefined' ? null : localStorage);

/** The saved guest ({ name, savedAt }) or null. */
export const loadGuestSession = () => {
    try {
        const raw = storage()?.getItem(KEY);
        const parsed = raw ? JSON.parse(raw) : null;
        return parsed && typeof parsed.name === 'string' && parsed.name.trim()
            ? parsed
            : null;
    } catch {
        return null;
    }
};

export const saveGuestSession = (name) => {
    const trimmed = String(name || '').trim();
    if (!trimmed) return;
    try {
        storage()?.setItem(KEY, JSON.stringify({ name: trimmed, savedAt: new Date().toISOString() }));
    } catch { /* storage full/blocked — guest just won't auto-resume */ }
};

export const clearGuestSession = () => {
    try {
        storage()?.removeItem(KEY);
    } catch { /* ignore */ }
};

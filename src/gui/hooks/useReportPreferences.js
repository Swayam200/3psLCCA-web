import { useCallback, useSyncExternalStore } from 'react';
import { CHANGE_EVENT, STORAGE_KEY, readReportPreferences, writeReportPreferences } from '../../utils/reportPreferences.js';

const subscribe = (onChange) => {
    window.addEventListener(CHANGE_EVENT, onChange);
    window.addEventListener('storage', onChange);
    return () => {
        window.removeEventListener(CHANGE_EVENT, onChange);
        window.removeEventListener('storage', onChange);
    };
};

// useSyncExternalStore compares snapshots by identity; serve the same
// object until the stored value actually changes.
let cachedRaw = null;
let cachedPrefs = readReportPreferences();
const getSnapshot = () => {
    let raw;
    try { raw = localStorage.getItem(STORAGE_KEY); } catch { raw = null; }
    if (raw !== cachedRaw) {
        cachedRaw = raw;
        cachedPrefs = readReportPreferences();
    }
    return cachedPrefs;
};
const getServerSnapshot = () => cachedPrefs;

/**
 * Report preferences shared between the Settings → Reports tab and the
 * Results page. Returns [prefs, update]; update(partial) persists and
 * re-renders every subscriber.
 */
export const useReportPreferences = () => {
    const prefs = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
    const update = useCallback((partial) => writeReportPreferences(partial), []);
    return [prefs, update];
};

export default useReportPreferences;

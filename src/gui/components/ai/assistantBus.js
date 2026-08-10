/**
 * Tiny pub/sub connecting "open the assistant" affordances (e.g. the Results
 * page cue) to the floating launcher, which owns the sheet's open state.
 * Module-scoped on purpose: both ends live inside the same lazy AI chunk, so
 * no context provider needs to exist in flag-off builds.
 */
const listeners = new Set();

/** Ask the floating assistant to open its sheet (no-op if not mounted). */
export const openAssistant = () => {
    for (const listener of [...listeners]) listener();
};

/** Subscribe to open requests. Returns an unsubscribe function. */
export const onAssistantOpen = (listener) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
};

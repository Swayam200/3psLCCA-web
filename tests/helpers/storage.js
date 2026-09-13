// Fresh Web Storage semantics for every test, independent of Node's optional
// native localStorage implementation and any developer machine state.
export function createStorage() {
    const entries = new Map();
    return {
        get length() { return entries.size; },
        key: index => [...entries.keys()][index] ?? null,
        getItem: key => entries.get(String(key)) ?? null,
        setItem: (key, value) => entries.set(String(key), String(value)),
        removeItem: key => entries.delete(String(key)),
        clear: () => entries.clear(),
    };
}

/**
 * Material-database search for the Add Material dialog, extracted as a pure
 * module so node:test can cover it. Mirrors the desktop GUI's matching:
 * normalized tokens, every query token must match, concatenated units like
 * "500mm" fall back to their parts, and rows from the current construction
 * section rank first.
 */

/** Lowercase, replace special chars with spaces, collapse whitespace. */
export const normalize = (text) => {
    if (!text) return '';
    return String(text).toLowerCase()
        .replace(/[(),\-/]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
};

export const tokenize = (text) => {
    const norm = normalize(text);
    return norm ? norm.split(' ') : [];
};

/** Token match with concatenated-unit fallback: "500mm" -> ["500","mm"]. */
export const tokenMatches = (tok, itemNorm) => {
    if (itemNorm.includes(tok)) return true;
    const parts = tok.match(/[a-z]+|\d+/g);
    if (parts && parts.length > 1) {
        return parts.every((p) => itemNorm.includes(p));
    }
    return false;
};

/**
 * Resolve the project's stored SOR key against the available database keys,
 * tolerating case and stray-whitespace drift — a silently failed exact
 * lookup is how "search shows no data" bugs are born.
 */
export const resolveDbKey = (dbKeys, rawKey) => {
    const raw = String(rawKey || '').trim();
    if (!raw) return null;
    if (dbKeys.includes(raw)) return raw;
    const canon = (key) => key.toLowerCase().replace(/\s+/g, '');
    const wanted = canon(raw);
    return dbKeys.find((key) => canon(key) === wanted) || null;
};

/** Minimum query length before searching (desktop parity). */
export const MIN_QUERY_LENGTH = 2;

/**
 * Search a material database (array of sheets, each {sheetName, type, data})
 * for a query. Returns ranked matches; [] when the query is too short.
 */
export const searchMaterials = (dbData, query, sectionName, { limit = 50 } = {}) => {
    if (!dbData || !query || query.length < MIN_QUERY_LENGTH) return [];

    const queryTokens = tokenize(query);
    if (queryTokens.length === 0) return [];

    const results = [];
    const normSection = String(sectionName || '').toLowerCase();

    dbData.forEach((sheet) => {
        const sheetNorm = sheet.sheetName.toLowerCase();
        const typeNorm = sheet.type.toLowerCase();

        // Prioritize if section name matches sheet name or type (e.g. "Girders" vs "Girder")
        const isRelevantSection = normSection.includes(sheetNorm) || sheetNorm.includes(normSection)
            || normSection.includes(typeNorm) || typeNorm.includes(normSection);

        sheet.data.forEach((item) => {
            const itemNorm = normalize(item.name);
            const allTokensMatch = queryTokens.every((tok) => tokenMatches(tok, itemNorm));

            if (allTokensMatch) {
                results.push({
                    ...item,
                    sheetName: sheet.sheetName,
                    type: sheet.type,
                    isRelevantSection,
                });
            }
        });
    });

    // Sorting priority: current section first, then prefix matches, then
    // shorter (usually more general) names, then alphabetical.
    return results.sort((a, b) => {
        if (a.isRelevantSection && !b.isRelevantSection) return -1;
        if (!a.isRelevantSection && b.isRelevantSection) return 1;

        const aStarts = a.name.toLowerCase().startsWith(query.toLowerCase());
        const bStarts = b.name.toLowerCase().startsWith(query.toLowerCase());
        if (aStarts && !bStarts) return -1;
        if (!aStarts && bStarts) return 1;

        if (a.name.length !== b.name.length) return a.name.length - b.name.length;

        return a.name.localeCompare(b.name);
    }).slice(0, limit);
};

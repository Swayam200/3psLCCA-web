/**
 * Key redaction for anything that might reach a log, an error message, or the
 * screen.
 *
 * Provider APIs habitually echo the offending request back in their error
 * bodies (Gemini even carries the key in the request URL), and a pasted key is
 * the user's own money. Every provider error passes through here before it
 * goes anywhere a human, a log, or a bug report can see it.
 */

// Common provider key shapes plus any long opaque token.
const PATTERNS = [
    /AIza[0-9A-Za-z\-_]{20,}/g,          // Google
    /sk-ant-[0-9A-Za-z\-_]{20,}/g,       // Anthropic
    /sk-[0-9A-Za-z\-_]{20,}/g,           // OpenAI-style
    /\b[0-9A-Za-z\-_]{32,}\b/g,          // anything else long and opaque
];

export function redact(text, ...extraSecrets) {
    let out = String(text ?? '');

    // Exact-match known secrets first — catches short or oddly-shaped keys the
    // generic patterns would miss.
    for (const secret of extraSecrets) {
        if (secret && String(secret).length >= 8) {
            out = out.split(String(secret)).join('[redacted]');
        }
    }
    for (const pattern of PATTERNS) out = out.replace(pattern, '[redacted]');
    return out;
}

/**
 * Turn a provider's error response into one readable, redacted line. Both
 * providers wrap the useful sentence in a page of JSON; dig it out when the
 * shape is recognisable, truncate when it is not.
 */
export function providerError(label, status, bodyText, apiKey) {
    let detail = String(bodyText || '').trim();
    try {
        const parsed = JSON.parse(detail);
        detail = parsed?.error?.message      // Gemini
            || parsed?.error?.type            // Anthropic
            || parsed?.message
            || detail;
        if (parsed?.error?.message && parsed?.error?.type) {
            detail = `${parsed.error.type}: ${parsed.error.message}`;
        }
    } catch { /* not JSON — use the raw text */ }

    if (detail.length > 240) detail = `${detail.slice(0, 240)}…`;
    return `${label} ${status}: ${redact(detail, apiKey)}`;
}

/** Safe display form of a key: never more than the last 4 characters. */
export const fingerprint = (key) => {
    if (!key) return null;
    const str = String(key);
    return str.length <= 4 ? '••••' : `••••${str.slice(-4)}`;
};

/**
 * Presentation helpers for the answer route ("which engine answered, how
 * sure was it"). Pure module — no JSX — so node:test can cover it directly.
 */

/** The logo's three circles, measured from public/logo-3pslcca.svg. */
export const LOGO_COLORS = { orange: '#ff5a2a', green: '#8ad400', purple: '#9e9eff' };

/** Per-tier accents, mapped onto the logo palette. */
export const TIER_COLORS = {
    rules: LOGO_COLORS.green, // deterministic, offline
    encoder: LOGO_COLORS.purple, // local retrieval
    generative: LOGO_COLORS.orange, // gemma / cloud providers
};

export const pillStyle = (outcome) => ({
    fontSize: '0.72rem',
    fontFamily: 'var(--bs-font-monospace, monospace)',
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: '999px',
    border: `1px solid ${outcome === 'error' ? 'var(--app-danger, #c2410c)' : 'var(--app-border-mid)'}`,
    borderStyle: (outcome === 'unparsed' || outcome === 'low-confidence') ? 'dashed' : 'solid',
    color: outcome === 'error' ? 'var(--app-danger, #c2410c)' : 'var(--app-text-secondary)',
});

/** "rules 100%" / "encoder: 41% < threshold" / "gemma: failed" */
export const pillLabel = (step) => {
    const pct = Number.isFinite(step.confidence) ? ` ${Math.round(step.confidence * 100)}%` : '';
    if (step.outcome === 'ok') return `${step.step}${pct}`;
    if (step.outcome === 'low-confidence') return `${step.step}:${pct} < threshold`;
    if (step.outcome === 'unparsed') return `${step.step}: no match`;
    return `${step.step}: failed`;
};

/**
 * Accent color for the tier that actually answered (last 'ok' hop of the
 * route), or null when nothing answered. Powers the launcher's badge tint —
 * the route pills stay the authoritative record.
 */
export const tierColor = (route) => {
    const answered = [...(route || [])].reverse().find((step) => step.outcome === 'ok');
    if (!answered) return null;
    if (answered.step === 'rules') return TIER_COLORS.rules;
    if (answered.step === 'encoder') return TIER_COLORS.encoder;
    return TIER_COLORS.generative;
};

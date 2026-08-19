/**
 * displayFormat.js
 * Global numeric display formatting for the Results page.
 * Ported VERBATIM from desktop gui/components/utils/display_format.py
 * (including its current behavior of using western suffixes for all
 * currencies — "21.13 million", not "2.11 crore").
 */

export const DECIMAL_PLACES = 2;

const WESTERN_UNITS = [
    // [threshold, divisor, full, short]
    [100_000_000_000, 1_000_000_000_000, 'trillion', 'T'],
    [100_000_000, 1_000_000_000, 'billion', 'B'],
    [100_000, 1_000_000, 'million', 'M'],
    [1_000, 1_000, 'thousand', 'K'],
];

const toFloat = (val) => {
    if (val === null || val === undefined) return null;
    const f = Number(val);
    return Number.isFinite(f) ? f : null;
};

/** Desktop `_fmt_suffix`: divide by the first matching threshold. */
export const fmtShort = (n, useShortSuffix = false) => {
    const f = toFloat(n);
    if (f === null) return '-';
    const sign = f < 0 ? '-' : '';
    const absN = Math.abs(f);
    for (const [threshold, divisor, full, short] of WESTERN_UNITS) {
        if (absN >= threshold) {
            const value = Math.round((absN / divisor) * 10 ** DECIMAL_PLACES) / 10 ** DECIMAL_PLACES;
            const vStr = Number.isInteger(value) ? String(value) : value.toFixed(DECIMAL_PLACES);
            const suffix = useShortSuffix ? short : full;
            const sep = useShortSuffix ? '' : ' ';
            return `${sign}${vStr}${sep}${suffix}`;
        }
    }
    return absN ? `${sign}${absN}` : '0';
};

/**
 * Desktop `fmt_currency`.
 * style "comma" → '1,234,567.00' · "short" → '1.23 million' · "both" → both.
 */
// eslint-disable-next-line no-unused-vars -- positional arg kept for desktop signature parity
export const fmtCurrency = (val, _currency = 'INR', { decimals = null, style = 'comma', useShortSuffix = false } = {}) => {
    const f = toFloat(val);
    if (f === null) return '-';
    const d = decimals === null ? DECIMAL_PLACES : decimals;
    const sign = f < 0 ? '-' : '';
    const absV = Math.abs(f);
    const commaStr = sign + absV.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
    const shortStr = fmtShort(f, useShortSuffix);
    if (style === 'comma') return commaStr;
    if (style === 'short') return shortStr;
    return `${commaStr} (${shortStr})`;
};

/** Desktop `currency_note`. */
export const currencyNote = (currency) => `All values in ${currency}`;

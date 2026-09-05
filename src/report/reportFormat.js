/**
 * Formatting helpers for the HTML report.
 *
 * Mirrors the desktop LaTeX report's conventions (code_to_latex/SETTINGS.py):
 * 2 decimals with thousands separators for values, 4 decimals for WPI
 * ratios, an em-dash for missing values.
 */

export const DECIMALS = 2;
export const RATIO_DECIMALS = 4;
export const EMDASH = '—';

const toNumber = (value) => {
    if (value === null || value === undefined || value === '') return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
};

/** Insert thousands separators into the integer part of a fixed-point string. */
const group = (fixed) => {
    const [int, frac] = fixed.split('.');
    const sign = int.startsWith('-') ? '-' : '';
    const digits = sign ? int.slice(1) : int;
    const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    return frac === undefined ? `${sign}${grouped}` : `${sign}${grouped}.${frac}`;
};

/**
 * `f"{val:,.2f}"` — desktop's number cell.
 *
 * Rounds with toFixed, not Intl: toFixed rounds the exact binary value like
 * Python's format does (0.975 → "0.97"), whereas Intl.NumberFormat rounds
 * the shortest decimal representation (0.975 → "0.98") and would disagree
 * with the desktop report on half-way cases.
 */
export const fmt = (value, decimals = DECIMALS) => {
    const n = toNumber(value);
    if (n === null) return EMDASH;
    return group(n.toFixed(decimals));
};

/** `f"{val:.2f}"` — no thousands separator (percentages, factors). */
export const fmtPlain = (value, decimals = DECIMALS) => {
    const n = toNumber(value);
    if (n === null) return EMDASH;
    return n.toFixed(decimals);
};

/** Integer without decimals (vehicle counts). */
export const fmtInt = (value) => {
    const n = toNumber(value);
    if (n === null) return EMDASH;
    return Math.trunc(n).toLocaleString('en-US');
};

/**
 * Desktop `fields_to_latex` value cell: raw value as entered (Python
 * `str(raw)`), em-dash when empty, followed by the field's unit.
 */
export const fieldValue = (raw, unit = '') => {
    const empty = raw === '' || raw === null || raw === undefined;
    const text = empty ? EMDASH : String(raw);
    return unit && !empty ? `${text} ${unit}` : text;
};

/** desktop definitions.UNIT_DISPLAY (units.json "display" overrides). */
const UNIT_DISPLAY = {
    m2: 'm²', m3: 'm³', ml: 'mL', l: 'L', mm2: 'mm²', cm2: 'cm²',
    ton_us: 'ton', ft2: 'ft²', yd2: 'yd²', ft3: 'ft³', yd3: 'yd³', in2: 'in²',
};
export const unitDisplay = (unit) => UNIT_DISPLAY[unit] || unit || '';

/** material_emissions_latex._fmt_ef_unit */
export const emissionUnitDisplay = (unit) => (unit || '')
    .replace('CO2e', 'CO₂e').replace('m2', 'm²').replace('m3', 'm³');

/** html_to_latex: rich-text remarks → plain text (tags stripped). */
export const stripHtml = (html) => {
    if (!html) return '';
    const text = String(html)
        .replace(/<style[\s\S]*?<\/style>/gi, ' ')
        .replace(/<[^>]+>/g, ' ')
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'")
        .replace(/\s+/g, ' ')
        .trim();
    return text;
};

/** Safe file-name stem for the printed PDF (desktop: spaces → underscores). */
export const reportFileStem = (name) => `${String(name || 'LCCA').trim().replace(/\s+/g, '_')}_Report`;

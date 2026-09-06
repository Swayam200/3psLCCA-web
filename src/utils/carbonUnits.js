/**
 * carbonUnits.js
 * Canonical carbon-emission unit resolution, ported from desktop
 * gui/components/structure/registry/material_entry.py (resolve_carbon_denom).
 *
 * Source data keeps two distinct fields, never aliased onto each other:
 *   - carbon_emission_units_den: always the bare denominator, e.g. "kg".
 *   - carbon_emission_units: the older/ambiguous column — historically
 *     filled with the full ratio (e.g. "kgCO2/kg"). The segment after the
 *     last "/" is the denominator; a value with no "/" is already bare.
 * "_den" wins when both are present (it's the unambiguous one).
 */

/** Return the bare denominator unit for a raw SOR/database item, or null. */
export const resolveCarbonDenom = (item = {}) => {
    const den = item.carbon_emission_units_den;
    if (den !== null && den !== undefined && den !== '' && den !== 0) {
        return String(den).trim();
    }
    const units = item.carbon_emission_units;
    if (units !== null && units !== undefined && units !== '' && units !== 0) {
        const str = String(units).trim();
        return str.includes('/') ? str.slice(str.lastIndexOf('/') + 1).trim() : str;
    }
    return null;
};

/**
 * Map an SOR denominator code to the display unit the web app stores in
 * carbonEmission.perUnit. Returns null for codes with no web equivalent so
 * callers can leave their current unit untouched (matching the desktop
 * dialog, which only moves its unit combo when the code resolves).
 */
export const denomToWebUnit = (denom) => {
    if (denom === 'cum') return 'm³';
    if (denom === 'kg') return 'kg';
    if (denom === 'MT') return 't';
    return null;
};

/** True when a unit string names CO2 (any casing, ₂ included) — i.e. it is a full ratio, not a bare denominator. */
export const mentionsCo2 = (value) => (
    String(value ?? '').toLowerCase().replace(/₂/g, '2').includes('co2')
);

// ── Quantity ↔ emission-factor unit compatibility ───────────────────────────
//
// A material row is priced per `quantityUnit` (MT, cum, Rmt, sqm, …) while
// its emission factor is per `emissionUnit` (usually kg). Total emissions
// are quantity × conversion_factor × factor, where conversion_factor is
// "emission units per quantity unit" (kg per MT = 1000, kg per cum = the
// density, …). Schedules of rates ship that factor per item; when it is
// missing the app can only derive it for units of the same dimension.

const UNIT_ALIASES = {
    kg: 'kg', kilogram: 'kg', kilograms: 'kg', kgs: 'kg',
    t: 't', mt: 't', tonne: 't', tonnes: 't', ton: 't', tons: 't',
    q: 'q', quintal: 'q',
    g: 'g', gram: 'g', grams: 'g',
    'm³': 'm³', m3: 'm³', cum: 'm³', cu_m: 'm³', 'cu.m': 'm³', 'cubic metre': 'm³', 'cubic meter': 'm³',
    l: 'L', litre: 'L', liter: 'L', litres: 'L', liters: 'L',
    ml: 'mL', millilitre: 'mL',
    'm²': 'm²', m2: 'm²', sqm: 'm²', 'sq.m': 'm²', 'square metre': 'm²', 'square meter': 'm²',
    'mm²': 'mm²', mm2: 'mm²', 'cm²': 'cm²', cm2: 'cm²', ha: 'ha',
    m: 'm', rmt: 'm', rm: 'm', metre: 'm', meter: 'm', 'running metre': 'm',
    mm: 'mm', cm: 'cm', km: 'km',
    nos: 'nos', 'nos.': 'nos', no: 'nos', number: 'nos', numbers: 'nos', each: 'nos', pcs: 'nos', 'pcs.': 'nos', pieces: 'nos',
};

const UNIT_FAMILY = {
    kg: ['mass', 1], t: ['mass', 1000], q: ['mass', 100], g: ['mass', 0.001],
    'm³': ['volume', 1], L: ['volume', 0.001], mL: ['volume', 0.000001],
    'm²': ['area', 1], 'mm²': ['area', 0.000001], 'cm²': ['area', 0.0001], ha: ['area', 10000],
    m: ['length', 1], mm: ['length', 0.001], cm: ['length', 0.01], km: ['length', 1000],
    nos: ['count', 1],
};

/** "m³ — Cubic Metre" / "MT" / "cum" → canonical unit code, or the trimmed raw string. */
export const canonicalUnit = (raw) => {
    const head = String(raw ?? '').split('—')[0].split('(')[0].trim();
    if (!head) return '';
    return UNIT_ALIASES[head.toLowerCase()] || UNIT_ALIASES[head] || head;
};

/**
 * Resolve the conversion factor (emission units per quantity unit) for a row.
 *
 * `explicit`  — a factor stored on the row (schedule of rates, import, user).
 * `trusted`   — true when that factor was chosen deliberately (SOR item,
 *               desktop import, or the user confirmed it), so it wins even
 *               when it equals 1.
 *
 * Returns { factor, status, note }:
 *   status 'explicit'  — stored factor used as-is
 *          'same'      — units identical, factor 1
 *          'derived'   — same dimension, converted (e.g. MT → kg ×1000)
 *          'mismatch'  — different dimensions and no usable factor; the row
 *                        must not be counted until a factor is supplied
 *          'unknown'   — one of the units is empty; factor falls back to 1
 */
export const resolveConversionFactor = ({ quantityUnit, emissionUnit, explicit, trusted = false } = {}) => {
    const explicitValue = Number(explicit);
    const hasExplicit = Number.isFinite(explicitValue) && explicitValue > 0;
    const q = canonicalUnit(quantityUnit);
    const e = canonicalUnit(emissionUnit);

    if (hasExplicit && trusted) {
        return { factor: explicitValue, status: 'explicit', note: `${explicitValue} ${e || 'unit'} per ${q || 'unit'} (stored)` };
    }
    if (!q || !e) {
        return { factor: hasExplicit ? explicitValue : 1, status: 'unknown', note: 'Emission unit not set' };
    }
    if (q === e) {
        return { factor: 1, status: 'same', note: '' };
    }
    const qf = UNIT_FAMILY[q];
    const ef = UNIT_FAMILY[e];
    if (qf && ef && qf[0] === ef[0]) {
        const factor = qf[1] / ef[1];
        return { factor, status: 'derived', note: `×${factor} (${q} → ${e})` };
    }
    // Different dimensions: a stored factor other than the default 1 is a
    // real figure (SOR density, import); a bare 1 is just the default.
    if (hasExplicit && explicitValue !== 1) {
        return { factor: explicitValue, status: 'explicit', note: `${explicitValue} ${e} per ${q} (stored)` };
    }
    return {
        factor: 0,
        status: 'mismatch',
        note: `Quantity is in ${q} but the factor is per ${e}: enter the conversion factor (${e} per ${q}).`,
    };
};

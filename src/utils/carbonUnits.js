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

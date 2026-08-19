/**
 * Recycling derivation — desktop parity.
 *
 * Mirrors desktop gui/components/recycling/main.py: the recycling table is
 * DERIVED from the construction material rows (each row carries a
 * recyclability percentage and scrap rate from the material database);
 * the recycling chunk itself only stores the computed summary. Recovered
 * value per row = quantity × recyclability%/100 × scrap_rate, summed over
 * rows that are valid and not manually excluded
 * (state.included_in_recyclability, default true).
 */
import { parseNumber } from '../gui/components/carbon_emission/carbonUtils.js';

export const REASON_INCOMPLETE = 'Incomplete Data';
export const REASON_EXCLUDED = 'Manually Excluded';

/** [projectData key, display category] — desktop CHUNKS order. */
export const RECYCLING_SECTIONS = [
    ['foundation_data', 'Foundation'],
    ['substructure_data', 'Sub Structure'],
    ['superstructure_data', 'Super Structure'],
    ['miscellaneous_data', 'Misc'],
];

const rowValues = (row) => (row && typeof row.values === 'object' && row.values) || {};

/** Desktop `_recycle_pct`: checks both field names for backward compat. */
export const recyclePct = (row) => {
    const v = rowValues(row);
    return parseNumber(
        v.post_demolition_recovery_percentage
        ?? v.recyclability_percentage
        ?? row.postDemolitionRecoveryPercentage
        ?? row.recyclabilityPercentage,
        0,
    );
};

export const scrapRate = (row) => {
    const v = rowValues(row);
    return parseNumber(v.scrap_rate ?? row.scrapRate, 0);
};

export const rowQuantity = (row) => {
    const v = rowValues(row);
    return parseNumber(v.quantity ?? row.qty ?? row.quantity, 0);
};

export const rowUnit = (row) => {
    const v = rowValues(row);
    return v.unit ?? row.unit ?? '';
};

export const rowName = (row) => {
    const v = rowValues(row);
    return v.material_name ?? row.workName ?? row.name ?? '';
};

/** Desktop `is_recyclable_valid`. */
export const isRecyclableValid = (row) => (
    recyclePct(row) > 0 && scrapRate(row) > 0 && rowQuantity(row) > 0
);

/** Desktop `calc_recyclable_qty`: quantity × (recyclability% / 100). */
export const calcRecyclableQty = (row) => rowQuantity(row) * (recyclePct(row) / 100);

/** Desktop `calc_recovered_value`: recyclable qty × scrap_rate. */
export const calcRecoveredValue = (row) => calcRecyclableQty(row) * scrapRate(row);

const isManuallyIncluded = (row) => {
    const state = (row && typeof row.state === 'object' && row.state) || {};
    return state.included_in_recyclability !== false;
};

/**
 * Desktop `_compute()`: walk every non-trashed material row across the four
 * structure categories and split into included/excluded with reasons.
 *
 * Returns { includedItems, excludedItems, totalRecoveredValue, catTotals,
 * includedCount, totalCount }; item entries carry {category, sectionKey,
 * sectionId, sectionName, row, value|reason} so the UI can act on rows.
 */
export const computeRecycling = (projectData = {}) => {
    const catTotals = Object.fromEntries(RECYCLING_SECTIONS.map(([, cat]) => [cat, 0]));
    const includedItems = [];
    const excludedItems = [];
    let totalRecoveredValue = 0;
    let totalCount = 0;

    for (const [sectionKey, category] of RECYCLING_SECTIONS) {
        const sections = Array.isArray(projectData[sectionKey]) ? projectData[sectionKey] : [];
        for (const section of sections) {
            const rows = Array.isArray(section?.rows) ? section.rows : [];
            for (const row of rows) {
                if (row?.state?.in_trash) continue;
                totalCount += 1;
                const valid = isRecyclableValid(row);
                const included = isManuallyIncluded(row);
                const base = {
                    category,
                    sectionKey,
                    sectionId: section.id,
                    sectionName: section.name,
                    row,
                };
                if (valid && included) {
                    const value = calcRecoveredValue(row);
                    totalRecoveredValue += value;
                    catTotals[category] += value;
                    includedItems.push({ ...base, value });
                } else {
                    excludedItems.push({
                        ...base,
                        reason: valid ? REASON_EXCLUDED : REASON_INCOMPLETE,
                    });
                }
            }
        }
    }

    return {
        includedItems,
        excludedItems,
        totalRecoveredValue,
        catTotals,
        includedCount: includedItems.length,
        totalCount,
    };
};

/** Desktop `get_data()`: the summary persisted into recycling_data. */
export const recyclingChunkData = (projectData, currency = '') => {
    const computed = computeRecycling(projectData);
    return {
        total_recovered_value: computed.totalRecoveredValue,
        included_count: computed.includedCount,
        total_count: computed.totalCount,
        cat_totals: computed.catTotals,
        currency,
    };
};

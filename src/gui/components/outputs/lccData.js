/**
 * lccData.js
 * Single source of truth for all LCC stage/row definitions on the Results
 * page. Ported VERBATIM from desktop gui/components/outputs/lcc_data.py —
 * stage keys, row labels, colors, and credit handling must not drift.
 */
import { COLORS as LC } from './lccColors.js';

/** Keys treated as credits (negated in charts and totals). */
export const CREDIT_KEYS = new Set(['total_scrap_value']);

/** [stage_key, category, result_key, label] — desktop `_MASTER_ROWS`. */
export const MASTER_ROWS = [
    // Initial Stage
    ['initial_stage', 'economic', 'initial_construction_cost', 'Initial Construction Cost'],
    ['initial_stage', 'economic', 'time_cost_of_loan', 'Time Costs'],
    ['initial_stage', 'environmental', 'initial_material_carbon_emission_cost', 'Initial Carbon Emissions'],
    ['initial_stage', 'environmental', 'initial_vehicular_emission_cost', 'Carbon emissions due to Rerouting (Construction)'],
    ['initial_stage', 'social', 'initial_road_user_cost', 'Road User Costs (Construction)'],

    // Use Stage
    ['use_stage', 'economic', 'routine_inspection_costs', 'Routine Inspection Costs'],
    ['use_stage', 'economic', 'periodic_maintenance', 'Periodic Maintenance Costs'],
    ['use_stage', 'economic', 'major_inspection_costs', 'Major Inspection Costs'],
    ['use_stage', 'economic', 'major_repair_cost', 'Major Repair Costs'],
    ['use_stage', 'economic', 'replacement_costs_for_bearing_and_expansion_joint', 'Replacement Costs of Bearings and Expansion joints'],
    ['use_stage', 'environmental', 'periodic_carbon_costs', 'Periodic Maintenance related Carbon Emissions'],
    ['use_stage', 'environmental', 'major_repair_material_carbon_emission_costs', 'Major Repair related Carbon Emissions'],
    ['use_stage', 'environmental', 'major_repair_vehicular_emission_costs', 'Carbon Emissions due to Rerouting during Major Repairs'],
    ['use_stage', 'environmental', 'vehicular_emission_costs_for_replacement_of_bearing_and_expansion_joint', 'Carbon Emissions due to Rerouting during Replacement of Bearings and Expansion joints'],
    ['use_stage', 'social', 'major_repair_road_user_costs', 'Road User Costs during Major Repairs'],
    ['use_stage', 'social', 'road_user_costs_for_replacement_of_bearing_and_expansion_joint', 'Road User Costs during Replacement of Bearings and Expansion joints'],

    // Reconstruction Stage
    ['reconstruction', 'economic', 'total_demolition_and_disposal_costs', 'Demolition and Disposal Costs'],
    ['reconstruction', 'economic', 'total_scrap_value', 'Recycling Costs'],
    ['reconstruction', 'economic', 'cost_of_reconstruction_after_demolition', 'Reconstruction Costs'],
    ['reconstruction', 'economic', 'time_cost_of_loan', 'Time Costs'],
    ['reconstruction', 'environmental', 'carbon_costs_demolition_and_disposal', 'Demolition and Disposal related Carbon Emissions'],
    ['reconstruction', 'environmental', 'demolition_vehicular_emission_cost', 'Carbon Emissions due to Rerouting during Demolition and Disposal'],
    ['reconstruction', 'environmental', 'carbon_cost_of_reconstruction_after_demolition', 'Reconstruction related Carbon Emissions'],
    ['reconstruction', 'environmental', 'reconstruction_vehicular_emission_cost', 'Carbon Emissions due to Rerouting during Reconstruction'],
    ['reconstruction', 'social', 'ruc_demolition', 'Road User Costs related to Demolition and Disposal during Reconstruction'],
    ['reconstruction', 'social', 'ruc_reconstruction', 'Road User Costs during Reconstruction'],

    // End of Life Stage
    ['end_of_life', 'economic', 'total_demolition_and_disposal_costs', 'Demolition and Disposal Costs'],
    ['end_of_life', 'economic', 'total_scrap_value', 'Recycling Costs'],
    ['end_of_life', 'environmental', 'carbon_costs_demolition_and_disposal', 'Demolition and Disposal related Carbon Emissions'],
    ['end_of_life', 'environmental', 'demolition_vehicular_emission_cost', 'Carbon Emissions due to Rerouting during Demolition and Disposal'],
    ['end_of_life', 'social', 'ruc_demolition', 'Road User Costs due to Demolition and Disposal'],
];

/** [stage_key, chart_title, breakdown_label, color, tick_color, stage_color, optional] */
export const STAGE_META = [
    ['initial_stage', 'Initial Stage', 'Initial Stage Costs', '#cfd9e8', '#2c4a75', LC.init_color, false],
    ['use_stage', 'Use Stage', 'Use Stage Costs', '#cfe8e2', '#1f6f66', LC.use_color, false],
    ['reconstruction', 'Reconstruction Stage', 'Reconstruction Stage', '#e8d5f0', '#5a3270', LC.recon_color, true],
    ['end_of_life', 'End-of-Life Stage', 'End-of-Life Stage', '#edd5d5', '#7a3b3b', LC.end_color, false],
];

/** Desktop `BREAKDOWN_STAGES` (rows grouped per stage). */
export const BREAKDOWN_STAGES = STAGE_META.map(([sk, , bdLbl, , , sColor, optional]) => ({
    label: bdLbl,
    stage_color: sColor,
    result_key: sk,
    optional,
    rows: MASTER_ROWS.filter(([rowSk]) => rowSk === sk).map(([, cat, key, label]) => [cat, key, label]),
}));

/** Desktop `STAGE_DEFS`: [chart_title, stage_key, {Category: [keys]}]. */
export const STAGE_DEFS = STAGE_META.map(([sk, chartTitle]) => {
    const cats = {};
    for (const [rowSk, cat, key] of MASTER_ROWS) {
        if (rowSk !== sk) continue;
        const catName = cat.charAt(0).toUpperCase() + cat.slice(1);
        (cats[catName] = cats[catName] || []).push(CREDIT_KEYS.has(key) ? `-${key}` : key);
    }
    return [chartTitle, sk, cats];
});

/** Desktop `stage_totals`: {Category: total} for one stage (credits negated). */
export const stageTotals = (results, resultKey, catKeys) => {
    const stageData = results?.[resultKey];
    if (!stageData || typeof stageData !== 'object') return {};
    const totals = {};
    for (const cat of Object.keys(catKeys)) {
        const catData = stageData[cat.toLowerCase()] || {};
        let total = 0;
        if (catData && typeof catData === 'object') {
            for (const [k, v] of Object.entries(catData)) {
                total += CREDIT_KEYS.has(k) ? -v : v;
            }
        }
        totals[cat] = total;
    }
    return totals;
};

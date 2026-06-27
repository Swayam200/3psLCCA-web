/**
 * breakdownStages.js
 * Defines the detailed row-by-row mapping of result keys to display labels.
 * Ported from: 3psLCCA-gui/gui/components/outputs/helper_functions/breakdown_stages.py
 */

import { COLORS } from './lccColors.js';

export const BREAKDOWN_STAGES = [
    {
        label: 'Initial Stage Costs',
        stageColor: COLORS.init_color,
        resultKey: 'initial_stage',
        optional: false,
        rows: [
            { pillar: 'economic', key: 'initial_construction_cost', label: 'Construction Cost' },
            { pillar: 'economic', key: 'time_cost_of_loan', label: 'Loan Interest' },
            { pillar: 'environmental', key: 'initial_material_carbon_emission_cost', label: 'Construction Carbon Emissions' },
            { pillar: 'environmental', key: 'initial_vehicular_emission_cost', label: 'Traffic Rerouting Emissions' },
            { pillar: 'social', key: 'initial_road_user_cost', label: 'Road User Cost (Construction)' },
        ],
    },
    {
        label: 'Use Stage Costs',
        stageColor: COLORS.use_color,
        resultKey: 'use_stage',
        optional: false,
        rows: [
            { pillar: 'economic', key: 'routine_inspection_costs', label: 'Routine Inspection' },
            { pillar: 'economic', key: 'periodic_maintenance', label: 'Periodic Maintenance' },
            { pillar: 'economic', key: 'major_inspection_costs', label: 'Major Inspection' },
            { pillar: 'economic', key: 'major_repair_cost', label: 'Major Repair' },
            { pillar: 'economic', key: 'replacement_costs_for_bearing_and_expansion_joint', label: 'Bearing & Expansion Joint Replacement' },
            { pillar: 'environmental', key: 'periodic_carbon_costs', label: 'Periodic Maintenance Emissions' },
            { pillar: 'environmental', key: 'major_repair_material_carbon_emission_costs', label: 'Major Repair Emissions' },
            { pillar: 'environmental', key: 'major_repair_vehicular_emission_costs', label: 'Major Repair Traffic Rerouting Emissions' },
            { pillar: 'environmental', key: 'vehicular_emission_costs_for_replacement_of_bearing_and_expansion_joint', label: 'Bearing Replacement Traffic Emissions' },
            { pillar: 'social', key: 'major_repair_road_user_costs', label: 'Road User Cost (Major Repair)' },
            { pillar: 'social', key: 'road_user_costs_for_replacement_of_bearing_and_expansion_joint', label: 'Road User Cost (Replacement)' },
        ],
    },
    {
        label: 'Reconstruction Stage',
        stageColor: COLORS.recon_color,
        resultKey: 'reconstruction',
        optional: true,
        rows: [
            { pillar: 'economic', key: 'cost_of_reconstruction_after_demolition', label: 'Reconstruction Cost' },
            { pillar: 'economic', key: 'total_demolition_and_disposal_costs', label: 'Demolition & Disposal' },
            { pillar: 'economic', key: 'time_cost_of_loan', label: 'Loan Interest' },
            { pillar: 'economic', key: 'total_scrap_value', label: 'Scrap Value Credit' },
            { pillar: 'environmental', key: 'carbon_cost_of_reconstruction_after_demolition', label: 'Reconstruction Emissions' },
            { pillar: 'environmental', key: 'carbon_costs_demolition_and_disposal', label: 'Demolition Material Emissions' },
            { pillar: 'environmental', key: 'demolition_vehicular_emission_cost', label: 'Demolition Traffic Emissions' },
            { pillar: 'environmental', key: 'reconstruction_vehicular_emission_cost', label: 'Reconstruction Traffic Emissions' },
            { pillar: 'social', key: 'ruc_demolition', label: 'Road User Cost (Demolition)' },
            { pillar: 'social', key: 'ruc_reconstruction', label: 'Road User Cost (Reconstruction)' },
        ],
    },
    {
        label: 'End-of-Life Stage',
        stageColor: COLORS.end_color,
        resultKey: 'end_of_life',
        optional: false,
        rows: [
            { pillar: 'economic', key: 'total_demolition_and_disposal_costs', label: 'Demolition & Disposal' },
            { pillar: 'economic', key: 'total_scrap_value', label: 'Scrap Value Credit' },
            { pillar: 'environmental', key: 'carbon_costs_demolition_and_disposal', label: 'Demolition Material Emissions' },
            { pillar: 'environmental', key: 'demolition_vehicular_emission_cost', label: 'Demolition Traffic Emissions' },
            { pillar: 'social', key: 'ruc_demolition', label: 'Road User Cost (Demolition)' },
        ],
    },
];

/**
 * Stage definitions for the consolidated summary table.
 * Maps [displayLabel, resultKey, pillarKeys]
 */
export const STAGE_DEFS = [
    ['Initial Stage', 'initial_stage', ['economic', 'environmental', 'social']],
    ['Use Stage', 'use_stage', ['economic', 'environmental', 'social']],
    ['Reconstruction Stage', 'reconstruction', ['economic', 'environmental', 'social']],
    ['End-of-Life Stage', 'end_of_life', ['economic', 'environmental', 'social']],
];

/**
 * Compute per-pillar totals for a given stage.
 * Treats total_scrap_value as a credit (negative).
 */
export function computeStagePillarTotals(results, resultKey, pillarKeys) {
    const stageData = results[resultKey];
    if (!stageData) return null;

    const totals = {};
    for (const pillar of pillarKeys) {
        const pillarData = stageData[pillar];
        if (!pillarData || typeof pillarData !== 'object') {
            totals[pillar] = 0;
            continue;
        }
        let sum = 0;
        for (const [k, v] of Object.entries(pillarData)) {
            if (k === 'total_scrap_value') {
                sum -= v;
            } else {
                sum += v;
            }
        }
        totals[pillar] = sum;
    }
    return totals;
}

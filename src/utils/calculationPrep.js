/**
 * Calculation-time project preparation — desktop parity.
 *
 * Desktop assembles the engine's inputs from its LIVE widgets at "Calculate"
 * time, so two values are always fresh no matter which pages were opened:
 *
 *  - recycling_data.total_recovered_value — recomputed from the construction
 *    material rows (recycling/main.py `_compute` via `get_data`), and
 *  - the social cost of carbon — resolved from the saved Ricke parameters
 *    (or the custom override) rather than read from a possibly-stale stored
 *    number (scc_tabs/ricke.py `get_cost`).
 *
 * The web persists project data instead of holding live widgets, so this
 * module recreates that behavior right before the engine call: it returns a
 * patched copy of the project for the calculation plus the chunks to
 * persist, and never throws — on any failure the project is used as-is
 * (the adapter's own validation then reports what is missing).
 */
import { loadCsccCountry } from '../lib/cscc.js';
import { parseNumber } from '../gui/components/carbon_emission/carbonUtils.js';
import { computeRicke, SOURCE_CUSTOM } from '../gui/components/carbon_emission/rickeCompute.js';
import { recyclingChunkData } from './recyclingDerivations.js';

const RICKE_UNIT = (currency) => `${currency}/kgCO₂e`;

/**
 * Resolve the social cost of carbon exactly like the Social Cost page
 * (and desktop's live widget) would. Returns null when nothing could be
 * resolved (keep whatever is stored).
 */
export const resolveSocialCostOfCarbon = async (projectData) => {
    const social = projectData?.carbon_emission_data?.social_cost_data || {};
    const currency = projectData?.general_info?.project_currency || projectData?.currency || 'INR';

    const isCustom = social.source === SOURCE_CUSTOM || social.mode === SOURCE_CUSTOM || social.mode === 'custom';
    if (isCustom) {
        const value = parseNumber(social.custom?.entered_value ?? social.custom?.scc_value, 0);
        return value > 0 ? { cost: value, selectedMode: SOURCE_CUSTOM, currency } : null;
    }

    const ricke = social.ricke;
    if (!ricke || typeof ricke !== 'object') return null;
    const countryData = await loadCsccCountry(ricke.iso3 || 'WLD');
    const { cost } = computeRicke(ricke, countryData, currency);
    if (!(cost > 0)) return null;
    return { cost, selectedMode: social.source || social.mode || 'K. Ricke et al. (Country-Level)', currency };
};

/**
 * Produce the calculation-ready project: recycling summary derived from the
 * material rows, SCC resolved from its parameters. Also reports what to
 * persist so the stored project (and the report) reflect the same values.
 *
 * @returns {{ project: object, recycling: object, socialCost: object|null }}
 */
export const prepareProjectForCalculation = async (projectData) => {
    const project = { ...(projectData || {}) };
    const currency = project.general_info?.project_currency || project.currency || 'INR';

    // Recycling: desktop recomputes the chunk from material rows on every
    // calculate. Keep the legacy saved list only for projects that have no
    // material rows at all.
    let recycling = null;
    try {
        const computed = recyclingChunkData(project, currency);
        if (computed.total_count > 0) {
            recycling = { ...(project.recycling_data || {}), ...computed };
            project.recycling_data = recycling;
        }
    } catch (error) {
        console.warn('[calculationPrep] recycling derivation failed:', error);
    }

    // Social cost of carbon: resolve from parameters; stored value is a cache.
    let socialCost = null;
    try {
        const resolved = await resolveSocialCostOfCarbon(project);
        if (resolved) {
            const social = project.carbon_emission_data?.social_cost_data || {};
            const nextSocial = {
                ...social,
                calculated_scc_local: resolved.cost,
                cost_of_carbon_local: resolved.cost,
                result: {
                    ...(social.result || {}),
                    selected_mode: resolved.selectedMode,
                    cost_of_carbon_local: resolved.cost,
                    currency: resolved.currency,
                    unit: RICKE_UNIT(resolved.currency),
                },
            };
            project.carbon_emission_data = {
                ...(project.carbon_emission_data || {}),
                social_cost_data: nextSocial,
            };
            socialCost = { cost: resolved.cost, social_cost_data: nextSocial };
        }
    } catch (error) {
        console.warn('[calculationPrep] SCC resolution failed:', error);
    }

    return { project, recycling, socialCost };
};

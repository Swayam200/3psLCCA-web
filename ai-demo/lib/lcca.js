/**
 * Simplified life-cycle cost calculation.
 *
 * This is NOT the real `three_ps_lcca_core` engine — it is a ~70-line stand-in
 * with the same *shape*: it consumes the project JSON, rolls construction
 * quantities up into stage costs, discounts recurring costs to present value,
 * and splits the total across the three sustainability pillars (the "3ps":
 * profit / planet / people). Swapping this for a POST to the real FastAPI
 * backend at /api/lcca/calculate is a one-function change.
 */

import { SECTION_KEYS, SECTION_LABELS } from './seed.js';

const num = (value) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
};

export const activeRows = (project, sectionKey) =>
    (project[sectionKey] || []).filter((row) => !row?.state?.in_trash);

/** Present value of a single amount occurring `year` years from now. */
const pv = (amount, rate, year) => amount / Math.pow(1 + rate, year);

export function calculate(project) {
    const fin = project.financial_data || {};
    const period = Math.max(1, num(fin.analysis_period) || 50);
    const discount = num(fin.discount_rate) / 100;
    const inflation = num(fin.inflation_rate) / 100;
    // Real (inflation-adjusted) discount rate — Fisher relation.
    const realRate = Math.max(0.0001, (1 + discount) / (1 + inflation) - 1);

    const sections = SECTION_KEYS.map((key) => {
        const rows = activeRows(project, key);
        const cost = rows.reduce((sum, r) => sum + num(r.qty) * num(r.rate), 0);
        const carbon = rows.reduce(
            (sum, r) => sum + num(r.qty) * num(r.carbonEmission?.factor),
            0,
        );
        return { key, label: SECTION_LABELS[key], rowCount: rows.length, cost, carbon };
    });

    const constructionCost = sections.reduce((s, x) => s + x.cost, 0);
    const embodiedCarbonT = sections.reduce((s, x) => s + x.carbon, 0);

    // --- Maintenance: a fixed % of construction cost every N years ----------
    const interval = Math.max(1, num(fin.maintenance_interval) || 8);
    const eventCost = constructionCost * (num(fin.maintenance_pct) / 100);
    const maintenanceEvents = [];
    for (let year = interval; year < period; year += interval) {
        maintenanceEvents.push({ year, cost: eventCost, pv: pv(eventCost, realRate, year) });
    }
    const maintenancePV = maintenanceEvents.reduce((s, e) => s + e.pv, 0);

    // --- Demolition / end-of-life ------------------------------------------
    const demolitionCost = constructionCost * (num(fin.demolition_pct) / 100);
    const demolitionPV = pv(demolitionCost, realRate, period);

    // --- Social: road user cost, annuity over the analysis period ----------
    const annualUser = num(fin.annual_road_user_cost);
    const userCostPV = realRate === 0
        ? annualUser * period
        : annualUser * (1 - Math.pow(1 + realRate, -period)) / realRate;

    // --- Environmental: monetised embodied carbon --------------------------
    const carbonCost = embodiedCarbonT * num(fin.social_cost_of_carbon);

    const pillars = {
        profit: constructionCost + maintenancePV + demolitionPV,
        planet: carbonCost,
        people: userCostPV,
    };
    const totalNPV = pillars.profit + pillars.planet + pillars.people;

    return {
        status: 'success',
        currency: project.currency || 'INR',
        assumptions: {
            analysis_period: period,
            discount_rate: num(fin.discount_rate),
            inflation_rate: num(fin.inflation_rate),
            real_discount_rate: Number((realRate * 100).toFixed(3)),
            maintenance_interval: interval,
            maintenance_pct: num(fin.maintenance_pct),
            demolition_pct: num(fin.demolition_pct),
            social_cost_of_carbon: num(fin.social_cost_of_carbon),
        },
        sections,
        stages: [
            { key: 'construction', label: 'Construction', cost: constructionCost },
            { key: 'maintenance', label: `Maintenance (${maintenanceEvents.length} events, PV)`, cost: maintenancePV },
            { key: 'operation', label: 'Road user cost (PV)', cost: userCostPV },
            { key: 'carbon', label: 'Embodied carbon (monetised)', cost: carbonCost },
            { key: 'demolition', label: 'Demolition / EOL (PV)', cost: demolitionPV },
        ],
        pillars,
        totals: {
            construction_cost: constructionCost,
            maintenance_pv: maintenancePV,
            demolition_pv: demolitionPV,
            user_cost_pv: userCostPV,
            carbon_cost: carbonCost,
            embodied_carbon_t: embodiedCarbonT,
            total_npv: totalNPV,
            npv_per_m: project.bridge_data?.span ? totalNPV / num(project.bridge_data.span) : null,
        },
        maintenance_events: maintenanceEvents,
    };
}

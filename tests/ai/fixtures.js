/**
 * Shared fixtures for the AI test suite: a project shaped like real app data,
 * with an outputs_data.results dict matching the core engine's stage/pillar
 * structure (see breakdownStages.js for the key vocabulary).
 */

export const RESULTS_FIXTURE = {
    initial_stage: {
        economic: { initial_construction_cost: 90_000_000, time_cost_of_loan: 6_000_000 },
        environmental: { initial_material_carbon_emission_cost: 11_000_000 },
        social: { initial_road_user_cost: 4_000_000 },
    },
    use_stage: {
        economic: { periodic_maintenance: 22_000_000, major_repair_cost: 9_000_000 },
        environmental: { periodic_carbon_costs: 3_000_000 },
        social: { major_repair_road_user_costs: 5_000_000 },
    },
    reconstruction: {
        economic: {},
        environmental: {},
        social: {},
    },
    end_of_life: {
        economic: { total_demolition_and_disposal_costs: 7_000_000, total_scrap_value: 2_000_000 },
        environmental: { carbon_costs_demolition_and_disposal: 1_500_000 },
        social: { ruc_demolition: 500_000 },
    },
};

// Lifetime total, mirroring lifecycleSummary's sumDict (scrap value is a credit):
// eco 90+6+22+9+7-2 = 132M, env 11+3+1.5 = 15.5M, social 4+5+0.5 = 9.5M → 157M.
export const EXPECTED = {
    eco: 132_000_000,
    env: 15_500_000,
    social: 9_500_000,
    lifetime: 157_000_000,
};

export const PROJECT_FIXTURE = {
    schema_version: 1,
    name: 'Kosi Crossing',
    country: 'INDIA',
    currency: 'INR',
    unitSystem: 'Metric (SI)',
    general_info: { project_name: 'Kosi Crossing', project_currency: 'INR' },
    bridge_data: {
        bridge_name: 'Kosi River Bridge',
        bridge_type: 'PSC I-girder',
        span: 240,
        num_lanes: 4,
        design_life: 100,
        analysis_period: 50,
    },
    financial_data: {
        discount_rate: 6.5,
        inflation_rate: 4.2,
        interest_rate: 8,
    },
    // Deliberately includes sections the AI code never special-cases —
    // the schema-driven walker must index them all the same.
    traffic_data: {
        vehicles: {
            hcv: { vehicles_per_day: 400, pwr: 7.22 },
            small_cars: { vehicles_per_day: 1200 },
        },
        traffic_growth: 5,
    },
    demolition_data: {
        demolition_cost_pct: 6,
    },
    foundation_data: [{
        id: 'sec-1',
        name: 'Section 1',
        rows: [
            { id: 'r1', workName: 'PCC M15 levelling course', qty: 180, unit: 'm³', rate: 6250, state: { in_trash: false } },
            { id: 'r2', workName: 'Reinforcement steel Fe500D', qty: 96000, unit: 'kg', rate: 78, state: { in_trash: false } },
            { id: 'r3', workName: 'Old trashed item', qty: 1, unit: 'nos', rate: 1, state: { in_trash: true } },
        ],
    }],
    superstructure_data: [{
        id: 'sec-2',
        name: 'Section 1',
        rows: [
            { id: 'r4', workName: 'PSC I-girder, M45', qty: 1260, unit: 'm³', rate: 13400, state: { in_trash: false } },
            { id: 'r5', workName: 'Bituminous concrete wearing coat', qty: 3150, unit: 'm²', rate: 720, state: { in_trash: false } },
        ],
    }],
    outputs_data: {
        results: RESULTS_FIXTURE,
        validation: { errors: [], warnings: ['Traffic growth rate defaulted to 5%.'] },
        analysis_period_years: 50,
        calculated_at: '2026-08-01T10:00:00.000Z',
        source: 'browser',
        engine: { source: 'browser', coreVersion: '1.0.2' },
    },
};

/** A project that has never been calculated. */
export const UNCALCULATED_PROJECT = {
    ...PROJECT_FIXTURE,
    outputs_data: {},
};

import test from 'node:test';
import assert from 'node:assert/strict';

import { normalizeProjectData } from '../src/utils/projectSchema.js';
import {
    normalizeCarbonEmissionData,
    normalizeBridgeData,
    normalizeProjectSection,
    validateBridgeData,
    validateDemolitionData,
    validateFinancialData,
    validateMaintenanceData,
    validateTrafficData,
} from '../src/utils/projectPageSchema.js';
import { buildCalculationProjectInputs } from '../src/utils/projectDerivations.js';

test('legacy project data normalizes without losing old maintenance or construction fields', () => {
    const normalized = normalizeProjectData({
        name: 'Legacy Bridge',
        construction_work_data: {
            Foundation: { rows: [{ workName: 'Pile', rate: '10', qty: '2' }] },
        },
        maintenance_data: {
            routine_inspection_cost: '0',
        },
    });

    assert.equal(normalized.schema_version, 1);
    assert.equal(normalized.general_info.project_name, 'Legacy Bridge');
    assert.equal(normalized.foundation_data[0].rows[0].workName, 'Pile');
    assert.equal(normalized.maintenance_repair_data.routine_inspection_cost, '0');
    assert.equal(normalized.maintenance_data.routine_inspection_cost, '0');
});

test('carbon emission data preserves transport and diversion aliases', () => {
    const normalized = normalizeCarbonEmissionData({
        transportation_emissions_data: { total_kgCO2e: 12 },
        diversion_emissions: { total_direct_emissions: 5 },
    });

    assert.equal(normalized.transport_emissions_data.total_kgCO2e, 12);
    assert.equal(normalized.transportation_emissions_data.total_kgCO2e, 12);
    assert.equal(normalized.diversion_emissions_data.total_direct_emissions, 5);
    assert.equal(normalized.diversion_emissions.total_direct_emissions, 5);
});

test('traffic page state derives to core-compatible traffic fields', () => {
    const project = normalizeProjectData({
        traffic_data: normalizeProjectSection('traffic_data', {
            calculation_mode: 'INDIA',
            vehicles: {
                small_cars: { vehicles_per_day: 10, accident_percentage: 100 },
            },
            severity: {
                severity_minor: 60,
                severity_major: 30,
                severity_fatal: 10,
            },
            alternate_road: {
                alternate_road_carriageway: 'Two Lane',
                carriage_width_in_m: 7,
                hourly_capacity: 1500,
            },
            road_params: {
                road_roughness_mm_per_km: 2000,
                work_zone_multiplier: 0.5,
            },
            peak_distribution: { h1: 0.1, h2: 0.1 },
            wpi_profile: '2024',
            wpi_data: { small_cars: { petrol: 1 } },
        }),
    });

    const derived = buildCalculationProjectInputs(project).traffic_and_road_data;
    assert.equal(derived.mode, 'INDIA');
    assert.equal(derived.vehicle_data.small_cars.vehicles_per_day, 10);
    assert.equal(derived.vehicle_data.small_cars.accident_percentage, 100);
    assert.equal(derived.severity_minor, 60);
    assert.equal(derived.alternate_road_carriageway, 'Two Lane');
});

test('traffic normalization restores desktop initial PWR and WPI defaults', () => {
    const normalized = normalizeProjectSection('traffic_data', {
        vehicles: {
            hcv: { vehicles_per_day: 0, accident_percentage: 0, pwr: 0 },
            mcv: {},
        },
        force_free_flow_off_peak: true,
    });

    assert.equal(normalized.vehicles.hcv.pwr, 7.22);
    assert.equal(normalized.vehicles.mcv.pwr, 8);
    assert.equal(normalized.wpi_profile, '2019');
    assert.equal(normalized.wpi_year, '2019');
    assert.equal(normalized.force_free_flow, true);
    assert.equal(normalized.road_params.road_roughness_mm_per_km, 2000);
    assert.equal(normalized.road_params.work_zone_multiplier, 1);
});

test('traffic normalization prefers the desktop WPI snapshot over stale flat data', () => {
    const normalized = normalizeProjectSection('traffic_data', {
        wpi_profile: '2019',
        wpi_data: { small_cars: { petrol: 0 } },
        wpi: {
            selected_profile_name: '2021',
            selected_profile_year: 2021,
            data_snapshot: {
                selected: { small_cars: { petrol: 108.4 } },
            },
        },
    });

    assert.equal(normalized.wpi_profile, '2021');
    assert.equal(normalized.wpi_year, '2021');
    assert.equal(normalized.wpi_data.small_cars.petrol, 108.4);
});

test('traffic validation requires rerouting road configuration in India mode', () => {
    const errors = validateTrafficData({
        calculation_mode: 'INDIA',
        alternate_road: {
            alternate_road_carriageway: '',
            carriage_width_in_m: 0,
            hourly_capacity: 0,
        },
        road_params: {
            road_roughness_mm_per_km: 2000,
            work_zone_multiplier: 1,
        },
        wpi_profile: '2019',
        wpi_data: {
            small_cars: { petrol: 1 },
        },
    });

    assert.ok(errors.some((message) => message.includes('Alternate road carriageway is required')));
});

test('page validators allow zero-cost percentages but reject invalid durations and traffic sums', () => {
    assert.deepEqual(validateFinancialData({
        discount_rate: '0',
        inflation_rate: '0',
        interest_rate: '0',
        investment_ratio: '0',
    }), []);

    assert.deepEqual(validateMaintenanceData({
        routine_inspection_cost: '0',
        routine_inspection_freq: '1',
        periodic_maintenance_cost: '0',
        periodic_maintenance_carbon_cost: '0',
        periodic_maintenance_freq: '5',
        major_inspection_cost: '0',
        major_inspection_freq: '5',
        major_repair_cost: '0',
        major_repair_carbon_cost: '0',
        major_repair_freq: '20',
        major_repair_duration: '3',
        bearing_exp_joint_cost: '0',
        bearing_exp_joint_freq: '25',
        bearing_exp_joint_duration: '2',
    }), []);

    assert.ok(validateDemolitionData({
        demolition_cost: '0',
        demolition_carbon_cost: '0',
        demolition_duration: '0',
    }).some((message) => message.includes('duration')));

    assert.ok(validateTrafficData({
        calculation_mode: 'INDIA',
        vehicles: { small_cars: { vehicles_per_day: 10, accident_percentage: 50 } },
        severity: { severity_minor: 60, severity_major: 30, severity_fatal: 10 },
        alternate_road: { alternate_road_carriageway: 'Two Lane', carriage_width_in_m: 7, hourly_capacity: 1500 },
        wpi_profile: '2024',
        wpi_data: { small_cars: { petrol: 1 } },
    }).some((message) => message.includes('Vehicle accident percentages')));
});

test('bridge normalization mirrors desktop defaults and carries project country', () => {
    const normalized = normalizeBridgeData({
        location_country: '',
        location_from: 'Mumbai',
        location_via: 'Creek',
        location_to: 'Navi Mumbai',
        service_life: 75,
        year_of_construction: '',
        working_days_per_month: '',
        days_per_month: '',
    }, {
        country: 'INDIA',
        general_info: { project_country: 'INDIA' },
    });

    assert.equal(normalized.project_country, 'INDIA');
    assert.equal(normalized.location, 'Mumbai, Creek, Navi Mumbai');
    assert.equal(normalized.analysis_period, 75);
    assert.equal(normalized.year_of_construction, new Date().getFullYear());
    assert.equal(normalized.working_days_per_month, 22);
    assert.equal(normalized.days_per_month, 30);
});

test('bridge validation only requires the four desktop-required fields', () => {
    const errors = validateBridgeData({
        year_of_construction: 2026,
        design_life: 50,
        analysis_period: 75,
        duration_construction_months: 12,
        working_days_per_month: 22,
        days_per_month: 30,
    });

    assert.deepEqual(errors, []);

    const missing = validateBridgeData({
        bridge_name: '',
        user_agency: '',
        project_country: 'INDIA',
        year_of_construction: 2026,
        working_days_per_month: 22,
        days_per_month: 30,
    });
    assert.equal(missing.length, 3);
    assert.ok(missing.some((message) => message.includes('design life')));
    assert.ok(missing.some((message) => message.includes('analysis period')));
    assert.ok(missing.some((message) => message.includes('duration construction months')));
});

test('carbon emission data sections sync and recalculate correctly from structural and traffic inputs', () => {
    const project = normalizeProjectData({
        foundation_data: [
            {
                name: 'Main Foundation',
                rows: [
                    { id: 'row-1', workName: 'Concrete', qty: 100, unit: 'm3', conversionFactor: 2.4, carbonEmission: { factor: 0.15 } }
                ]
            }
        ],
        traffic_data: {
            calculation_mode: 'INDIA',
            vehicles: {
                small_cars: { vehicles_per_day: 500, accident_percentage: 100 }
            }
        },
        carbon_emission_data: {
            material_emissions_data: {
                excluded_ids: []
            },
            transportation_emissions_data: {
                raw_ui_entries: [
                    {
                        vehicle: { name: 'Medium Truck', capacity: 10.0, gross_weight: 16.0, empty_weight: 6.0, emission_factor: 1.2 },
                        route: { origin: 'Quarry', distance_km: 50 },
                        selectedMaterials: [
                            { id: 'row-1', name: 'Concrete', quantity: 0, unit: 'm3', kgFactor: 1.0 }
                        ]
                    }
                ]
            },
            machinery_emissions_data: {
                mode: 'detailed',
                detailed_entries: [
                    { rate: 1, hours: 8, days: 5, ef: 2.5 }
                ]
            },
            diversion_emissions_data: {
                mode: 'calculate',
                reroute_km: 10,
                factors: {
                    small_cars: 0.1
                }
            },
            social_cost_data: {
                mode: 'NITI Aayog',
                inr_rate: 1.5
            }
        }
    });

    const carbon = project.carbon_emission_data;

    // 1. Material emissions recalculation check (100 * 2.4 * 0.15 = 36)
    assert.equal(carbon.material_emissions_data.total_kgCO2e, 36);

    // 2. Transportation emissions recalculation check
    // Updated material weight: 100 qty * 2.4 conversion factor = 240 kg = 0.24 T
    // Trips: ceil(0.24 / 10 capacity) = 1 trip
    // Emission: (16 gross + 6 empty) * 1 trip * 50 km * 1.2 ef = 1320 kgCO2e
    assert.equal(carbon.transport_emissions_data.total_kgCO2e, 1320);
    assert.equal(carbon.transport_emissions_data.raw_ui_entries[0].selectedMaterials[0].quantity, 100);
    assert.equal(carbon.transport_emissions_data.raw_ui_entries[0].selectedMaterials[0].kgFactor, 2.4);

    // 3. Machinery emissions check (1 * 8 * 5 * 2.5 = 100)
    assert.equal(carbon.machinery_emissions_data.total_kgCO2e, 100);

    // 4. Traffic diversion emissions check (500 adt * 10 km * 0.1 ef = 500)
    assert.equal(carbon.diversion_emissions_data.total_kgCO2e_per_day, 500);

    // 5. Social cost of carbon check (6.3936 * 1.5 inr_rate = 9.5904)
    assert.equal(carbon.social_cost_data.calculated_scc_local, 9.5904);
});


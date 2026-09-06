/**
 * Projects created on the web (not imported from a desktop .3ps) must reach
 * the calculation payload and the report with the values the user entered.
 * Regression coverage for the 2026-09-06 end-to-end QA findings BUG-01…04.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeTrafficData, pickTrafficField } from '../src/utils/projectPageSchema.js';
import { deriveTrafficAndRoadData, flattenTrafficData } from '../src/utils/projectDerivations.js';
import { desktopChunksForReport } from '../src/gui/components/outputs/reportChunks.js';
import { buildReportDocument } from '../src/report/reportDocument.js';

// What the Traffic Data page saved before the flat mirror existed: only the
// nested sub-objects (this is the QA tester's project shape).
const webTraffic = {
    calculation_mode: 'INDIA',
    vehicles: {
        small_cars: { vehicles_per_day: 1200, accident_percentage: 30, pwr: 0 },
        big_cars: { vehicles_per_day: 300, accident_percentage: 10, pwr: 0 },
        two_wheelers: { vehicles_per_day: 1500, accident_percentage: 40, pwr: 0 },
        o_buses: { vehicles_per_day: 100, accident_percentage: 5, pwr: 0 },
        d_buses: { vehicles_per_day: 20, accident_percentage: 1, pwr: 0 },
        lcv: { vehicles_per_day: 200, accident_percentage: 5, pwr: 0 },
        hcv: { vehicles_per_day: 150, accident_percentage: 6, pwr: 7.22 },
        mcv: { vehicles_per_day: 50, accident_percentage: 3, pwr: 8 },
    },
    alternate_road: { alternate_road_carriageway: 'Two Lane', carriage_width_in_m: 7, hourly_capacity: 1200 },
    severity: { severity_minor: 80, severity_major: 15, severity_fatal: 5 },
    road_params: {
        road_roughness_mm_per_km: 2000, road_rise_m_per_km: 0, road_fall_m_per_km: 0,
        additional_reroute_distance_km: 5, additional_travel_time_min: 10,
        crash_rate_accidents_per_million_km: 0.5, work_zone_multiplier: 1,
    },
    num_peak_hours: 2,
    peak_distribution: { peak_hour_1: 0.1, peak_hour_2: 0.1 },
};

const webProject = () => ({
    general_info: { project_name: 'QA Bridge', project_currency: 'INR' },
    bridge_data: { project_country: 'India', analysis_period: 60 },
    traffic_data: webTraffic,
    foundation_data: [{
        id: 'foundation-1', name: 'Excavation',
        rows: [
            { id: 'row-exc', workName: 'Excavation', qty: 100, unit: 'm³ — Cubic Metre', rate: 500, source: 'QA', carbonEmission: null },
        ],
    }],
    superstructure_data: [{
        id: 'super-1', name: 'Girder',
        rows: [
            { id: 'row-steel', workName: 'Steel girders', qty: 45000, unit: 'kg — Kilogram', rate: 110, source: 'QA', carbonEmission: { factor: 1.9, perUnit: 'kgCO2e/kg', source: 'QA' } },
            { id: 'row-deck', workName: 'RCC deck', qty: 60, unit: 'm³ — Cubic Metre', rate: 18000, source: 'QA', carbonEmission: { factor: 450, perUnit: 'kgCO2e/m3', source: 'QA' }, conversionFactor: 1 },
        ],
    }],
    carbon_emission_data: {
        material_emissions_data: { excluded_ids: ['superstructure_data-row-deck'] },
        diversion_emissions_data: { mode: 'Calculate by Vehicle', emission_factors: { small_cars: 0.1, big_cars: 0.27, two_wheelers: 0.04, o_buses: 0.45, d_buses: 0.61, lcv: 0.31, hcv: 0.59, mcv: 0.74 } },
    },
    transport_data: {
        vehicles: [{
            id: 'del-1',
            vehicle: { name: 'Truck', capacity: 20, gross_weight: 30, empty_weight: 10, emission_factor: 0.1, is_custom: true },
            route: { origin: 'Steel yard', destination: 'Site', distance_km: 50 },
            materials: [{ uuid: 'superstructure_data-row-steel', kg_factor: 1, material_name: 'Steel girders' }],
            summary: {}, meta: {}, state: {},
        }],
    },
});

test('pickTrafficField: nested wins unless blank, or zero while the flat copy is real', () => {
    assert.equal(pickTrafficField(7.5, 7), 7.5);
    assert.equal(pickTrafficField(0, 7), 7);
    assert.equal(pickTrafficField(undefined, 7), 7);
    assert.equal(pickTrafficField('', '2L'), '2L');
    assert.equal(pickTrafficField(0, 0), 0);
    assert.equal(pickTrafficField(0, undefined), 0);
});

test('BUG-01: web-entered road width and capacity reach the calculation payload', () => {
    const derived = deriveTrafficAndRoadData(webProject());
    assert.equal(derived.carriage_width_in_m, 7);
    assert.equal(derived.hourly_capacity, 1200);
    assert.equal(derived.additional_reroute_distance_km, 5);
    assert.equal(derived.additional_travel_time_min, 10);
    assert.equal(derived.severity_minor, 80);
    assert.equal(derived.crash_rate_accidents_per_million_km, 0.5);
    assert.equal(derived.vehicle_data.small_cars.vehicles_per_day, 1200);
});

test('BUG-01: a form edit (nested) beats a stale desktop flat key; an untouched import keeps the flat value', () => {
    const edited = deriveTrafficAndRoadData({ ...webProject(), traffic_data: { ...webTraffic, carriage_width_in_m: 7, alternate_road: { ...webTraffic.alternate_road, carriage_width_in_m: 7.5 } } });
    assert.equal(edited.carriage_width_in_m, 7.5);
    const imported = deriveTrafficAndRoadData({ ...webProject(), traffic_data: { ...webTraffic, carriage_width_in_m: 9, hourly_capacity: 2900, alternate_road: { carriage_width_in_m: 0, hourly_capacity: 0 } } });
    assert.equal(imported.carriage_width_in_m, 9);
    assert.equal(imported.hourly_capacity, 2900);
});

test('normalizeTrafficData seeds the form sub-objects from desktop flat keys', () => {
    const normalized = normalizeTrafficData({ carriage_width_in_m: 14, hourly_capacity: 2900, severity_minor: 60, additional_reroute_distance_km: 3, alternate_road_carriageway: '4L' });
    assert.equal(normalized.alternate_road.carriage_width_in_m, 14);
    assert.equal(normalized.alternate_road.hourly_capacity, 2900);
    assert.equal(normalized.alternate_road.alternate_road_carriageway, '4L');
    assert.equal(normalized.severity.severity_minor, 60);
    assert.equal(normalized.road_params.additional_reroute_distance_km, 3);
    assert.equal(normalized.road_params.road_roughness_mm_per_km, 2000);
});

test('flattenTrafficData exposes the web sub-objects under the desktop keys without touching real flat values', () => {
    const flat = flattenTrafficData(webTraffic);
    assert.equal(flat.carriage_width_in_m, 7);
    assert.equal(flat.hourly_capacity, 1200);
    assert.equal(flat.additional_reroute_distance_km, 5);
    assert.equal(flat.vehicle_data.hcv.pwr, 7.22);
    assert.deepEqual(flat.peak_hour_distribution, { peak_hour_1: 0.1, peak_hour_2: 0.1 });
    assert.equal(flat.mode, 'INDIA');
    const desktop = flattenTrafficData({ carriage_width_in_m: 9, alternate_road: { carriage_width_in_m: 0 }, vehicle_data: { hcv: { pwr: 1 } }, vehicles: { hcv: { pwr: 2 } } });
    assert.equal(desktop.carriage_width_in_m, 9);
    assert.equal(desktop.vehicle_data.hcv.pwr, 1);
});

const findSection = (doc, id) => {
    const stack = [...doc.inputSections];
    while (stack.length) {
        const s = stack.shift();
        if (s.id === id) return s;
        if (s.children) stack.push(...s.children);
    }
    return null;
};

test('BUG-02: report shows the traffic geometry and the diversion emissions the page computed', () => {
    const doc = buildReportDocument(webProject(), { results: null, currency: 'INR' });
    const road = findSection(doc, 'traffic-road');
    const rowText = road.rows.map((r) => `${r.label}=${r.value}`).join('|');
    assert.match(rowText, /Rerouting Road Configuration=Two Lane/);
    assert.match(rowText, /Carriageway Width=7 \(m\)/);
    assert.match(rowText, /Road Hourly Capacity=1200 \(PCU\/hr\)/);
    assert.match(rowText, /Rerouting Distance=5 \(km\)/);
    assert.match(rowText, /Minor Injury=80 \(%\)/);
    const diversion = findSection(doc, 'traffic-diversion');
    assert.match(diversion.caption, /Detour: 5\.00 km/);
    // 1200 small cars × 0.10 × 5 km = 600 kg/day for the first row
    assert.deepEqual(diversion.rows[0], ['Small Car', '1,200', '0.10', '600.00']);
    assert.equal(diversion.total, '2528.50');
});

test('BUG-03: web materials with complete factor data are included; user exclusions say so', () => {
    const chunks = desktopChunksForReport(webProject(), { results: null, currency: 'INR' });
    const [steel, deck] = chunks.str_super_structure.Girder;
    assert.equal(steel.state.included_in_carbon_emission, true);
    assert.equal(deck.state.included_in_carbon_emission, false);
    assert.equal(deck.values.exclusion_reason.carbon, 'Manually Excluded');
    const [excavation] = chunks.str_foundation.Excavation;
    assert.equal(excavation.state.included_in_carbon_emission, false);
    assert.equal(excavation.values.exclusion_reason.carbon, 'Incomplete Data');

    const doc = buildReportDocument(webProject(), { results: null, currency: 'INR' });
    const material = findSection(doc, 'material');
    assert.equal(material.included.length, 1);
    assert.equal(material.included[0].rows[0].material, 'Steel girders');
    assert.equal(material.included[0].rows[0].total, '85,500.00');
    const excludedNames = material.excluded.flatMap((g) => g.rows.map((r) => `${r.material}:${r.reason}`));
    assert.ok(excludedNames.includes('RCC deck:Manually Excluded'));
    assert.ok(excludedNames.includes('Excavation:Incomplete Data'));
});

test('BUG-04: web transport deliveries resolve their material and emissions in the report', () => {
    const doc = buildReportDocument(webProject(), { results: null, currency: 'INR' });
    const transport = findSection(doc, 'transport');
    assert.equal(transport.deliveries.length, 1);
    const [delivery] = transport.deliveries;
    assert.equal(delivery.rows[0].material, 'Steel girders');
    assert.equal(delivery.rows[0].qtyKg, '45,000.00');
    assert.equal(delivery.rows[0].trips, '3.00');
    // (30 + 10) t × 3 trips × 50 km × 0.1 = 600 kgCO2e
    assert.equal(delivery.rows[0].emissions, '600.00');
    assert.equal(delivery.summary.total, '600.00');
});

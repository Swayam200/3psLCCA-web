/**
 * Desktop parity for traffic-mode resolution
 * (gui/components/carbon_emission/widgets/traffic_emissions.py
 * _load_traffic_context): an explicitly stored mode wins; an empty mode
 * falls back to INDIA when bridge_data.project_country is INDIA —
 * bridge_data ONLY, so web can never disagree with desktop on the same file.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveTrafficMode, computeTrafficReroutingData } from '../src/gui/components/carbon_emission/carbonUtils.js';
import { deriveTrafficAndRoadData } from '../src/utils/projectDerivations.js';

test('empty mode + bridge_data India falls back to INDIA', () => {
    const project = { traffic_data: {}, bridge_data: { project_country: 'India ' } };
    assert.equal(resolveTrafficMode(project), 'INDIA');
    assert.equal(computeTrafficReroutingData(project).mode, 'Calculate by Vehicle');
});

test('empty mode + non-India country stays GLOBAL', () => {
    const project = { traffic_data: {}, bridge_data: { project_country: 'USA' } };
    assert.equal(resolveTrafficMode(project), 'GLOBAL');
    assert.equal(computeTrafficReroutingData(project).mode, 'Enter Directly');
});

test('an explicitly stored mode wins even for an India project', () => {
    const project = {
        traffic_data: { mode: 'global' },
        bridge_data: { project_country: 'INDIA' },
    };
    assert.equal(resolveTrafficMode(project), 'GLOBAL');
});

test('desktop-faithful: general_info country alone does NOT trigger the fallback', () => {
    // Desktop reads only bridge_data.project_country. If web also honored
    // general_info here, the two apps could compute different rerouting
    // emissions for the same project file.
    const project = { traffic_data: {}, general_info: { project_country: 'INDIA' } };
    assert.equal(resolveTrafficMode(project), 'GLOBAL');
});

test('mode is read from traffic_and_road_data when the derived chunk is present', () => {
    const project = { traffic_and_road_data: { mode: 'INDIA' } };
    assert.equal(resolveTrafficMode(project), 'INDIA');
});

test('legacy calculation_mode still resolves when mode is absent', () => {
    const project = { traffic_data: { calculation_mode: 'india' } };
    assert.equal(resolveTrafficMode(project), 'INDIA');
});

test('deriveTrafficAndRoadData stamps the resolved fallback mode', () => {
    const project = {
        traffic_data: {},
        bridge_data: { project_country: 'INDIA' },
    };
    assert.equal(deriveTrafficAndRoadData(project).mode, 'INDIA');

    const abroad = { traffic_data: {}, bridge_data: { project_country: 'FRANCE' } };
    assert.equal(deriveTrafficAndRoadData(abroad).mode, 'GLOBAL');
});

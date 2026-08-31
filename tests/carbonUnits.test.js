/**
 * Desktop parity for carbon-unit resolution
 * (gui/components/structure/registry/material_entry.py resolve_carbon_denom).
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveCarbonDenom, denomToWebUnit, mentionsCo2 } from '../src/utils/carbonUnits.js';

test('resolveCarbonDenom: bare _den column wins when present', () => {
    assert.equal(resolveCarbonDenom({ carbon_emission_units_den: 'kg' }), 'kg');
    assert.equal(resolveCarbonDenom({ carbon_emission_units_den: ' cum ' }), 'cum');
    // _den wins over the ratio column, like desktop.
    assert.equal(
        resolveCarbonDenom({ carbon_emission_units_den: 'MT', carbon_emission_units: 'kgCO2/kg' }),
        'MT',
    );
});

test('resolveCarbonDenom: ratio in carbon_emission_units yields its denominator', () => {
    assert.equal(resolveCarbonDenom({ carbon_emission_units: 'kgCO2/kg' }), 'kg');
    assert.equal(resolveCarbonDenom({ carbon_emission_units: 'kgCO₂e/cum' }), 'cum');
    // Split on the LAST slash, like desktop's rsplit("/", 1).
    assert.equal(resolveCarbonDenom({ carbon_emission_units: 'kg/CO2/MT' }), 'MT');
    // A value with no "/" is already bare and passes through unchanged.
    assert.equal(resolveCarbonDenom({ carbon_emission_units: 'kg' }), 'kg');
});

test('resolveCarbonDenom: empty-ish values fall through like desktop `not in (None, "", 0)`', () => {
    assert.equal(resolveCarbonDenom({}), null);
    assert.equal(resolveCarbonDenom({ carbon_emission_units_den: '', carbon_emission_units: null }), null);
    assert.equal(resolveCarbonDenom({ carbon_emission_units_den: 0, carbon_emission_units: 'kgCO2e/kg' }), 'kg');
});

test('denomToWebUnit maps the SOR codes the web app displays', () => {
    assert.equal(denomToWebUnit('cum'), 'm³');
    assert.equal(denomToWebUnit('kg'), 'kg');
    assert.equal(denomToWebUnit('MT'), 't');
    // Unknown codes return null so callers leave their current unit untouched.
    assert.equal(denomToWebUnit('sqm'), null);
    assert.equal(denomToWebUnit(null), null);
});

test('mentionsCo2 catches all casings including the subscript character', () => {
    assert.equal(mentionsCo2('kgCO2e/kg'), true);
    assert.equal(mentionsCo2('kgCO₂e/cum'), true);
    assert.equal(mentionsCo2('kg'), false);
    assert.equal(mentionsCo2(''), false);
});

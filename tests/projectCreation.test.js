/**
 * Project creation carries the optional SOR database choice into
 * general_info.sor_database — the field the Add Material search reads.
 * Optional means optional: omitting it must produce a valid project with an
 * empty selection, changeable later in General Information.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import { buildProjectFromCreation, mapCreationToGeneralInfo } from '../src/utils/projectCreation.js';

const BASE = { name: 'Test Bridge', country: 'India', currency: 'INR', unitSystem: 'Metric (SI)' };

test('creation with an SOR choice lands in general_info.sor_database', () => {
    const project = buildProjectFromCreation({ ...BASE, sorDatabase: 'INDIA/Maharashtra/Mumbai-2023' });
    assert.equal(project.general_info.sor_database, 'INDIA/Maharashtra/Mumbai-2023');
    assert.equal(project.general_info.project_name, 'Test Bridge');
});

test('creation without an SOR choice is valid and leaves it empty', () => {
    const project = buildProjectFromCreation(BASE);
    assert.equal(project.general_info.sor_database, '');
    assert.equal(project.name, 'Test Bridge');
    assert.equal(project.currency, 'INR');
});

test('mapCreationToGeneralInfo tolerates missing fields entirely', () => {
    const info = mapCreationToGeneralInfo({});
    assert.equal(info.sor_database, '');
    assert.equal(info.project_name, '');
});

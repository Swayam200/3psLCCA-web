/**
 * The Add Material dialog's search, as pure functions. The user-facing bug
 * was "sometimes the data doesn't show up": a stored SOR key that missed the
 * exact DB_MAP lookup, or zero matches rendered as pure silence. The lookup
 * is now tolerant and the component always answers — these tests pin the
 * matching behavior itself.
 */
import assert from 'node:assert/strict';
import test from 'node:test';
import {
    normalize, tokenize, tokenMatches, resolveDbKey, searchMaterials, MIN_QUERY_LENGTH,
} from '../src/gui/components/constructionworkdata/materialSearch.js';

const DB = [
    {
        sheetName: 'Foundation',
        type: 'Substructure',
        data: [
            { name: 'Plain Cement Concrete (M15)', unit: 'cum', rate: 6600 },
            { name: 'Steel Rebar (HYSD) 500mm Large', unit: 'MT', rate: 78000 },
        ],
    },
    {
        sheetName: 'Girders',
        type: 'Superstructure',
        data: [
            { name: 'Structural Steel IS 2062', unit: 'MT', rate: 92000 },
            { name: 'Plain Cement Concrete (M15) Deck', unit: 'cum', rate: 7000 },
        ],
    },
];

test('normalization folds punctuation and case like the desktop GUI', () => {
    assert.equal(normalize('Plain Cement Concrete (M15)'), 'plain cement concrete m15');
    assert.deepEqual(tokenize('Steel-Rebar/HYSD'), ['steel', 'rebar', 'hysd']);
});

test('concatenated unit tokens match through their parts', () => {
    assert.equal(tokenMatches('500mm', 'steel rebar hysd 500mm large'), true);
    assert.equal(tokenMatches('500mm', 'steel rebar hysd 500 mm large'), true);
    assert.equal(tokenMatches('600mm', 'steel rebar hysd 500 mm large'), false);
});

test('all query tokens must match — partial hits are not results', () => {
    const hits = searchMaterials(DB, 'cement granite', 'Foundation');
    assert.equal(hits.length, 0);
});

test('queries below the minimum length return nothing', () => {
    assert.equal(searchMaterials(DB, 'c', 'Foundation').length, 0);
    assert.equal(MIN_QUERY_LENGTH, 2);
});

test('current construction section ranks first for equal matches', () => {
    const hits = searchMaterials(DB, 'cement concrete', 'Girders');
    assert.equal(hits.length, 2);
    assert.equal(hits[0].sheetName, 'Girders', 'section-relevant sheet must rank first');
});

test('resolveDbKey tolerates case and whitespace drift, rejects unknowns', () => {
    const keys = ['INDIA/Bihar/Darbhanga-2025', 'INDIA/Maharashtra/Mumbai-2023'];
    assert.equal(resolveDbKey(keys, 'INDIA/Bihar/Darbhanga-2025'), 'INDIA/Bihar/Darbhanga-2025');
    assert.equal(resolveDbKey(keys, '  india/bihar/darbhanga-2025 '), 'INDIA/Bihar/Darbhanga-2025');
    assert.equal(resolveDbKey(keys, 'INDIA / Maharashtra / Mumbai-2023'), 'INDIA/Maharashtra/Mumbai-2023');
    assert.equal(resolveDbKey(keys, 'INDIA/Karnataka/Bangalore-2024'), null);
    assert.equal(resolveDbKey(keys, ''), null);
});

test('searchMaterials survives a missing database', () => {
    assert.deepEqual(searchMaterials(undefined, 'cement', 'Foundation'), []);
    assert.deepEqual(searchMaterials(null, 'cement', 'Foundation'), []);
});

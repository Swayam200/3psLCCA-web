/**
 * Desktop display-format parity (gui/components/utils/display_format.py).
 * The expected strings follow desktop's current behavior: western suffixes
 * for all currencies ("21.13 million"), western comma grouping in tables.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fmtCurrency, fmtShort, currencyNote } from '../src/gui/components/outputs/displayFormat.js';

test('fmtShort: western suffix mode like desktop fmt_short', () => {
    assert.equal(fmtShort(21_130_458.89), '21.13 million');
    assert.equal(fmtShort(1_000_000), '1 million');
    assert.equal(fmtShort(500_000), '0.50 million'); // million triggers at 0.1M, like desktop
    assert.equal(fmtShort(-216_231.12), '-0.22 million');
    assert.equal(fmtShort(0), '0');
    assert.equal(fmtShort(12_600_000, true), '12.60M');
});

test('fmtCurrency: comma / short / both styles like desktop fmt_currency', () => {
    assert.equal(fmtCurrency(6_561_474.31, 'INR', { decimals: 2 }), '6,561,474.31');
    assert.equal(fmtCurrency(-66_593.88, 'INR', { decimals: 2 }), '-66,593.88');
    assert.equal(fmtCurrency(21_130_458.89, 'INR', { decimals: 0, style: 'short' }), '21.13 million');
    assert.equal(
        fmtCurrency(1_500_000, 'INR', { decimals: 0, style: 'both' }),
        '1,500,000 (1.50 million)',
    );
});

test('currencyNote matches desktop', () => {
    assert.equal(currencyNote('INR'), 'All values in INR');
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { fmt, fmtPlain, fmtInt, EMDASH } from '../src/report/reportFormat.js';

test('fmt rounds like Python format (binary half-way cases round down)', () => {
    // Desktop prints 0.975 t as "0.97" (f"{0.975:,.2f}"); Intl would say 0.98.
    assert.equal(fmt(0.975), '0.97');
    assert.equal(fmt(2.675), '2.67');
    assert.equal(fmtPlain(0.975), '0.97');
});

test('fmt groups thousands and keeps sign and decimals', () => {
    assert.equal(fmt(1234.5), '1,234.50');
    assert.equal(fmt(-1234567.891), '-1,234,567.89');
    assert.equal(fmt(0), '0.00');
    assert.equal(fmt(999), '999.00');
    assert.equal(fmt('23085113.82'), '23,085,113.82');
    assert.equal(fmt(1.72104, 4), '1.7210');
});

test('fmt and fmtInt treat empty values as an em dash', () => {
    assert.equal(fmt(''), EMDASH);
    assert.equal(fmt(null), EMDASH);
    assert.equal(fmt('n/a'), EMDASH);
    assert.equal(fmtInt(7271.4), '7,271');
});

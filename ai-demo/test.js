/**
 * End-to-end test for the demo API.
 *
 *   node ai-demo/test.js          (server must be running on PORT / 4173)
 *
 * Covers every CRUD path, every AI tool, and the rejection paths — including
 * the ones that matter most for an AI feature: an out-of-range parameter and
 * an ambiguous row reference must be REFUSED, not guessed at.
 */

import assert from 'node:assert/strict';
import test from 'node:test';

const BASE = `http://localhost:${process.env.PORT || 4173}`;

const call = async (path, options = {}) => {
    const res = await fetch(`${BASE}${path}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    return { status: res.status, body: await res.json() };
};

const ai = (prompt, settings) => call('/api/ai/command', {
    method: 'POST',
    body: JSON.stringify({ prompt, settings }),
});
const reset = () => call('/api/reset', { method: 'POST' });

const rowsOf = (body, key) =>
    body.sections.find((s) => s.key === key).rows.filter((r) => !r.state.in_trash);

test('reset is reproducible', async () => {
    const { body: first } = await reset();
    await ai('Increase all foundation rates by 25%');
    const { body: second } = await reset();
    assert.deepEqual(
        rowsOf(second, 'foundation_data').map((r) => [r.id, r.qty, r.rate]),
        rowsOf(first, 'foundation_data').map((r) => [r.id, r.qty, r.rate]),
    );
});

test('seed state is coherent', async () => {
    const { body } = await reset();
    assert.equal(body.sections.length, 4);
    for (const section of body.sections) assert.equal(section.rows.length, 5);
    assert.equal(body.results.status, 'success');
    assert.ok(body.results.totals.total_npv > 0);
    // The kg-factor bug this dataset was fixed for: embodied carbon must stay
    // in the thousands of tonnes, not the hundreds of thousands.
    assert.ok(
        body.results.totals.embodied_carbon_t > 1000 && body.results.totals.embodied_carbon_t < 20000,
        `embodied carbon out of plausible range: ${body.results.totals.embodied_carbon_t}`,
    );
});

test('CREATE adds a row and moves the totals', async () => {
    const { body: before } = await reset();
    const { status, body } = await call('/api/sections/foundation_data/materials', {
        method: 'POST',
        body: JSON.stringify({ workName: 'Test anchor bolt', qty: 100, unit: 'nos', rate: 250, carbonFactor: 0.01 }),
    });
    assert.equal(status, 201);
    assert.equal(rowsOf(body, 'foundation_data').length, 6);
    assert.equal(
        Math.round(body.results.totals.construction_cost - before.results.totals.construction_cost),
        25000,
    );
});

test('CREATE rejects a negative quantity', async () => {
    const { status, body } = await call('/api/sections/foundation_data/materials', {
        method: 'POST',
        body: JSON.stringify({ workName: 'Bad row', qty: -5, unit: 'nos', rate: 10 }),
    });
    assert.equal(status, 400);
    assert.match(body.error, /non-negative/);
});

test('UPDATE changes a field', async () => {
    const { body: seed } = await reset();
    const target = rowsOf(seed, 'substructure_data')[0];
    const { status, body } = await call(`/api/materials/${target.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ rate: 12000 }),
    });
    assert.equal(status, 200);
    assert.equal(rowsOf(body, 'substructure_data')[0].rate, 12000);
});

test('DELETE is a soft delete and RESTORE brings the row back', async () => {
    const { body: seed } = await reset();
    const target = rowsOf(seed, 'miscellaneous_data')[0];

    const { body: deleted } = await call(`/api/materials/${target.id}`, { method: 'DELETE' });
    assert.equal(rowsOf(deleted, 'miscellaneous_data').length, 4);
    assert.ok(deleted.results.totals.construction_cost < seed.results.totals.construction_cost);

    const { body: restored } = await call(`/api/materials/${target.id}/restore`, { method: 'POST' });
    assert.equal(rowsOf(restored, 'miscellaneous_data').length, 5);
    assert.equal(
        Math.round(restored.results.totals.construction_cost),
        Math.round(seed.results.totals.construction_cost),
    );
});

test('parameter changes are range-checked', async () => {
    await reset();
    const ok = await call('/api/parameters', { method: 'PATCH', body: JSON.stringify({ name: 'discount_rate', value: 9 }) });
    assert.equal(ok.status, 200);
    assert.equal(ok.body.project.financial_data.discount_rate, 9);

    const bad = await call('/api/parameters', { method: 'PATCH', body: JSON.stringify({ name: 'discount_rate', value: 900 }) });
    assert.equal(bad.status, 400);

    const unknown = await call('/api/parameters', { method: 'PATCH', body: JSON.stringify({ name: 'profit_margin', value: 5 }) });
    assert.equal(unknown.status, 400);
    assert.match(unknown.body.error, /Unknown parameter/);
});

test('UNDO reverts the last change', async () => {
    const { body: seed } = await reset();
    await call('/api/parameters', { method: 'PATCH', body: JSON.stringify({ name: 'analysis_period', value: 100 }) });
    const { body } = await call('/api/undo', { method: 'POST' });
    assert.equal(body.project.financial_data.analysis_period, seed.project.financial_data.analysis_period);
});

// ------------------------------------------------------------------ AI ----

test('AI: bulk scale hits only the named section', async () => {
    const { body: seed } = await reset();
    const { body } = await ai('Increase all foundation rates by 8%');

    assert.equal(body.rejected.length, 0, JSON.stringify(body.rejected));
    assert.equal(body.applied[0].name, 'scale_rates');

    const before = rowsOf(seed, 'foundation_data')[0].rate;
    const after = rowsOf(body, 'foundation_data')[0].rate;
    assert.ok(Math.abs(after / before - 1.08) < 0.001, `${before} → ${after}`);

    // Other sections untouched.
    assert.equal(rowsOf(body, 'superstructure_data')[0].rate, rowsOf(seed, 'superstructure_data')[0].rate);
    assert.ok(body.delta.construction_cost > 0);
});

test('AI: parameter tweak re-runs the calculation', async () => {
    await reset();
    const { body } = await ai('Set the discount rate to 8');
    assert.equal(body.applied[0].name, 'set_parameter');
    assert.equal(body.project.financial_data.discount_rate, 8);
    // A higher discount rate shrinks the present value of future costs.
    assert.ok(body.after.totals.maintenance_pv < body.before.totals.maintenance_pv);
});

test('AI: create adds a row through the same validation as the UI', async () => {
    await reset();
    const { body } = await ai('Add 240 m³ of RCC M40 pier shaft to substructure at 9500');
    assert.equal(body.rejected.length, 0, JSON.stringify(body.rejected));
    assert.equal(body.applied[0].name, 'create_material');

    const added = rowsOf(body, 'substructure_data').at(-1);
    assert.equal(added.qty, 240);
    assert.equal(added.rate, 9500);
    assert.equal(added.unit, 'm³');
    assert.match(added.workName, /pier shaft/i);
    assert.equal(Math.round(body.delta.construction_cost), 2280000);
});

test('AI: update by fuzzy name match', async () => {
    await reset();
    const { body } = await ai('Change the MS railing quantity to 520');
    assert.equal(body.rejected.length, 0, JSON.stringify(body.rejected));
    const row = rowsOf(body, 'miscellaneous_data').find((r) => /MS railing/i.test(r.workName));
    assert.equal(row.qty, 520);
});

test('AI: delete by fuzzy name match', async () => {
    await reset();
    const { body } = await ai('Delete the drainage spout');
    assert.equal(body.rejected.length, 0, JSON.stringify(body.rejected));
    assert.ok(!rowsOf(body, 'miscellaneous_data').some((r) => /drainage/i.test(r.workName)));
    assert.ok(body.delta.construction_cost < 0);
});

test('AI: ambiguous reference is refused, not guessed', async () => {
    await reset();
    // "Reinforcement steel Fe500D" exists in both foundation and substructure.
    const { body } = await ai('Delete the reinforcement steel');
    assert.equal(body.applied.length, 0);
    assert.equal(body.rejected.length, 1);
    assert.match(body.rejected[0].error, /ambiguous/i);
    // And crucially: nothing changed.
    assert.equal(body.delta.construction_cost, 0);
});

test('AI: a rejected op does not block the valid ops beside it', async () => {
    await reset();
    const { body } = await ai('Delete the reinforcement steel and set the discount rate to 8');
    // The delete is genuinely ambiguous and must fail; the parameter change is
    // valid and must still land. One bad op does not void the batch.
    assert.equal(body.rejected.length, 1);
    assert.match(body.rejected[0].error, /ambiguous/i);
    assert.equal(body.applied.length, 1);
    assert.equal(body.project.financial_data.discount_rate, 8);
});

test('AI: out-of-range parameter is refused', async () => {
    await reset();
    const { body } = await ai('Set the discount rate to 400');
    assert.equal(body.applied.length, 0);
    assert.equal(body.rejected.length, 1);
    assert.match(body.rejected[0].error, /between 0 and 30/);
});

test('AI: read-only question changes nothing', async () => {
    const { body: seed } = await reset();
    const { body } = await ai('What is the total life-cycle NPV?');
    assert.equal(body.applied.length, 1);
    assert.equal(body.applied[0].readOnly, true);
    assert.equal(
        Math.round(body.results.totals.total_npv),
        Math.round(seed.results.totals.total_npv),
    );
});

test('AI: one prompt can carry several operations', async () => {
    await reset();
    const { body } = await ai('Increase all superstructure rates by 5% and set the analysis period to 75');
    const names = body.applied.map((a) => a.name).sort();
    assert.deepEqual(names, ['scale_rates', 'set_parameter']);
    assert.equal(body.project.financial_data.analysis_period, 75);
});

test('AI edits are attributed to "ai" in the audit log', async () => {
    await reset();
    await ai('Set the discount rate to 7');
    const { body } = await call('/api/state');
    assert.equal(body.audit[0].actor, 'ai');
    assert.match(body.audit[0].detail, /Discount rate/);
});

test('unknown routes 404', async () => {
    const { status } = await call('/api/nope');
    assert.equal(status, 404);
});

// ------------------------------------------------- modes, keys, fallback ---

test('mode routing: rules only never leaves the machine', async () => {
    await reset();
    const { body } = await ai('Set the discount rate to 8', { mode: 'rules' });
    assert.equal(body.provider, 'rules');
    assert.deepEqual(body.route, [{ step: 'rules', outcome: 'ok' }]);
    assert.equal(body.project.financial_data.discount_rate, 8);
});

test('mode routing: a mode needing a key degrades to rules instead of failing', async () => {
    await reset();
    // No key is configured in the test environment.
    const { body } = await ai('Set the discount rate to 8', { mode: 'model', provider: 'gemini' });
    assert.equal(body.mode, 'model');
    assert.equal(body.effectiveMode, 'rules');
    assert.equal(body.degraded, true);
    // Degraded or not, the request still did the right thing.
    assert.equal(body.project.financial_data.discount_rate, 8);
});

test('mode routing: rules-first answers locally when the rules match', async () => {
    await reset();
    const { body } = await ai('Increase all foundation rates by 8%', { mode: 'rules-first' });
    assert.equal(body.provider, 'rules');
    // Only one hop — the model was never called, which is the point of the mode.
    assert.equal(body.route.length, 1);
    assert.equal(body.route[0].outcome, 'ok');
});

test('rules report "unparsed" for phrasings they do not know', async () => {
    await reset();
    const { body } = await ai('Could you possibly reconsider the procurement strategy for us?');
    assert.equal(body.applied.length, 1);
    assert.equal(body.applied[0].readOnly, true);
    assert.match(body.applied[0].summary, /could not parse/i);
    assert.equal(body.route.at(-1).outcome, 'unparsed');
});

test('status reports modes and providers without leaking a key', async () => {
    const { status, body } = await call('/api/ai/status', {
        method: 'POST',
        body: JSON.stringify({ settings: { mode: 'rules-first', provider: 'claude' } }),
    });
    assert.equal(status, 200);
    assert.equal(body.mode, 'rules-first');
    assert.equal(body.provider, 'claude');
    assert.ok(body.modes.length >= 4);
    assert.ok(body.providers.length >= 2);
    // The status payload must never carry the secret itself.
    assert.equal(JSON.stringify(body).includes('x-provider-key'), false);
    assert.ok(!('apiKey' in body));
});

test('a browser-supplied key is accepted from localhost and never echoed back', async () => {
    const fakeKey = 'AIzaTestKeyNotReal000000000000000000';
    const res = await fetch(`${BASE}/api/ai/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-provider-key': fakeKey },
        body: JSON.stringify({ settings: { mode: 'model', provider: 'gemini' } }),
    });
    const body = await res.json();
    assert.equal(res.status, 200);
    assert.equal(body.hasKey, true);
    assert.equal(body.keySource, 'settings');
    // Fingerprint only — at most the last four characters.
    assert.equal(body.keyFingerprint, '••••0000');
    assert.equal(JSON.stringify(body).includes(fakeKey), false);
});

// NOTE: this one makes a real outbound call (that is the endpoint's job).
// It passes offline too — a network failure is still a clean, key-free "no".
test('key test endpoint reports failure without exposing the key', async () => {
    const fakeKey = 'AIzaDefinitelyInvalidKey0000000000000';
    const res = await fetch(`${BASE}/api/ai/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-provider-key': fakeKey },
        body: JSON.stringify({ settings: { provider: 'gemini' } }),
    });
    const body = await res.json();
    assert.equal(res.status, 200);
    assert.equal(body.ok, false);
    assert.ok(body.error.length > 0);
    // The whole point: whatever the upstream said, the key is not in it.
    assert.equal(JSON.stringify(body).includes(fakeKey), false);
});

test('key test with no key at all is a clean no', async () => {
    const { body } = await call('/api/ai/test', {
        method: 'POST',
        body: JSON.stringify({ settings: { provider: 'claude' } }),
    });
    assert.equal(body.ok, false);
    assert.match(body.error, /No API key/i);
});

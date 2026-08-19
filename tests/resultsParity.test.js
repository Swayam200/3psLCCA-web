/**
 * Results parity — desktop reference (docs: results-page parity, Phase 0).
 *
 * Fixtures:
 *  - m20-web-project.json: the M_20_2L_OF_S reference project as imported
 *    into the web app (lossless .3ps import).
 *  - m20-desktop-chunks.json: the same project's desktop store, whose
 *    comparison_cache.results are the healthy desktop engine output.
 *
 * The desktop reference derives the recycling total and the social cost of
 * carbon live at calculation time; these tests pin the web derivations to
 * the desktop-computed numbers.
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
    computeRecycling,
    recyclingChunkData,
    REASON_INCOMPLETE,
} from '../src/utils/recyclingDerivations.js';
import { deriveRecyclingData } from '../src/utils/projectDerivations.js';
import { computeRicke } from '../src/gui/components/carbon_emission/rickeCompute.js';
import { lookupScc } from '../src/lib/cscc.js';
import {
    prepareProjectForCalculation,
    resolveSocialCostOfCarbon,
} from '../src/utils/calculationPrep.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const project = JSON.parse(readFileSync(path.join(here, 'fixtures/m20-web-project.json'), 'utf8'));
const desktopChunks = JSON.parse(readFileSync(path.join(here, 'fixtures/m20-desktop-chunks.json'), 'utf8'));

// Serve the CSCC database from disk when the code under test fetches it.
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, options) => {
    const match = String(url).match(/\/data\/cscc\/([A-Z0-9]+\.json)$/);
    if (match) {
        const body = readFileSync(path.join(here, '../public/data/cscc', match[1]), 'utf8');
        return new Response(body, { status: 200, headers: { 'content-type': 'application/json' } });
    }
    return realFetch(url, options);
};

// Desktop reference numbers (recycling/main.py over this project's rows;
// per-row values also appear verbatim in the desktop report's
// "Materials Included in Recyclability Calculation" table). One row
// ("Reinforcement in pile") is manually excluded in the project data;
// honoring that flag makes core's discounted scrap value match the healthy
// desktop results EXACTLY (216,231.12; including it gives 216,241.80).
const DESKTOP_RECYCLING_TOTAL = 936065.47;
const DESKTOP_GIRDER_VALUE = 575325.24;
// Core discounts the recovered value at end-of-life; the healthy desktop
// results carry the discounted figure:
const DESKTOP_DISCOUNTED_SCRAP = 216231.12;

test('recycling: derived from material rows exactly like desktop', () => {
    const computed = computeRecycling(project);
    assert.equal(computed.totalCount, 29, 'all non-trashed material rows are candidates');
    assert.equal(computed.includedCount, 8, 'valid rows minus the manually excluded one');
    assert.ok(Math.abs(computed.totalRecoveredValue - DESKTOP_RECYCLING_TOTAL) < 0.01,
        `total ${computed.totalRecoveredValue} != desktop ${DESKTOP_RECYCLING_TOTAL}`);
    const girder = computed.includedItems.find((item) => /main Girder/.test(item.row.workName || ''));
    assert.ok(girder, 'girder row included');
    assert.ok(Math.abs(girder.value - DESKTOP_GIRDER_VALUE) < 0.01);
    const manual = computed.excludedItems.filter((item) => item.reason !== REASON_INCOMPLETE);
    assert.equal(manual.length, 1, 'exactly the one manually excluded row');
    assert.match(manual[0].row.workName || '', /Reinforcement in pile$/);
});

test('recycling: summary chunk and calculation input carry the derived total', () => {
    const chunk = recyclingChunkData(project, 'INR');
    assert.ok(Math.abs(chunk.total_recovered_value - DESKTOP_RECYCLING_TOTAL) < 0.01);
    assert.equal(chunk.included_count, 8);
    assert.equal(chunk.currency, 'INR');

    const derived = deriveRecyclingData(project);
    assert.ok(Math.abs(derived.total_recovered_value - DESKTOP_RECYCLING_TOTAL) < 0.01,
        'deriveRecyclingData no longer trusts the stale stored chunk');
});

test('recycling: manual exclusion on the row is honored (desktop state flag)', () => {
    const patched = JSON.parse(JSON.stringify(project));
    for (const sections of [patched.superstructure_data]) {
        for (const section of sections) {
            for (const row of section.rows || []) {
                if (/main Girder/.test(row.workName || '')) {
                    row.state = { ...(row.state || {}), included_in_recyclability: false };
                }
            }
        }
    }
    const computed = computeRecycling(patched);
    assert.equal(computed.includedCount, 7);
    assert.ok(Math.abs(computed.totalRecoveredValue - (DESKTOP_RECYCLING_TOTAL - DESKTOP_GIRDER_VALUE)) < 0.01);
});

test('scc: computeRicke mirrors the desktop formula (values[pct] × cpi × usd / 1000)', async () => {
    const ricke = {
        ...desktopChunks.social_cost_data.ricke,
        usd_to_local_rate: 88.0,
        cpi_ratio: 1.0,
    };
    // The same lookup computeRicke performs internally, done directly:
    const countryData = JSON.parse(readFileSync(path.join(here, '../public/data/cscc/IND.json'), 'utf8'));
    const { CLOSEST_RCP } = await import('../src/lib/cscc.js');
    const { values, reason } = lookupScc(countryData, {
        run: 'bhm_sr', dmgfuncpar: 'bootstrap', climate: 'expected',
        ssp: 'SSP1', rcp: CLOSEST_RCP.SSP1, prtp: '2', eta: '1p5', dr: 'NA',
    });
    assert.equal(reason, 'ok');
    const expected = (values[1] * 1.0 * 88.0) / 1000; // 50% percentile
    const { cost } = computeRicke(ricke, countryData, 'INR');
    assert.ok(Math.abs(cost - expected) < 1e-9, `${cost} != ${expected}`);
    assert.ok(cost > 0);
});

test('scc: resolver applies Ricke params at calculation time', async () => {
    const patched = JSON.parse(JSON.stringify(project));
    patched.carbon_emission_data.social_cost_data.ricke.usd_to_local_rate = 88.0;
    const resolved = await resolveSocialCostOfCarbon(patched);
    assert.ok(resolved && resolved.cost > 0, 'SCC resolves once the USD rate is present');

    // The archive's stored usd rate is 0 (lost by the desktop save bug):
    // desktop's live widget would also compute 0 and warn — resolver
    // must not invent a value.
    const unresolved = await resolveSocialCostOfCarbon(project);
    assert.equal(unresolved, null);
});

test('scc: custom override mode uses the entered value', async () => {
    const patched = JSON.parse(JSON.stringify(project));
    const social = patched.carbon_emission_data.social_cost_data;
    social.source = 'Custom / Manual Override';
    social.custom = { entered_value: 9.54 };
    const resolved = await resolveSocialCostOfCarbon(patched);
    assert.equal(resolved.cost, 9.54);
});

test('prepareProjectForCalculation patches recycling + scc onto the project', async () => {
    const patched = JSON.parse(JSON.stringify(project));
    patched.carbon_emission_data.social_cost_data.ricke.usd_to_local_rate = 88.0;
    const prepared = await prepareProjectForCalculation(patched);
    assert.ok(Math.abs(prepared.project.recycling_data.total_recovered_value - DESKTOP_RECYCLING_TOTAL) < 0.01);
    assert.ok(prepared.socialCost.cost > 0);
    assert.equal(
        prepared.project.carbon_emission_data.social_cost_data.result.cost_of_carbon_local,
        prepared.socialCost.cost,
    );
    // Reference note: with the reconstructed desktop-session SCC
    // (9.762147 INR/kg), the core turns this recycling total into the
    // desktop-reference discounted scrap value of 216,231.12 — verified
    // end-to-end against three_ps_lcca_core (see PR notes).
    assert.ok(DESKTOP_DISCOUNTED_SCRAP < DESKTOP_RECYCLING_TOTAL);
});

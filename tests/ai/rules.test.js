import assert from 'node:assert/strict';
import test from 'node:test';

import { generate } from '../../src/lib/ai/providers/rules.js';
import { buildAiContext } from '../../src/lib/ai/tools/context.js';
import { PROJECT_FIXTURE, UNCALCULATED_PROJECT } from './fixtures.js';

const context = buildAiContext(PROJECT_FIXTURE);

const answerOf = async (prompt, ctx = context) => {
    const result = await generate(prompt, { context: ctx });
    assert.equal(result.calls.length, 1);
    assert.equal(result.calls[0].name, 'answer');
    return { text: result.calls[0].args.text, unparsed: Boolean(result.unparsed) };
};

test('total life-cycle cost', async () => {
    const { text, unparsed } = await answerOf('What is the total life-cycle cost?');
    assert.equal(unparsed, false);
    assert.match(text, /15,70,00,000/);       // 157M INR, en-IN grouping
    assert.match(text, /50-year/);
});

test('biggest cost driver names the top display-labelled item', async () => {
    const { text, unparsed } = await answerOf('What is the biggest cost driver?');
    assert.equal(unparsed, false);
    assert.match(text, /Construction Cost/);
    assert.match(text, /Initial Stage/);
});

test('stage breakdown', async () => {
    const { text, unparsed } = await answerOf('How do costs split by stage?');
    assert.equal(unparsed, false);
    assert.match(text, /initial/i);
    assert.match(text, /end of life/i);
});

test('carbon phrasing maps to the environmental pillar', async () => {
    const { text, unparsed } = await answerOf('How much do carbon emissions cost?');
    assert.equal(unparsed, false);
    assert.match(text, /Environmental/i);
    assert.match(text, /1,55,00,000/);        // 15.5M
});

test('validation question reports the warning', async () => {
    const { text } = await answerOf('Were there any validation warnings?');
    assert.match(text, /Traffic growth rate defaulted/);
});

test('engine provenance', async () => {
    const { text } = await answerOf('Which engine calculated this?');
    assert.match(text, /in-browser engine/i);
    assert.match(text, /1\.0\.2/);
});

test('summary composes identity and totals', async () => {
    const { text } = await answerOf('Summarize this project');
    assert.match(text, /Kosi/);
    assert.match(text, /PSC I-girder/);
    assert.match(text, /15,70,00,000/);
});

test('edit attempts get a read-only refusal, not a parse failure', async () => {
    const { text, unparsed } = await answerOf('Set the discount rate to 8');
    assert.equal(unparsed, false);
    assert.match(text, /read-only/i);
});

test('questions about an uncalculated project point to the Results page', async () => {
    const { text } = await answerOf('What is the total cost?', buildAiContext(UNCALCULATED_PROJECT));
    assert.match(text, /No calculation has been run/i);
});

test('unknown phrasing is flagged unparsed for the router, with a helpful message', async () => {
    const { text, unparsed } = await answerOf('Would the stakeholders find this palatable?');
    assert.equal(unparsed, true);
    assert.match(text, /could not parse/i);
});

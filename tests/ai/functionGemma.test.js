import assert from 'node:assert/strict';
import test from 'node:test';

import { parseFunctionCalls, generate } from '../../src/lib/ai/providers/functionGemma.js';

test('parses a single escaped-string call', () => {
    const calls = parseFunctionCalls(
        '<start_function_call>call:answer{text:<escape>The total is X.<escape>}<end_function_call>',
    );
    assert.deepEqual(calls, [{ name: 'answer', args: { text: 'The total is X.' } }]);
});

test('escaped values keep commas, braces and colons intact', () => {
    const calls = parseFunctionCalls(
        '<start_function_call>call:answer{text:<escape>eco: 1, env: 2, social: 3<escape>}<end_function_call>',
    );
    assert.equal(calls[0].args.text, 'eco: 1, env: 2, social: 3');
});

test('parses numbers, booleans and multiple args', () => {
    const calls = parseFunctionCalls(
        '<start_function_call>call:set_parameter{name:<escape>discount_rate<escape>,value:8,flag:true}<end_function_call>',
    );
    assert.deepEqual(calls[0], {
        name: 'set_parameter',
        args: { name: 'discount_rate', value: 8, flag: true },
    });
});

test('parses multiple calls, skips garbage between them', () => {
    const text = 'preamble <start_function_call>call:answer{text:<escape>a<escape>}<end_function_call>'
        + ' chatter <start_function_call>call:answer{text:<escape>b<escape>}<end_function_call>';
    const calls = parseFunctionCalls(text);
    assert.equal(calls.length, 2);
    assert.equal(calls[1].args.text, 'b');
});

test('malformed output parses to no calls', () => {
    assert.deepEqual(parseFunctionCalls('I think the answer is 42.'), []);
    assert.deepEqual(parseFunctionCalls('<start_function_call>call:answer{'), []);
});

test('provider maps unparseable generations to unparsed, not a guess', async () => {
    const result = await generate('whatever', {
        context: {},
        runner: async () => 'The model rambled with no function call.',
    });
    assert.equal(result.unparsed, true);
    assert.match(result.calls[0].args.text, /did not produce a usable tool call/);
});

test('provider returns parsed calls with no fabricated confidence', async () => {
    const result = await generate('whatever', {
        context: {},
        runner: async () =>
            '<start_function_call>call:answer{text:<escape>grounded answer<escape>}<end_function_call>',
    });
    assert.equal(result.unparsed, undefined);
    assert.equal(result.confidence, undefined);
    assert.equal(result.calls[0].args.text, 'grounded answer');
});

test('unknown tools from the model are surfaced for the executor to reject', async () => {
    const result = await generate('whatever', {
        context: {},
        runner: async () =>
            '<start_function_call>call:delete_everything{sure:true}<end_function_call>',
    });
    // The provider passes it through; the EXECUTOR is the safety gate.
    assert.equal(result.calls[0].name, 'delete_everything');
});

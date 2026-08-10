/**
 * Claude provider — real tool use against the Anthropic Messages API.
 *
 * Enable with:  AI_PROVIDER=claude  ANTHROPIC_API_KEY=...  node server.js
 * or by pasting a key into the demo's Settings panel, which arrives here as
 * options.apiKey and is used for that one request only.
 *
 * Same contract as the Gemini and mock providers: in a prompt string, out a
 * list of { name, args }. Only the wire format differs — Anthropic calls the
 * schema field `input_schema` and returns `tool_use` content blocks.
 */

import { TOOLS, systemPrompt } from './tools.js';
import { providerError } from './redact.js';

export const DEFAULT_MODEL = 'claude-sonnet-5';
const ENDPOINT = 'https://api.anthropic.com/v1/messages';

export const envKey = () => process.env.ANTHROPIC_API_KEY || null;
export const defaultModel = () => process.env.ANTHROPIC_MODEL || DEFAULT_MODEL;

export async function generate(prompt, options = {}) {
    const apiKey = options.apiKey || envKey();
    const model = options.model || defaultModel();
    if (!apiKey) throw new Error('No Anthropic API key — paste one in Settings or set ANTHROPIC_API_KEY.');

    const body = {
        model,
        max_tokens: 2048,
        temperature: 0,
        system: systemPrompt(),
        messages: [{ role: 'user', content: prompt }],
        tools: TOOLS.map((tool) => ({
            name: tool.name,
            description: tool.description,
            input_schema: tool.parameters,
        })),
        // "any" forces the model to pick a tool rather than replying in prose.
        tool_choice: { type: 'any' },
    };

    const response = await fetch(ENDPOINT, {
        method: 'POST',
        headers: {
            'content-type': 'application/json',
            'x-api-key': apiKey,
            'anthropic-version': '2023-06-01',
        },
        body: JSON.stringify(body),
    });

    if (!response.ok) {
        throw new Error(providerError('Anthropic API', response.status, await response.text(), apiKey));
    }

    const data = await response.json();
    const blocks = data.content || [];

    const calls = blocks
        .filter((block) => block.type === 'tool_use')
        .map((block) => ({ name: block.name, args: block.input || {} }));

    if (!calls.length) {
        const text = blocks.filter((b) => b.type === 'text').map((b) => b.text).join(' ').trim();
        return {
            calls: [{ name: 'answer', args: { text: text || 'No response from Claude.' } }],
            model,
        };
    }
    return { calls, usage: data.usage, model };
}

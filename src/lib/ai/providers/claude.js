/**
 * Claude provider — tool use against the Anthropic Messages API, called
 * directly from the browser with the user's own key.
 *
 * Same contract as every provider: generate(prompt, opts) → { calls, … }.
 * Only the wire format differs — Anthropic calls the schema field
 * `input_schema` and returns `tool_use` content blocks.
 */

import { providerError } from '../redact.js';

export const DEFAULT_MODEL = 'claude-sonnet-5';
const ENDPOINT = 'https://api.anthropic.com/v1/messages';

export async function generate(prompt, { apiKey, model, system, tools } = {}) {
    if (!apiKey) throw new Error('No Anthropic API key — add one in Settings → AI Assistant.');
    const usedModel = model || DEFAULT_MODEL;

    const body = {
        model: usedModel,
        max_tokens: 1024,
        temperature: 0,
        system,
        messages: [{ role: 'user', content: prompt }],
        tools: (tools || []).map((tool) => ({
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
            // Required for direct browser calls to the Anthropic API.
            'anthropic-dangerous-direct-browser-access': 'true',
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
            model: usedModel,
        };
    }
    return { calls, usage: data.usage, model: usedModel };
}

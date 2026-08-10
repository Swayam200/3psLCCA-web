/**
 * Gemini provider — real function calling against the Generative Language API.
 *
 * Enable with:  AI_PROVIDER=gemini  GEMINI_API_KEY=...  node server.js
 * or by pasting a key into the demo's Settings panel, which arrives here as
 * options.apiKey and is used for that one request only.
 *
 * Note the shape: we hand Gemini the tool declarations from lib/ai/tools.js and
 * read `functionCall` parts back out. We never read the model's prose. If the
 * model returns text only, that text is wrapped into an `answer` call so the
 * downstream code has exactly one thing to handle.
 */

import { TOOLS, systemPrompt } from './tools.js';
import { providerError } from './redact.js';

export const DEFAULT_MODEL = 'gemini-2.5-flash';
const ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models';

export const envKey = () => process.env.GEMINI_API_KEY || null;
export const defaultModel = () => process.env.GEMINI_MODEL || DEFAULT_MODEL;

/** Gemini rejects JSON-Schema keywords it does not know, so trim to its subset. */
const toGeminiSchema = (schema) => {
    if (!schema || typeof schema !== 'object') return schema;
    const out = {};
    for (const [key, value] of Object.entries(schema)) {
        if (key === 'properties') {
            out.properties = Object.fromEntries(
                Object.entries(value).map(([k, v]) => [k, toGeminiSchema(v)]),
            );
        } else if (['type', 'description', 'enum', 'required', 'items'].includes(key)) {
            out[key] = key === 'items' ? toGeminiSchema(value) : value;
        }
    }
    return out;
};

export async function generate(prompt, options = {}) {
    const apiKey = options.apiKey || envKey();
    const model = options.model || defaultModel();
    if (!apiKey) throw new Error('No Gemini API key — paste one in Settings or set GEMINI_API_KEY.');

    const body = {
        systemInstruction: { parts: [{ text: systemPrompt() }] },
        contents: [{ role: 'user', parts: [{ text: prompt }] }],
        tools: [{
            functionDeclarations: TOOLS.map((tool) => ({
                name: tool.name,
                description: tool.description,
                parameters: toGeminiSchema(tool.parameters),
            })),
        }],
        // ANY forces a tool call every turn — the model cannot drift into prose.
        toolConfig: { functionCallingConfig: { mode: 'ANY' } },
        generationConfig: { temperature: 0 },
    };

    const response = await fetch(
        `${ENDPOINT}/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        },
    );

    if (!response.ok) {
        // Gemini puts the key in the query string, so its error bodies can echo
        // it. Redact before this string escapes anywhere.
        throw new Error(providerError('Gemini API', response.status, await response.text(), apiKey));
    }

    const data = await response.json();
    const parts = data?.candidates?.[0]?.content?.parts || [];

    const calls = parts
        .filter((part) => part.functionCall)
        .map((part) => ({ name: part.functionCall.name, args: part.functionCall.args || {} }));

    if (!calls.length) {
        const text = parts.map((p) => p.text).filter(Boolean).join(' ').trim();
        return {
            calls: [{ name: 'answer', args: { text: text || 'No response from Gemini.' } }],
            model,
        };
    }
    return { calls, usage: data.usageMetadata, model };
}

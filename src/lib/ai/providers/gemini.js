/**
 * Gemini provider — function calling against the Generative Language API,
 * called directly from the browser with the user's own key.
 *
 * Contract (shared by every provider):
 *   generate(prompt, { apiKey, model, system, tools }) → { calls, usage, model }
 * where calls is [{ name, args }]. The caller supplies the system prompt and
 * tool declarations (tools/schema.js); this module only speaks the wire format.
 */

import { providerError } from '../redact.js';

export const DEFAULT_MODEL = 'gemini-2.5-flash';
const ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models';

/** Gemini rejects JSON-Schema keywords it does not know — trim to its subset. */
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

export async function generate(prompt, { apiKey, model, system, tools } = {}) {
    if (!apiKey) throw new Error('No Gemini API key — add one in Settings → AI Assistant.');
    const usedModel = model || DEFAULT_MODEL;

    const body = {
        systemInstruction: { parts: [{ text: system }] },
        contents: [{ role: 'user', parts: [{ text: prompt }] }],
        tools: [{
            functionDeclarations: (tools || []).map((tool) => ({
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
        `${ENDPOINT}/${encodeURIComponent(usedModel)}:generateContent?key=${encodeURIComponent(apiKey)}`,
        {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        },
    );

    if (!response.ok) {
        // Gemini carries the key in the URL, so error bodies can echo it —
        // providerError redacts before this string escapes anywhere.
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
            model: usedModel,
        };
    }
    return { calls, usage: data.usageMetadata, model: usedModel };
}

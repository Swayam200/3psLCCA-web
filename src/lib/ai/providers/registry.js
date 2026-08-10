/**
 * Provider registry — the open-source contribution surface.
 *
 * A provider is a module with:
 *   generate(prompt, { apiKey, model, system, tools }) → Promise<{ calls, usage?, model? }>
 *   DEFAULT_MODEL (string, model providers only)
 * where calls is [{ name, args }] drawn from the declarations in
 * tools/schema.js. Errors must be thrown with user-safe, key-free messages
 * (use redact.js helpers).
 *
 * To add a provider: create the module, then register it here with a label.
 * Everything else — settings UI, routing, fallback — picks it up from this
 * table. See docs/ai-setup.md for the full contract.
 */

import * as gemini from './gemini.js';
import * as claude from './claude.js';
import * as proxy from './proxy.js';
import * as rules from './rules.js';

const MODEL_PROVIDERS = new Map([
    ['gemini', { label: 'Google Gemini', module: gemini }],
    ['claude', { label: 'Anthropic Claude', module: claude }],
]);

export const registerProvider = (id, { label, module }) => {
    if (!id || !module?.generate) throw new Error('A provider needs an id and a generate().');
    MODEL_PROVIDERS.set(id, { label: label || id, module });
};

export const providerIds = () => [...MODEL_PROVIDERS.keys()];

export const providerMeta = () => providerIds().map((id) => ({
    id,
    label: MODEL_PROVIDERS.get(id).label,
    defaultModel: MODEL_PROVIDERS.get(id).module.DEFAULT_MODEL || null,
}));

export const getProvider = (id) => MODEL_PROVIDERS.get(id) || MODEL_PROVIDERS.get('gemini');

export { proxy, rules };

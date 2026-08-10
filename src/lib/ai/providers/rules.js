/**
 * Rules provider — Tier 0 of the local cascade. Offline, free, deterministic.
 *
 * Maps a sentence to an intent with regex patterns, then answers through the
 * shared intent catalogue (tools/intents.js) — the same answer functions the
 * encoder and FunctionGemma tiers use, so every local tier speaks with one
 * voice and no figures are ever computed twice.
 *
 * Confidence contract (shared by all providers):
 *   a regex hit is deterministic → confidence 1.0
 *   no pattern matched          → unparsed: true, confidence 0
 * The router's cascade mode uses these to decide whether to fall through to
 * the next (heavier) tier.
 */

import { answerIntent } from '../tools/intents.js';
import { lexicalSearch, formatMatches } from '../tools/projectIndex.js';

// Ordered: first match wins. Stems, not whole words — "warnings", "errors",
// "validation", "summarize" must all match.
const PATTERNS = [
    // Edit attempts FIRST: "set the discount rate", "add a material" must hit
    // the refusal before the input-data intents could claim their nouns.
    ['edit_refusal', /\b(set|change|update|increase|decrease|add|delete|remove|edit|modify)\b/],
    ['validation', /\b(valid|error|warning|issue|problem|wrong|missing)/],
    ['materials', /\b(materials|made of|inventory)\b/],
    ['engine', /\b(engine|calculated when|when was|version|provenance|browser or backend)\b/],
    ['driver', /\b(biggest|largest|highest|main|top|most expensive|costliest|driver|drives)\b/],
    ['stages', /\bstage\b/],
    ['pillar_environmental', /\b(carbon|emission|environment|planet)\b/],
    ['pillar_social', /\b(social|road user|people)\b/],
    ['pillar_economic', /\b(economic|profit)\b/],
    ['pillars', /\b(pillar|3ps)\b/],
    ['total', /\b(total|overall|lifetime|life[- ]?cycle|npv|lcc\b|cost of the (bridge|project))\b/],
    ['summary', /\b(summar|overview|describ|about this project|tell me about)/],
];

const answer = (intent, context, question) => ({
    calls: [{ name: 'answer', args: { text: answerIntent(intent, context, question) } }],
    intent,
    confidence: 1,
});

export async function generate(prompt, { context } = {}) {
    const text = String(prompt || '').trim().toLowerCase();

    for (const [intent, pattern] of PATTERNS) {
        if (pattern.test(text)) return answer(intent, context || {}, prompt);
    }

    // No aggregate intent matched — search the project index directly. This
    // is generic, schema-driven data access: any field the walker indexed
    // ("span", "discount rate", "HCV", a material row name) is answerable
    // here with zero per-question code. Exact token matches only; paraphrase
    // and synonymy belong to the encoder tier above this one.
    const matches = lexicalSearch(prompt, context?.index || []);
    if (matches.length) {
        return {
            calls: [{ name: 'answer', args: { text: formatMatches(matches) } }],
            intent: 'data_lookup',
            confidence: 1,
        };
    }

    return {
        unparsed: true,
        confidence: 0,
        calls: [{
            name: 'answer',
            args: {
                text: 'The offline rules engine could not parse that question. Try one of the '
                    + 'suggested questions, or enable a heavier tier (local models or a provider) '
                    + 'in Settings → AI Assistant to handle free-form phrasing.',
            },
        }],
    };
}

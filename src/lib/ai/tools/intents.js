/**
 * The intent catalogue — the single source of truth shared by every LOCAL
 * inference tier.
 *
 * Each intent bundles:
 *   - answer(context): the deterministic, engine-grounded answer function
 *   - examples[]:      canonical phrasings of that intent
 *
 * The tiers differ only in HOW they map a user's sentence to an intent key:
 *   - providers/rules.js         regex patterns          (Tier 0, exact)
 *   - providers/localEncoder.js  embedding similarity    (Tier 1, paraphrase)
 *   - providers/functionGemma.js generative tool call    (Tier 3, free-form)
 *
 * The examples double as the encoder's matching library, so adding a phrasing
 * here improves BOTH the docs and the matcher — one list, no drift. Answers
 * quote only figures from the context object (tools/context.js); no tier is
 * ever asked to compute a number.
 */

import { formatAmount } from './context.js';
import { materialsOverview } from './projectIndex.js';

const PILLAR_LABELS = {
    economic: 'economic (profit)',
    environmental: 'environmental (planet)',
    social: 'social (people)',
};

const noResults = () =>
    'No calculation has been run for this project yet — open the Results page and '
    + 'click Proceed to run the LCCA engine, then ask again.';

const fmtFor = (context) => (value) => formatAmount(value, context.project?.currency || 'INR');

// NOTE: there is deliberately no per-topic lookup logic here. Questions about
// specific data fields ("what cement was used", "what is the span", "which
// discount rate") are answered by searching the schema-driven project index —
// see tools/projectIndex.js and the data-lookup fallback in the providers.
// Intents exist only for aggregates and canned views.

export const INTENTS = {
    total: {
        examples: [
            'What is the total life-cycle cost?',
            'What is the overall NPV of this project?',
            'How much does the bridge cost over its lifetime?',
            'What is the lifetime cost?',
            'Total LCC please',
        ],
        answer(context) {
            const results = context.results;
            if (!results) return noResults();
            const fmt = fmtFor(context);
            const period = context.bridge?.analysis_period_years;
            return `The lifetime life-cycle cost is ${fmt(results.lifetime_total)}`
                + `${period ? ` over a ${period}-year analysis period` : ''}.`;
        },
    },

    driver: {
        examples: [
            'What is the biggest cost driver?',
            'Which item is the most expensive?',
            'Which stage costs the most?',
            'What dominates the total cost?',
            'Where does most of the money go?',
        ],
        answer(context) {
            const results = context.results;
            if (!results) return noResults();
            const fmt = fmtFor(context);
            const top = results.top_cost_items?.[0];
            if (!top) return 'The result set contains no non-zero cost items.';
            const share = results.lifetime_total
                ? ` — ${((top.value / results.lifetime_total) * 100).toFixed(1)}% of the lifetime total`
                : '';
            const stages = results.stagewise || {};
            const stageEntries = [
                ['the initial stage', stages.initial],
                ['the use & reconstruction stages', stages.use_and_reconstruction],
                ['the end-of-life stage', stages.end_of_life],
            ].filter(([, value]) => Number.isFinite(value));
            stageEntries.sort((a, b) => b[1] - a[1]);
            const topStage = stageEntries[0];
            return `The largest single cost item is "${top.label}" (${top.stage}, `
                + `${PILLAR_LABELS[top.pillar] || top.pillar}) at ${fmt(top.value)}${share}. `
                + `By stage, ${topStage[0]} costs the most at ${fmt(topStage[1])}.`;
        },
    },

    stages: {
        examples: [
            'How do costs split by stage?',
            'Show me the stage breakdown',
            'How much is the initial stage versus end of life?',
            'What does each life-cycle stage cost?',
        ],
        answer(context) {
            const results = context.results;
            if (!results) return noResults();
            const fmt = fmtFor(context);
            const stages = results.stagewise || {};
            return `By life-cycle stage: initial ${fmt(stages.initial)}, use & reconstruction `
                + `${fmt(stages.use_and_reconstruction)}, end of life ${fmt(stages.end_of_life)}.`;
        },
    },

    pillars: {
        examples: [
            'Break down the costs by pillar',
            'Show the 3ps split',
            'How do the three pillars compare?',
            'What are the pillar totals?',
        ],
        answer(context) {
            const results = context.results;
            if (!results) return noResults();
            const fmt = fmtFor(context);
            const pillars = results.pillar_totals || {};
            return `Pillar totals: economic ${fmt(pillars.economic)}, environmental `
                + `${fmt(pillars.environmental)}, social ${fmt(pillars.social)}.`;
        },
    },

    pillar_environmental: {
        examples: [
            'How large is the environmental pillar?',
            'How much do carbon emissions cost?',
            'What is the planet cost of this bridge?',
            'What is the carbon footprint cost?',
        ],
        answer(context) {
            const results = context.results;
            if (!results) return noResults();
            const fmt = fmtFor(context);
            const pillars = results.pillar_totals || {};
            const share = results.lifetime_total
                ? ` (${((pillars.environmental / results.lifetime_total) * 100).toFixed(1)}% of the lifetime total)`
                : '';
            return `Environmental (planet) costs total ${fmt(pillars.environmental)}${share}.`;
        },
    },

    pillar_social: {
        examples: [
            'What is the social pillar total?',
            'How much is the road user cost overall?',
            'What do people-related costs come to?',
        ],
        answer(context) {
            const results = context.results;
            if (!results) return noResults();
            return `Social (people) costs total ${fmtFor(context)(results.pillar_totals?.social)}.`;
        },
    },

    pillar_economic: {
        examples: [
            'What is the economic pillar total?',
            'How much is the profit pillar?',
            'What are the direct monetary costs?',
        ],
        answer(context) {
            const results = context.results;
            if (!results) return noResults();
            return `Economic (profit) costs total ${fmtFor(context)(results.pillar_totals?.economic)}.`;
        },
    },

    validation: {
        examples: [
            'Were there any validation warnings?',
            'Are there errors in my input data?',
            'Any issues with the project inputs?',
            'Did the calculation report problems?',
        ],
        answer(context) {
            const errors = context.validation?.errors || [];
            const warnings = context.validation?.warnings || [];
            if (!errors.length && !warnings.length) {
                return 'The last calculation reported no validation errors or warnings.';
            }
            const parts = [];
            if (errors.length) parts.push(`${errors.length} error(s): ${errors.join('; ')}`);
            if (warnings.length) parts.push(`${warnings.length} warning(s): ${warnings.join('; ')}`);
            return parts.join(' — ');
        },
    },

    engine: {
        examples: [
            'Which engine calculated this and when?',
            'What version produced these results?',
            'Was this computed in the browser or on the backend?',
            'When were the results last calculated?',
        ],
        answer(context) {
            const results = context.results;
            if (!results) return noResults();
            const engine = results.engine || {};
            const source = engine.source === 'browser'
                ? 'the in-browser engine'
                : engine.source === 'backend' ? 'the FastAPI backend' : 'an unknown engine';
            const when = results.calculated_at
                ? new Date(results.calculated_at).toLocaleString()
                : 'an unknown time';
            const version = engine.core_version ? ` (3psLCCA-core ${engine.core_version})` : '';
            return `The results were calculated by ${source}${version} at ${when}.`;
        },
    },

    summary: {
        examples: [
            'Summarize this project',
            'Give me an overview of the project',
            'Tell me about this bridge',
            'Describe the project in brief',
        ],
        answer(context) {
            const bridge = context.bridge || {};
            const intro = `${context.project?.name || 'This project'}${bridge.name ? ` — ${bridge.name}` : ''}`
                + `${bridge.type ? `, a ${bridge.type}` : ''}`
                + `${bridge.span_m ? ` of ${bridge.span_m} m span` : ''}`
                + `${bridge.lanes ? ` with ${bridge.lanes} lanes` : ''}.`;
            const results = context.results;
            if (!results) return `${intro} ${noResults()}`;
            const fmt = fmtFor(context);
            const pillars = results.pillar_totals || {};
            return `${intro} Lifetime cost ${fmt(results.lifetime_total)} over `
                + `${bridge.analysis_period_years || '—'} years: economic ${fmt(pillars.economic)}, `
                + `environmental ${fmt(pillars.environmental)}, social ${fmt(pillars.social)}. `
                + `Largest item: ${results.top_cost_items?.[0]?.label || '—'}.`;
        },
    },

    materials: {
        examples: [
            'What materials is the bridge made of?',
            'List the construction materials',
            'Give me the material inventory',
        ],
        answer(context) {
            return materialsOverview(context.index || []);
        },
    },

    edit_refusal: {
        // These examples matter for the encoder: edit attempts must land HERE
        // (a clear refusal) rather than fuzzily matching some read intent.
        examples: [
            'Set the discount rate to 8',
            'Change the span to 300 metres',
            'Increase all foundation rates by 8%',
            'Add a new material to the substructure',
            'Delete the drainage line item',
            'Update the analysis period to 75 years',
        ],
        answer() {
            return 'This assistant is read-only for now — it can explain results but not change data. '
                + 'Use the data-entry pages on the left to edit the project.';
        },
    },
};

/** Flat [ { intent, text } ] list — the encoder's matching library. */
export const intentExamples = () =>
    Object.entries(INTENTS).flatMap(([intent, def]) =>
        def.examples.map((text) => ({ intent, text })));

/**
 * Answer a resolved intent. `question` is the user's original sentence —
 * lookup-style intents (materials) use it to pick rows; the rest ignore it.
 */
export function answerIntent(intent, context, question = '') {
    const def = INTENTS[intent];
    if (!def) return 'I could not map that question to something I know how to answer.';
    return def.answer(context || {}, question);
}

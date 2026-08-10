/**
 * Mock provider — a deterministic, offline stand-in for a real LLM.
 *
 * It produces exactly the same output shape a real provider does: a list of
 * { name, args } tool calls drawn from lib/ai/tools.js. That is the point.
 * Because the contract is the calls and not the prose, the rest of the
 * application cannot tell which provider produced them, and the demo runs on
 * a laptop with no API key and no network.
 *
 * It is a regex cascade, not a language model: it understands the phrasings
 * listed in the UI's example chips and little else. When it cannot parse a
 * request it says so plainly rather than guessing — which is also the correct
 * behaviour for the real thing.
 */

import { getProject } from '../store.js';
import { calculate } from '../lcca.js';

const SECTION_ALIASES = [
    [/\b(foundation|pile|footing)\b/i, 'foundation_data'],
    [/\b(sub[- ]?structure|pier|abutment|bearing)\b/i, 'substructure_data'],
    [/\b(super[- ]?structure|girder|deck|slab)\b/i, 'superstructure_data'],
    [/\b(misc(ellaneous)?|railing|barrier|drainage|expansion joint)\b/i, 'miscellaneous_data'],
];

const PARAM_ALIASES = [
    [/\b(discount rate|discounting rate)\b/i, 'discount_rate'],
    [/\b(inflation( rate)?)\b/i, 'inflation_rate'],
    [/\b(analysis period|study period|service life|horizon)\b/i, 'analysis_period'],
    [/\b(maintenance interval|maintenance cycle|maintenance every)\b/i, 'maintenance_interval'],
    [/\b(maintenance (cost|percent|percentage|pct))\b/i, 'maintenance_pct'],
    [/\b(demolition|end[- ]of[- ]life|eol)\b/i, 'demolition_pct'],
    [/\b(social cost of carbon|carbon price|carbon cost)\b/i, 'social_cost_of_carbon'],
    [/\b(road user cost|user cost)\b/i, 'annual_road_user_cost'],
];

const detectSection = (text) => {
    for (const [pattern, key] of SECTION_ALIASES) if (pattern.test(text)) return key;
    return null;
};

const detectParam = (text) => {
    for (const [pattern, key] of PARAM_ALIASES) if (pattern.test(text)) return key;
    return null;
};

const numberFrom = (raw) => Number(String(raw).replace(/,/g, ''));

/**
 * Trim a captured row reference at the first clause boundary. Without this the
 * greedy tail of "delete the X and set the discount rate to 8" is captured as
 * the row name, and the resulting error blames the wrong thing. A real model
 * splits clauses on its own; the regex cascade has to be told.
 */
const clause = (raw) => String(raw)
    .split(/\s+(?:and|then|also|,)\s+/i)[0]
    .replace(/\s+(row|item|line item|material|entry)\s*$/i, '')
    .replace(/^(the|a|an)\s+/i, '')
    .trim();

const fmtINR = (value) => `₹${Math.round(value).toLocaleString('en-IN')}`;

/** Read-only questions get answered from the live computed result. */
function answerQuestion(text) {
    const project = getProject();
    const result = calculate(project);
    const t = text.toLowerCase();

    if (/\b(carbon|co2|emission)\b/.test(t)) {
        return `Embodied carbon is ${result.totals.embodied_carbon_t.toFixed(1)} tCO₂e, monetised at `
            + `${fmtINR(result.totals.carbon_cost)} using a social cost of carbon of `
            + `₹${result.assumptions.social_cost_of_carbon}/tCO₂e.`;
    }
    if (/\b(maintenance)\b/.test(t)) {
        return `Maintenance is ${result.maintenance_events.length} events every `
            + `${result.assumptions.maintenance_interval} years at ${result.assumptions.maintenance_pct}% of `
            + `construction cost, worth ${fmtINR(result.totals.maintenance_pv)} in present value.`;
    }
    if (/\b(expensive|costliest|largest|biggest|driver)\b/.test(t)) {
        const top = [...result.sections].sort((a, b) => b.cost - a.cost)[0];
        return `The largest construction section is ${top.label} at ${fmtINR(top.cost)} `
            + `(${((top.cost / result.totals.construction_cost) * 100).toFixed(1)}% of construction cost).`;
    }
    if (/\b(construction cost)\b/.test(t)) {
        return `Initial construction cost is ${fmtINR(result.totals.construction_cost)} across `
            + `${result.sections.reduce((s, x) => s + x.rowCount, 0)} active line items.`;
    }
    return `Total life-cycle NPV is ${fmtINR(result.totals.total_npv)} over `
        + `${result.assumptions.analysis_period} years at a ${result.assumptions.discount_rate}% discount rate — `
        + `profit ${fmtINR(result.pillars.profit)}, planet ${fmtINR(result.pillars.planet)}, `
        + `people ${fmtINR(result.pillars.people)}.`;
}

export async function generate(prompt) {
    const text = String(prompt || '').trim();
    const calls = [];

    // --- read-only question ------------------------------------------------
    if (/^(what|how much|how many|which|show|tell me|is there|why)\b/i.test(text)
        && !/\b(add|set|change|increase|decrease|delete|remove|update)\b/i.test(text)) {
        return { calls: [{ name: 'answer', args: { text: answerQuestion(text) } }] };
    }

    // --- parameter change: "set the discount rate to 8%" -------------------
    const paramMatch = text.match(/\b(?:set|change|make|use|update)\b[^.]*?\bto\s+([\d,.]+)\s*(%|percent|years?|yrs?)?/i);
    if (paramMatch) {
        const param = detectParam(text);
        if (param) {
            calls.push({ name: 'set_parameter', args: { name: param, value: numberFrom(paramMatch[1]) } });
        }
    }

    // --- bulk scale: "increase all foundation rates by 8%" -----------------
    const scaleMatch = text.match(/\b(increase|raise|bump|decrease|reduce|cut|lower)\b[^.]*?\bby\s+([\d.]+)\s*(%|percent)/i);
    if (scaleMatch) {
        const direction = /^(decrease|reduce|cut|lower)$/i.test(scaleMatch[1]) ? -1 : 1;
        const pct = Number(scaleMatch[2]);
        calls.push({
            name: 'scale_rates',
            args: {
                section: detectSection(text) || undefined,
                factor: Number((1 + (direction * pct) / 100).toFixed(4)),
                field: /\bquantit(y|ies)|\bqty\b/i.test(text) ? 'qty' : 'rate',
            },
        });
    }

    // --- create: "add 250 m3 of X to substructure at 9500" -----------------
    const addMatch = text.match(
        /\badd\b\s+([\d,.]+)\s*([a-zA-Zm²³%/]+)?\s*(?:of\s+)?(.+?)(?:\s+(?:to|into|under)\s+(?:the\s+)?[\w\s]*?)?(?:\s+(?:at|@|for)\s+(?:₹|rs\.?\s*)?([\d,.]+))?\s*(?:per\s+[\w²³]+)?\s*$/i,
    );
    if (addMatch && !scaleMatch) {
        const [, qty, unitRaw, nameRaw, rate] = addMatch;
        const section = detectSection(text) || 'miscellaneous_data';
        // Strip any trailing section words the name regex swept up.
        const workName = nameRaw
            .replace(/\s+(to|into|under)\s+(the\s+)?(foundation|sub[- ]?structure|super[- ]?structure|misc\w*)\s*(section)?\s*$/i, '')
            .replace(/\s+section\s*$/i, '')
            .trim();
        const carbon = text.match(/\bcarbon\s*(?:factor)?\s*(?:of\s*)?([\d.]+)/i);
        calls.push({
            name: 'create_material',
            args: {
                section,
                workName,
                qty: numberFrom(qty),
                unit: unitRaw && !/^(of|the|a|an)$/i.test(unitRaw) ? unitRaw.replace('m3', 'm³').replace('m2', 'm²') : 'nos',
                rate: rate ? numberFrom(rate) : 0,
                carbonFactor: carbon ? Number(carbon[1]) : 0,
                source: 'AI-assisted entry',
            },
        });
    }

    // --- delete: "delete the MS railing" -----------------------------------
    const delMatch = text.match(/\b(delete|remove|drop|trash)\s+(?:the\s+)?(.+?)\s*$/i);
    if (delMatch && !addMatch) {
        calls.push({
            name: 'delete_material',
            args: {
                match: clause(delMatch[2]),
                section: detectSection(text) || undefined,
            },
        });
    }

    // --- field update: "change the MS railing quantity to 1600" ------------
    const fieldMatch = text.match(
        /\b(?:change|set|update|make)\s+(?:the\s+)?(.+?)\s+(quantity|qty|rate|unit|carbon factor)\s+(?:to|=)\s+(?:₹|rs\.?\s*)?([\d,.]+)/i,
    );
    if (fieldMatch && !calls.some((c) => c.name === 'set_parameter')) {
        const fieldKey = {
            quantity: 'qty', qty: 'qty', rate: 'rate', unit: 'unit', 'carbon factor': 'carbonFactor',
        }[fieldMatch[2].toLowerCase()];
        calls.push({
            name: 'update_material',
            args: {
                match: clause(fieldMatch[1]),
                fields: { [fieldKey]: numberFrom(fieldMatch[3]) },
            },
        });
    }

    if (!calls.length) {
        // `unparsed` is the signal the router uses in "rules first, AI fallback"
        // mode. It is the difference between "the rules answered you" and "the
        // rules had nothing" — without it, a fallback chain cannot know when to
        // escalate, and would either never fall through or always would.
        return {
            unparsed: true,
            calls: [{
                name: 'answer',
                args: {
                    text: 'The rule engine could not parse that. It understands a fixed set of phrasings — '
                        + 'try one of the example chips, or switch to a model in Settings (⚙) to route the '
                        + 'same request to Gemini or Claude.',
                },
            }],
        };
    }
    return { calls };
}

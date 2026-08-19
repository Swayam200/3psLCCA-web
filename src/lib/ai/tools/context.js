/**
 * Builds the compact, bounded context object every provider receives.
 *
 * This is the only bridge between the app's data and the AI layer, and the
 * import direction matters: this file imports FROM the app (summary helpers,
 * breakdown labels); nothing in the app imports from here.
 *
 * Everything numeric comes from the last engine run persisted in
 * projectData.outputs_data — the model describes figures the engine computed,
 * it never derives them. If no calculation has been run, the context says so
 * and the providers tell the user to run one.
 */

import { computeAllSummaries } from '../../../gui/components/outputs/lifecycleSummary.js';
import { BREAKDOWN_STAGES } from '../../../gui/components/outputs/breakdownStages.js';
import { buildProjectIndex } from './projectIndex.js';

const num = (value) => {
    if (value === null || value === undefined || value === '') return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
};

const round = (value) => (value === null ? null : Math.round(value));

/** Format an amount in the project currency for display in answers. */
export const formatAmount = (value, currency = 'INR') => {
    const parsed = num(value);
    if (parsed === null) return '—';
    const locale = currency === 'INR' ? 'en-IN' : 'en-US';
    try {
        return new Intl.NumberFormat(locale, {
            style: 'currency',
            currency,
            maximumFractionDigits: 0,
        }).format(parsed);
    } catch {
        return `${currency} ${Math.round(parsed).toLocaleString(locale)}`;
    }
};

/**
 * Flatten the raw results dict into labelled line items using the same
 * key→label mapping the results tables render from, so the assistant and the
 * screen always use identical vocabulary.
 */
const lineItems = (results) => {
    const items = [];
    for (const stage of BREAKDOWN_STAGES) {
        const stageData = results?.[stage.resultKey];
        if (!stageData) continue;
        for (const row of stage.rows) {
            const value = num(stageData?.[row.pillar]?.[row.key]);
            if (value === null || value === 0) continue;
            items.push({
                label: row.label,
                stage: stage.label,
                pillar: row.pillar,
                // Scrap value is a recovery — represent it as negative so sums
                // and "biggest driver" sorting treat it correctly.
                value: round(row.key === 'total_scrap_value' ? -Math.abs(value) : value),
            });
        }
    }
    return items.sort((a, b) => b.value - a.value);
};

/**
 * Build the context for one prompt. Bounded by construction: aggregate
 * results for the curated intents, plus the schema-driven project index
 * (tools/projectIndex.js) as the generic path to every input and result
 * field. Never the raw project tree.
 */
export function buildAiContext(projectData) {
    const project = projectData || {};
    const bridge = project.bridge_data || {};
    const outputs = project.outputs_data || {};
    const results = outputs.results || null;

    const context = {
        project: {
            name: project.name || project.general_info?.project_name || 'Untitled project',
            country: project.country || project.general_info?.project_country || null,
            currency: project.currency || project.general_info?.project_currency || 'INR',
            unitSystem: project.unitSystem || project.general_info?.unit_system || null,
        },
        bridge: {
            name: bridge.bridge_name || null,
            type: bridge.bridge_type || null,
            span_m: num(bridge.span),
            lanes: num(bridge.num_lanes),
            design_life_years: num(bridge.design_life),
            analysis_period_years: num(outputs.analysis_period_years ?? bridge.analysis_period),
        },
        results: null,
        // Every meaningful field of the project, searchable. The generative
        // tiers read this directly; the local tiers search it (lexically or
        // semantically). See tools/projectIndex.js.
        index: buildProjectIndex(project),
        validation: {
            errors: (outputs.validation?.errors || []).slice(0, 12),
            warnings: (outputs.validation?.warnings || []).slice(0, 12),
        },
    };

    if (results) {
        const summaries = computeAllSummaries(results);
        const items = lineItems(results);
        const lifetime = summaries.pillar_totals.eco
            + summaries.pillar_totals.env
            + summaries.pillar_totals.social;

        context.results = {
            calculated_at: outputs.calculated_at || null,
            engine: {
                source: outputs.source || outputs.engine?.source || null,
                core_version: outputs.engine?.coreVersion || null,
            },
            lifetime_total: round(lifetime),
            pillar_totals: {
                economic: round(summaries.pillar_totals.eco),
                environmental: round(summaries.pillar_totals.env),
                social: round(summaries.pillar_totals.social),
            },
            stagewise: {
                initial: round(summaries.stagewise.initial),
                use: round(summaries.stagewise.use),
                end_of_life: round(summaries.stagewise.end_of_life),
            },
            top_cost_items: items.slice(0, 10),
            credits: items.filter((item) => item.value < 0),
        };
    }

    return context;
}

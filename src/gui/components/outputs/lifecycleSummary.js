/**
 * lifecycleSummary.js
 * Computes summary views from LCCA result dict.
 * Ported VERBATIM from desktop
 * gui/components/outputs/helper_functions/lifecycle_summary.py.
 *
 * NOTE (desktop semantics): "reconstruction" and "end_of_life" are merged
 * into a single "end_of_life" group in all summary outputs; "use_stage" is
 * reported alone.
 */

/**
 * Sum all numeric values in a dict, treating scrap value as a credit.
 */
function sumDict(d) {
    if (!d || typeof d !== 'object') return 0;
    let total = 0;
    for (const [k, v] of Object.entries(d)) {
        if (k === 'total_scrap_value') {
            total -= v; // scrap value is a recovery/credit
        } else {
            total += v;
        }
    }
    return total;
}

/**
 * Given one stage's data dict, return its three pillar sub-totals.
 */
function stageTotals(stageData) {
    return {
        eco: sumDict(stageData?.economic || {}),
        env: sumDict(stageData?.environmental || {}),
        social: sumDict(stageData?.social || {}),
    };
}

/**
 * Compute summary views from LCCA result dict.
 *
 * @param {Object} data - The raw LCCA results dict
 * @returns {Object} { stagewise, pillar_wise, pillar_totals, environmental_split }
 */
export function computeAllSummaries(data) {
    // Step 1: Compute per-stage pillar totals
    const stages = {};
    for (const k of ['initial_stage', 'use_stage', 'reconstruction', 'end_of_life']) {
        stages[k] = stageTotals(data?.[k] || {});
    }

    // Helper: sum all three pillars for a single raw stage key
    const totalOf = (stageKey) => {
        const s = stages[stageKey] || {};
        return (s.eco || 0) + (s.env || 0) + (s.social || 0);
    };

    // 1) Stagewise (Merged)
    const stagewise = {
        initial: totalOf('initial_stage'),
        use: totalOf('use_stage'),
        end_of_life: totalOf('reconstruction') + totalOf('end_of_life'),
    };

    // 2) Pillar-wise (Merged)
    const pillar_wise = {
        initial: stages.initial_stage,
        use: stages.use_stage,
        end_of_life: {
            eco: stages.reconstruction.eco + stages.end_of_life.eco,
            env: stages.reconstruction.env + stages.end_of_life.env,
            social: stages.reconstruction.social + stages.end_of_life.social,
        },
    };

    // 3) Pillar totals (lifetime)
    const pillar_totals = { eco: 0, env: 0, social: 0 };
    for (const s of Object.values(stages)) {
        pillar_totals.eco += s.eco || 0;
        pillar_totals.env += s.env || 0;
        pillar_totals.social += s.social || 0;
    }

    // 4) Environmental split
    const environmental_split = {
        initial: stages.initial_stage.env,
        use: stages.use_stage.env,
        end_of_life: stages.reconstruction.env + stages.end_of_life.env,
    };

    return { stagewise, pillar_wise, pillar_totals, environmental_split };
}

/**
 * The tool contract — single source of truth for every provider.
 *
 * Phase 1 is deliberately read-only: the model's entire vocabulary is one
 * tool, `answer`. It cannot request an edit because no edit operation exists
 * to request. Phase 2 grows this registry (see docs/ai-integration-plan.md);
 * nothing else about the pipeline changes when it does.
 *
 * These declarations are plain data. The same objects are rendered into
 * Gemini's functionDeclarations, Claude's tools[], and the proxy contract.
 */

export const TOOLS = [
    {
        name: 'answer',
        description:
            'Answer the user\'s question about the current project in one to three '
            + 'sentences, using only the figures provided in the project context. '
            + 'This is the only available action.',
        parameters: {
            type: 'object',
            properties: {
                text: {
                    type: 'string',
                    description: 'The answer. Quote figures exactly as given in the context.',
                },
            },
            required: ['text'],
        },
    },
];

/**
 * System prompt for model providers. The aggregate context is embedded as
 * JSON; the project index (every input and result field, one line each) is
 * embedded as plain lines to keep tokens down. The model describes values it
 * was handed — it never derives them.
 */
export const systemPrompt = (context) => {
    const { index, ...aggregates } = context || {};
    const dataLines = (index || []).map((entry) => entry.text).join('\n');
    return `You are the read-only assistant inside 3psLCCA, a life-cycle cost analysis (LCCA) tool for bridge projects. The user is viewing the project below.

PROJECT CONTEXT (all figures computed by the LCCA engine; currency amounts are in ${context?.project?.currency || 'the project currency'}):
${JSON.stringify(aggregates, null, 1)}

PROJECT DATA (every entered input and computed line item, one per line):
${dataLines || '(no data entered yet)'}

RULES
1. You are read-only. You cannot change any value. If asked to change something, use the "answer" tool to say that editing via the assistant is not available yet and point to the relevant data-entry page.
2. Answer ONLY from the context above. Never estimate, extrapolate, or invent a figure. If the context lacks the answer (e.g. no calculation has been run), say so and tell the user to run the calculation from the Results page.
3. Always respond through the "answer" tool. Keep answers to one to three sentences.
4. "eco"/"economic" is the profit pillar, "env"/"environmental" the planet pillar, "social" the people pillar of the 3ps framework.`;
};

/**
 * Execute a model-produced call list. Phase 1: `answer` is the only executor.
 * The {applied, rejected} shape is shared with Phase 2, where executors start
 * mutating project data through ProjectDataContext.
 */
export function executeCalls(calls) {
    const applied = [];
    const rejected = [];

    for (const call of calls || []) {
        if (call.name === 'answer') {
            const text = String(call.args?.text || '').trim();
            if (text) {
                applied.push({ name: 'answer', summary: text, readOnly: true });
            } else {
                rejected.push({ name: 'answer', error: 'Empty answer.' });
            }
        } else {
            rejected.push({
                name: call.name,
                error: `Unknown tool "${call.name}" — this assistant is read-only.`,
            });
        }
    }
    return { applied, rejected };
}

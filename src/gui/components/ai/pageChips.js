/**
 * Suggestion chips, keyed by the page the user is looking at. Every chip is a
 * question the current pipeline answers well (they come from the smoke-test
 * battery in docs/ai-smoke-test.md), so suggestions never showcase failures.
 * Pure module — no JSX — covered by node:test.
 */

export const RESULTS_CHIPS = [
    'What is the total life-cycle cost?',
    'Which stage costs the most?',
    'What is the biggest cost driver?',
    'How large is the environmental pillar?',
    'What materials is the bridge made of?',
    'Summarize this project',
    'Were there any validation warnings?',
];

export const GENERAL_CHIPS = [
    'Summarize this project',
    'What is the total life-cycle cost?',
    'What materials is the bridge made of?',
    'What discount rate did we use?',
];

const PAGE_CHIPS = [
    {
        match: ['bridge'],
        chips: [
            'What is the span of the bridge?',
            'How many lanes does it have?',
            'How wide is the carriageway?',
            'Summarize this project',
        ],
    },
    {
        match: ['financial'],
        chips: [
            'What discount rate did we use?',
            'What is the inflation rate?',
            'What interest do we pay on the loan?',
            'Summarize this project',
        ],
    },
    {
        match: ['traffic'],
        chips: [
            'How many HCV vehicles per day?',
            'What is the traffic growth?',
            'Summarize this project',
        ],
    },
    {
        match: ['construction', 'foundation', 'sub structure', 'super structure', 'miscellaneous'],
        chips: [
            'What materials is the bridge made of?',
            'What was the type of cement used?',
            'How much steel reinforcement is there?',
            'Summarize this project',
        ],
    },
    {
        match: ['demolition'],
        chips: [
            'What is the demolition cost percentage?',
            'What is the total life-cycle cost?',
            'Summarize this project',
        ],
    },
    {
        match: ['outputs', 'results'],
        chips: RESULTS_CHIPS,
    },
];

/** Chips for the active sidebar node; falls back to the general set. */
export const chipsForPage = (activeNode) => {
    const node = String(activeNode || '').toLowerCase();
    // 'Traffic Rerouting Emissions' must hit the carbon default, not traffic.
    if (node.includes('emission')) return GENERAL_CHIPS;
    const page = PAGE_CHIPS.find(({ match }) => match.some((m) => node.includes(m)));
    return page ? page.chips : GENERAL_CHIPS;
};

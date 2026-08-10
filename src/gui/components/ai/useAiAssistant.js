/**
 * The assistant's behavior, extracted from the old Results-page panel so the
 * floating sheet (and any future frame) share one implementation: build the
 * context from live project data, hand the prompt to the router, keep the
 * outcome — including the route, because a silent fallback is worse than no
 * fallback.
 */
import { useMemo, useState } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext.jsx';
import { runPrompt, providerStatus, buildAiContext, loadPrefs } from '../../../lib/ai/index.js';

export default function useAiAssistant() {
    const { projectData } = useProjectData();
    const [prompt, setPrompt] = useState('');
    const [busy, setBusy] = useState(false);
    const [outcome, setOutcome] = useState(null);
    // Cheap localStorage read, but not per-keystroke: refreshed on answers and
    // whenever the frame asks (sheet opened, settings modal closed).
    const [statusTick, setStatusTick] = useState(0);
    const status = useMemo(() => providerStatus(), [outcome, statusTick]); // eslint-disable-line react-hooks/exhaustive-deps

    const refreshStatus = () => setStatusTick((tick) => tick + 1);

    const ask = async (text) => {
        const question = String(text ?? prompt).trim();
        if (!question || busy) return;
        setBusy(true);
        try {
            const context = buildAiContext(projectData);
            setOutcome(await runPrompt(question, { context }));
        } finally {
            setBusy(false);
        }
    };

    return {
        enabled: loadPrefs().enabled,
        status,
        refreshStatus,
        prompt,
        setPrompt,
        busy,
        outcome,
        ask,
    };
}

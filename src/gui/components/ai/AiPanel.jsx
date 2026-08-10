/**
 * Read-only AI assistant panel for the Results page.
 *
 * Loaded ONLY via dynamic import gated on VITE_AI_ENABLED (see Outputs.jsx) —
 * this file and everything it imports stays out of flag-off bundles.
 *
 * The panel is a thin shell: it builds the context from the live project
 * data, hands the prompt to the router, and renders the outcome — including
 * the route (which engine actually answered), because a silent fallback is
 * worse than no fallback.
 */
import React, { useMemo, useState } from 'react';
import { Button, Form, Spinner } from 'react-bootstrap';
import { useProjectData } from '../../../contexts/ProjectDataContext.jsx';
import { runPrompt, providerStatus, buildAiContext, loadPrefs } from '../../../lib/ai/index.js';

const EXAMPLES = [
    'What is the total life-cycle cost?',
    'Which stage costs the most?',
    'What is the biggest cost driver?',
    'How large is the environmental pillar?',
    'What materials is the bridge made of?',
    'What discount rate did we use?',
    'Summarize this project',
    'Were there any validation warnings?',
];

const pillStyle = (outcome) => ({
    fontSize: '0.72rem',
    fontFamily: 'var(--bs-font-monospace, monospace)',
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: '999px',
    border: `1px solid ${outcome === 'error' ? 'var(--app-danger, #c2410c)' : 'var(--app-border-mid)'}`,
    borderStyle: (outcome === 'unparsed' || outcome === 'low-confidence') ? 'dashed' : 'solid',
    color: outcome === 'error' ? 'var(--app-danger, #c2410c)' : 'var(--app-text-secondary)',
});

/** "rules 100%" / "encoder: 41% < threshold" / "gemma: failed" */
const pillLabel = (step) => {
    const pct = Number.isFinite(step.confidence) ? ` ${Math.round(step.confidence * 100)}%` : '';
    if (step.outcome === 'ok') return `${step.step}${pct}`;
    if (step.outcome === 'low-confidence') return `${step.step}:${pct} < threshold`;
    if (step.outcome === 'unparsed') return `${step.step}: no match`;
    return `${step.step}: failed`;
};

export default function AiPanel() {
    const { projectData } = useProjectData();
    const [open, setOpen] = useState(true);
    const [prompt, setPrompt] = useState('');
    const [busy, setBusy] = useState(false);
    const [outcome, setOutcome] = useState(null);

    // Recompute cheap status on each render cycle the panel opens with —
    // settings may have changed in the modal since the last question.
    const status = useMemo(() => providerStatus(), [outcome, open]); // eslint-disable-line react-hooks/exhaustive-deps

    if (!loadPrefs().enabled) return null;

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

    return (
        <div
            className="border rounded mb-4"
            style={{ borderColor: 'var(--app-border-mid)', backgroundColor: 'var(--app-bg-card)' }}
            data-testid="ai-panel"
        >
            <button
                type="button"
                onClick={() => setOpen(!open)}
                className="w-100 d-flex align-items-center justify-content-between px-3 py-2 border-0 bg-transparent"
                style={{ color: 'var(--app-text-primary)', cursor: 'pointer' }}
            >
                <span className="fw-bold" style={{ fontSize: '0.95rem' }}>
                    AI Assistant
                    <span
                        className="ms-2 fw-normal"
                        style={{ fontSize: '0.75rem', color: 'var(--app-text-secondary)' }}
                    >
                        read-only · {status.degraded ? 'offline rules (no key)'
                            : status.mode === 'cascade' ? 'local cascade'
                                : status.modeLabel.toLowerCase()}
                    </span>
                </span>
                <span style={{ color: 'var(--app-text-secondary)' }}>{open ? '▾' : '▸'}</span>
            </button>

            {open && (
                <div className="px-3 pb-3">
                    <div className="d-flex flex-wrap gap-1 mb-2">
                        {EXAMPLES.map((example) => (
                            <button
                                key={example}
                                type="button"
                                disabled={busy}
                                onClick={() => { setPrompt(example); ask(example); }}
                                className="btn btn-sm"
                                style={{
                                    fontSize: '0.75rem',
                                    border: '1px dashed var(--app-border-mid)',
                                    color: 'var(--app-text-secondary)',
                                    borderRadius: '999px',
                                    padding: '2px 10px',
                                }}
                            >
                                {example}
                            </button>
                        ))}
                    </div>

                    <div className="d-flex gap-2">
                        <Form.Control
                            as="textarea"
                            rows={1}
                            value={prompt}
                            placeholder="Ask about this project's results…"
                            onChange={(e) => setPrompt(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); }
                            }}
                            style={{
                                backgroundColor: 'var(--app-bg-alt)',
                                color: 'var(--app-text-primary)',
                                borderColor: 'var(--app-border-mid)',
                                fontSize: '0.85rem',
                                resize: 'vertical',
                            }}
                        />
                        <Button
                            onClick={() => ask()}
                            disabled={busy || !prompt.trim()}
                            style={{ minWidth: '72px' }}
                        >
                            {busy ? <Spinner size="sm" animation="border" /> : 'Ask'}
                        </Button>
                    </div>

                    {outcome && (
                        <div className="mt-3" data-testid="ai-outcome">
                            <div className="d-flex align-items-center flex-wrap gap-1 mb-2">
                                {(outcome.route || []).map((step, index) => (
                                    <React.Fragment key={`${step.step}-${index}`}>
                                        {index > 0 && (
                                            <span style={{ color: 'var(--app-text-secondary)', fontSize: '0.72rem' }}>→</span>
                                        )}
                                        <span style={pillStyle(step.outcome)} title={step.error || undefined}>
                                            {pillLabel(step)}
                                        </span>
                                    </React.Fragment>
                                ))}
                                <span
                                    className="ms-2"
                                    style={{ fontSize: '0.72rem', color: 'var(--app-text-secondary)' }}
                                >
                                    {outcome.model || outcome.provider} · {outcome.latencyMs} ms
                                </span>
                            </div>

                            {outcome.status === 'error' ? (
                                <div style={{ color: 'var(--app-danger, #c2410c)', fontSize: '0.85rem' }}>
                                    {outcome.error}
                                </div>
                            ) : (
                                (outcome.applied || []).map((entry, index) => (
                                    <div
                                        key={index}
                                        className="border rounded px-3 py-2 mb-1"
                                        style={{
                                            borderColor: 'var(--app-border-mid)',
                                            backgroundColor: 'var(--app-bg-alt)',
                                            color: 'var(--app-text-primary)',
                                            fontSize: '0.87rem',
                                        }}
                                    >
                                        {entry.summary}
                                    </div>
                                ))
                            )}
                        </div>
                    )}

                    <div className="mt-2" style={{ fontSize: '0.72rem', color: 'var(--app-text-secondary)' }}>
                        Answers describe engine-computed results only — the assistant cannot change
                        project data. Configure providers under Settings → AI Assistant.
                    </div>
                </div>
            )}
        </div>
    );
}

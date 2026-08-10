/**
 * The assistant's conversation surface: suggestion chips, prompt box, route
 * pills with per-tier confidence, and the answers. Frame-agnostic — the
 * floating sheet renders it today; any future host passes the same props.
 */
import React from 'react';
import { Button, Form, Spinner } from 'react-bootstrap';
import { pillStyle, pillLabel } from './routePills.js';

export default function AiConversation({ assistant, chips }) {
    const { prompt, setPrompt, busy, outcome, ask } = assistant;

    return (
        <div>
            <div className="d-flex flex-wrap gap-1 mb-2">
                {chips.map((example) => (
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
                    placeholder="Ask about this project…"
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
                Answers describe this project's own data and engine-computed results —
                the assistant cannot change anything. Configure providers under
                Settings → AI Assistant.
            </div>
        </div>
    );
}

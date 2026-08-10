/**
 * The Results page's slim affordance for the assistant: a small pill that
 * opens the floating sheet (the old in-page panel moved there — see
 * docs/ai-integration-plan.md §3.5). Loaded only through the same
 * VITE_AI_ENABLED lazy gate as everything else in this package.
 */
import AiLogoMark from './AiLogoMark.jsx';
import { openAssistant } from './assistantBus.js';
import { loadPrefs } from '../../../lib/ai/index.js';

export default function AiResultsCue({ label = 'Ask the AI assistant about these results' }) {
    if (!loadPrefs().enabled) return null;
    return (
        <button
            type="button"
            onClick={openAssistant}
            className="d-inline-flex align-items-center gap-2"
            data-testid="ai-results-cue"
            style={{
                border: '1px dashed var(--app-border-mid)',
                background: 'var(--app-bg-card)',
                color: 'var(--app-text-secondary)',
                borderRadius: '999px',
                padding: '4px 14px 4px 8px',
                fontSize: '0.8rem',
                cursor: 'pointer',
            }}
        >
            <AiLogoMark size={18} />
            {label}
        </button>
    );
}

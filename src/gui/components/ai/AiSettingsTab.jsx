/**
 * Settings → AI Assistant tab.
 *
 * Loaded only via dynamic import gated on VITE_AI_ENABLED (see
 * SettingsModal.jsx). All state here writes through src/lib/ai/settings.js —
 * the one audited home of key handling. Nothing in this tab (or anywhere
 * else) syncs the key to Appwrite or into project files.
 */
import { useMemo, useState } from 'react';
import { Button, Form } from 'react-bootstrap';
import {
    loadPrefs, savePrefs, loadKey, saveKey, clearKey, maskKey,
    providerStatus, runPrompt, MODES, providerMeta,
    loadEncoder, loadGemma, ENCODER_DOWNLOAD_MB, GEMMA_DOWNLOAD_MB,
} from '../../../lib/ai/index.js';

export default function AiSettingsTab({ theme }) {
    const [prefs, setPrefs] = useState(loadPrefs);
    const [keyValue, setKeyValue] = useState(loadKey);
    const [showKey, setShowKey] = useState(false);
    const [testState, setTestState] = useState(null); // {ok, message}
    const [encoderStatus, setEncoderStatus] = useState('');
    const [gemmaStatus, setGemmaStatus] = useState('');

    const status = useMemo(() => providerStatus(prefs, keyValue), [prefs, keyValue]);
    const providers = providerMeta();
    const modeNeedsModel = MODES[prefs.mode]?.needsModel;
    const isCascade = prefs.mode === 'cascade';

    const apply = (patch) => setPrefs(savePrefs(patch));

    const prefetch = async (loader, setStatus) => {
        try {
            await loader(setStatus);
        } catch (error) {
            setStatus(`Failed: ${error.message}`);
        }
    };

    const commitKey = (value, storage = prefs.storage) => {
        setKeyValue(value);
        saveKey(value, storage);
    };

    const testKey = async () => {
        setTestState({ ok: null, message: 'Testing…' });
        const outcome = await runPrompt(
            'Reply using the answer tool with the single word: ready.',
            {
                context: { project: { name: 'connection test', currency: 'INR' }, results: null, validation: { errors: [], warnings: [] } },
                prefs: { ...prefs, mode: 'model' },
                apiKey: keyValue,
            },
        );
        setTestState(outcome.status === 'success' && !outcome.degraded
            ? { ok: true, message: `Works — ${outcome.provider} responded using ${outcome.model}.` }
            : { ok: false, message: outcome.error || outcome.degraded ? 'No API key or proxy URL to test.' : 'Test failed.' });
    };

    const hint = { fontSize: '0.78rem', color: theme.textSecondary, marginTop: '2px' };

    return (
        <div style={{ border: `1px solid ${theme.border}`, padding: '20px', borderRadius: '4px', backgroundColor: theme.bgCard }}>
            <Form.Group className="mb-4">
                <Form.Check
                    type="switch"
                    id="ai-enabled-switch"
                    label="Enable the AI assistant"
                    checked={prefs.enabled}
                    onChange={(e) => apply({ enabled: e.target.checked })}
                />
                <div style={hint}>
                    Shows a read-only assistant on the Results page. It can explain computed
                    results; it cannot change project data.
                </div>
            </Form.Group>

            <Form.Group className="mb-4">
                <Form.Label>How questions are handled</Form.Label>
                <Form.Select value={prefs.mode} onChange={(e) => apply({ mode: e.target.value })}>
                    {status.modes.map((mode) => (
                        <option key={mode.id} value={mode.id}>{mode.label}</option>
                    ))}
                </Form.Select>
                <div style={hint}>{MODES[prefs.mode]?.blurb}</div>
                {status.degraded && (
                    <div style={{ ...hint, color: theme.activeIconColor }}>{status.degradedReason}</div>
                )}
            </Form.Group>

            {isCascade && (
                <div
                    className="mb-4 p-3 rounded"
                    style={{ border: `1px solid ${theme.border}` }}
                    data-testid="ai-local-models"
                >
                    <div className="fw-bold mb-2" style={{ fontSize: '0.9rem' }}>Local models</div>
                    <div style={{ ...hint, marginBottom: '10px' }}>
                        Everything below runs inside this browser — free, offline after the
                        one-time download, and nothing is sent anywhere. Tiers hand over to the
                        next when their confidence is below the threshold.
                    </div>

                    <Form.Check
                        type="switch"
                        id="ai-local-encoder"
                        label={`Paraphrase matcher (~${ENCODER_DOWNLOAD_MB} MB) — maps free-form phrasings to known questions`}
                        checked={prefs.local.encoder}
                        onChange={(e) => apply({ local: { encoder: e.target.checked } })}
                        style={{ fontSize: '0.85rem' }}
                    />
                    <div className="d-flex gap-2 align-items-center mt-1 mb-3">
                        <Button
                            size="sm"
                            variant="outline-secondary"
                            disabled={!prefs.local.encoder}
                            onClick={() => prefetch(loadEncoder, setEncoderStatus)}
                        >
                            Download now
                        </Button>
                        <span style={hint}>{encoderStatus || 'Downloads on first use if not prefetched.'}</span>
                    </div>

                    <Form.Group className="mb-3">
                        <Form.Label style={{ fontSize: '0.85rem' }}>
                            Matcher confidence threshold ({Math.round(prefs.local.encoderThreshold * 100)}%)
                        </Form.Label>
                        <Form.Range
                            min={0.5}
                            max={0.95}
                            step={0.01}
                            value={prefs.local.encoderThreshold}
                            onChange={(e) => apply({ local: { encoderThreshold: Number(e.target.value) } })}
                        />
                        <div style={hint}>
                            Below this similarity the matcher refuses instead of guessing and the
                            question falls through to the next tier. Lower = more answers, more
                            mistakes; higher = stricter.
                        </div>
                    </Form.Group>

                    <Form.Check
                        type="switch"
                        id="ai-local-gemma"
                        label={`FunctionGemma 270M (~${GEMMA_DOWNLOAD_MB} MB) — experimental generative tier`}
                        checked={prefs.local.gemma}
                        onChange={(e) => apply({ local: { gemma: e.target.checked } })}
                        style={{ fontSize: '0.85rem' }}
                    />
                    <div className="d-flex gap-2 align-items-center mt-1">
                        <Button
                            size="sm"
                            variant="outline-secondary"
                            disabled={!prefs.local.gemma}
                            onClick={() => prefetch(loadGemma, setGemmaStatus)}
                        >
                            Download now
                        </Button>
                        <span style={hint}>
                            {gemmaStatus || 'Large download; WebGPU recommended. Expect rough answers until fine-tuned.'}
                        </span>
                    </div>
                </div>
            )}

            {modeNeedsModel && (
                <>
                    <Form.Group className="mb-4">
                        <Form.Label>Model provider</Form.Label>
                        <Form.Select
                            value={prefs.provider}
                            onChange={(e) => apply({ provider: e.target.value, model: '' })}
                        >
                            {providers.map((provider) => (
                                <option key={provider.id} value={provider.id}>{provider.label}</option>
                            ))}
                        </Form.Select>
                    </Form.Group>

                    <Form.Group className="mb-4">
                        <Form.Label>API key</Form.Label>
                        <div className="d-flex gap-2">
                            <Form.Control
                                type={showKey ? 'text' : 'password'}
                                autoComplete="off"
                                spellCheck={false}
                                value={keyValue}
                                placeholder="paste your own key"
                                onChange={(e) => commitKey(e.target.value.trim())}
                            />
                            <Button variant="outline-secondary" onClick={() => setShowKey(!showKey)}>
                                {showKey ? 'Hide' : 'Show'}
                            </Button>
                        </div>
                        <div style={hint}>
                            {keyValue
                                ? `Key loaded (${maskKey(keyValue)}), kept: ${prefs.storage === 'none' ? 'memory only' : prefs.storage}.`
                                : 'No key. Without one (or a proxy URL below), model modes run on the offline rules.'}
                        </div>
                    </Form.Group>

                    <Form.Group className="mb-4">
                        <Form.Label>Keep this key</Form.Label>
                        {[
                            ['local', 'On this browser', 'survives closing the browser (localStorage, unencrypted)'],
                            ['session', 'Until this tab closes', 'sessionStorage — safer default on a shared machine'],
                            ['none', "Don't keep it", 'memory only, gone on refresh'],
                        ].map(([value, label, description]) => (
                            <Form.Check
                                key={value}
                                type="radio"
                                id={`ai-storage-${value}`}
                                name="ai-key-storage"
                                label={`${label} — ${description}`}
                                checked={prefs.storage === value}
                                onChange={() => { apply({ storage: value }); commitKey(keyValue, value); }}
                                style={{ fontSize: '0.85rem' }}
                            />
                        ))}
                    </Form.Group>

                    <Form.Group className="mb-4">
                        <Form.Label>Model <span style={hint}>(blank = provider default)</span></Form.Label>
                        <Form.Control
                            type="text"
                            spellCheck={false}
                            value={prefs.model}
                            placeholder={providers.find((p) => p.id === prefs.provider)?.defaultModel || ''}
                            onChange={(e) => apply({ model: e.target.value.trim() })}
                        />
                    </Form.Group>

                    <Form.Group className="mb-4">
                        <Form.Label>Proxy URL <span style={hint}>(optional — for organisations)</span></Form.Label>
                        <Form.Control
                            type="text"
                            spellCheck={false}
                            value={prefs.proxyUrl}
                            placeholder="https://ai.example.org/lcca-assistant"
                            onChange={(e) => apply({ proxyUrl: e.target.value.trim() })}
                        />
                        <div style={hint}>
                            If set, questions go to this endpoint instead of calling the provider
                            directly, and the API key stays on that server — this browser never
                            needs one. See docs/ai-setup.md for the endpoint contract.
                        </div>
                    </Form.Group>

                    <div
                        className="mb-4 p-3 rounded"
                        style={{ border: `1px solid ${theme.activeIconColor}`, fontSize: '0.8rem', color: theme.textSecondary }}
                    >
                        <strong style={{ color: theme.textPrimary }}>Before pasting a key:</strong>{' '}
                        a saved key is stored in this browser in plain text and is readable by any
                        script on this page — only do this on a machine you trust. Use a key with a
                        spending limit, scoped to this use, and revoke it when done. Keys never sync
                        to your account or into project files. Deployed installations should prefer
                        the proxy option.
                    </div>

                    <div className="d-flex gap-2 align-items-center">
                        <Button variant="outline-secondary" onClick={testKey}>Test connection</Button>
                        <Button
                            variant="outline-secondary"
                            onClick={() => { clearKey(); setKeyValue(''); setTestState(null); }}
                        >
                            Clear key
                        </Button>
                        {testState && (
                            <span style={{
                                fontSize: '0.8rem',
                                color: testState.ok === false ? '#c2410c' : testState.ok ? '#17803d' : theme.textSecondary,
                            }}
                            >
                                {testState.message}
                            </span>
                        )}
                    </div>
                </>
            )}
        </div>
    );
}

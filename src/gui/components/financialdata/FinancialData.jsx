/* eslint-disable no-unused-vars */
import React, { useState, useCallback, useEffect } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import { normalizeFinancialData, validateFinancialData } from '../../../utils/projectPageSchema';
import './FinancialData.css';

// ── Constants ────────────────────────────────────────────────────────────────

const FINANCIAL_FIELDS = [
    {
        key: 'discount_rate',
        label: 'Discount Rate',
        hint: 'The rate used to convert future cash flows into present value. Reflects the time value of money and investment risk.',
        type: 'float',
        min: 0.0,
        max: 100.0,
        step: 0.01,
        unit: '(%)',
        required: true,
    },
    {
        key: 'discount_rate_source',
        label: 'Source: Discount Rate',
        type: 'text',
        required: false,
    },
    {
        key: 'inflation_rate',
        label: 'Inflation Rate',
        hint: 'Expected annual increase in general price levels over time.',
        type: 'float',
        min: 0.0,
        max: 100.0,
        step: 0.01,
        unit: '(%)',
        required: true,
    },
    {
        key: 'inflation_rate_source',
        label: 'Source: Inflation Rate',
        type: 'text',
        required: false,
    },
    {
        key: 'interest_rate',
        label: 'Interest Rate',
        hint: 'The borrowing or lending rate applied to capital financing.',
        type: 'float',
        min: 0.0,
        max: 100.0,
        step: 0.01,
        unit: '(%)',
        required: true,
    },
    {
        key: 'interest_rate_source',
        label: 'Source: Interest Rate',
        type: 'text',
        required: false,
    },
    {
        key: 'investment_ratio',
        label: 'Investment Ratio',
        hint: 'Proportion of total cost financed through investment (0–1). Example: 0.5 means 50%.',
        type: 'float',
        min: 0.0,
        max: 1.0,
        step: 0.0001,
        unit: null,
        required: true,
    },
    {
        key: 'investment_ratio_source',
        label: 'Source: Investment Ratio',
        type: 'text',
        required: false,
    },
];

const SUGGESTED_VALUES = {
    discount_rate: 6.70,
    inflation_rate: 5.15,
    interest_rate: 7.75,
    investment_ratio: 0.5,
};

const INITIAL_STATE = Object.fromEntries(
    FINANCIAL_FIELDS.map((f) => [f.key, f.type === 'text' ? '' : ''])
);

const REQUIRED_KEYS = new Set(
    FINANCIAL_FIELDS.filter((f) => f.required).map((f) => f.key)
);

const NUMBER_FIELDS = FINANCIAL_FIELDS.filter((f) => f.type !== 'text');
const FIELD_BY_KEY = Object.fromEntries(FINANCIAL_FIELDS.map((f) => [f.key, f]));
const SUGGESTED_SOURCE = '3psLCCA suggested default';

/** Returns an inline error message when a numeric value is outside the field's min/max, otherwise ''. */
const getRangeError = (key, value) => {
    const field = FIELD_BY_KEY[key];
    if (!field || field.type === 'text') return '';
    if (value === '' || value === null || value === undefined) return '';
    const number = Number(value);
    if (Number.isNaN(number)) return `${field.label} must be a number.`;
    if (number < field.min || number > field.max) {
        return `${field.label} must be between ${field.min} and ${field.max}${field.unit ? ` ${field.unit}` : ''}.`;
    }
    return '';
};

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({ title }) {
    return (
        <h5 className="mb-4 fw-bold pb-2 mt-4" style={{ borderBottom: '1px solid var(--app-border-dark)', fontSize: '1rem', color: 'var(--app-text-primary)', transition: 'all 0.3s' }}>
            {title}
        </h5>
    );
}

function FieldHint({ text }) {
    if (!text) return null;
    return (
        <div style={{ fontSize: '0.8rem', color: 'var(--app-text-muted)', marginBottom: '8px' }}>
            {text}
        </div>
    );
}

function TextField({ field, value, onChange }) {
    const { key, label, hint, required } = field;
    return (
        <div className="mb-4">
            <label htmlFor={key} className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>
                {label}{required && <span className="text-danger"> *</span>}
            </label>
            <FieldHint text={hint} />
            <input
                id={key}
                type="text"
                value={value || ''}
                onChange={(e) => onChange(key, e.target.value)}
                className="form-control"
                placeholder="Source information..."
            />
        </div>
    );
}

function NumberField({ field, value, onChange, onBlur, hasError, errorMessage }) {
    const { key, label, hint, required, min, max, step, unit } = field;
    return (
        <div className="mb-4">
            <label htmlFor={key} className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>
                {label}{required && <span className="text-danger"> *</span>}
            </label>
            <FieldHint text={hint} />
            <div className={`input-group ${hasError ? 'is-invalid' : ''}`}>
                <input
                    id={key}
                    type="number"
                    min={min}
                    max={max}
                    step={step}
                    value={value || ''}
                    onChange={(e) => onChange(key, e.target.value)}
                    onBlur={(e) => onBlur && onBlur(key, e.target.value)}
                    className={`form-control ${hasError ? 'is-invalid' : ''}`}
                    aria-invalid={hasError || undefined}
                    aria-describedby={errorMessage ? `${key}-error` : undefined}
                />
                {unit && (
                    <span className="input-group-text border-start-0" style={{ fontSize: '0.8rem', backgroundColor: 'var(--app-bg-alt)', borderColor: 'var(--app-border-mid)' }}>
                        {unit}
                    </span>
                )}
            </div>
            {errorMessage && (
                <div id={`${key}-error`} className="invalid-feedback d-block" style={{ fontSize: '0.8rem' }}>
                    {errorMessage}
                </div>
            )}
        </div>
    );
}

// ── Main Component ────────────────────────────────────────────────────────────

const FinancialData = ({ controller }) => {
    const { projectData, updateProjectData } = useProjectData();
    const [form, setForm] = useState(() => {
        const saved = projectData.financial_data;
        return normalizeFinancialData((saved && Object.keys(saved).length > 0) ? { ...INITIAL_STATE, ...saved } : INITIAL_STATE);
    });
    const [errors, setErrors] = useState(new Set());
    const [rangeErrors, setRangeErrors] = useState({});
    const [validationMsg, setValidationMsg] = useState('');
    const [statusMsg, setStatusMsg] = useState('');

    // Auto-dismiss the transient status line
    useEffect(() => {
        if (!statusMsg) return undefined;
        const timer = setTimeout(() => setStatusMsg(''), 3000);
        return () => clearTimeout(timer);
    }, [statusMsg]);

    // Sync local state when projectData changes externally
    useEffect(() => {
        const saved = projectData.financial_data;
        const next = normalizeFinancialData({ ...INITIAL_STATE, ...(saved || {}) });
        setForm(prev => JSON.stringify(next) !== JSON.stringify(prev) ? next : prev);
    }, [projectData.financial_data]);

    // Sync form to context whenever it changes
    useEffect(() => {
        updateProjectData('financial_data', form);
    }, [form, updateProjectData]);

    // ── Handlers ─────────────────────────────────────────────────────────────

    const updateRangeError = useCallback((key, value) => {
        const message = getRangeError(key, value);
        setRangeErrors((prev) => {
            if ((prev[key] || '') === message) return prev;
            const next = { ...prev };
            if (message) next[key] = message;
            else delete next[key];
            return next;
        });
    }, []);

    const handleChange = useCallback((key, value) => {
        setForm(prev => ({ ...prev, [key]: value }));
        setErrors(prev => {
            if (!prev.has(key)) return prev;
            const next = new Set(prev);
            next.delete(key);
            return next;
        });

        // Clear errors if the field becomes valid
        if (REQUIRED_KEYS.has(key)) {
            setErrors((prev) => {
                const next = new Set(prev);
                if (value && value.toString().trim() && Number(value) > 0) {
                    next.delete(key);
                }
                return next;
            });
        }
        updateRangeError(key, value);
        setValidationMsg('');
    }, [updateRangeError]);

    const handleBlur = useCallback((key, value) => {
        updateRangeError(key, value);
    }, [updateRangeError]);

    const handleLoadSuggested = () => {
        const next = {
            ...form, ...Object.fromEntries(
                Object.entries(SUGGESTED_VALUES).map(([k, v]) => [k, String(v)])
            )
        };
        // Record provenance for every suggested value unless the user already typed a source
        Object.keys(SUGGESTED_VALUES).forEach((k) => {
            const sourceKey = `${k}_source`;
            if (sourceKey in INITIAL_STATE && !(next[sourceKey] || '').toString().trim()) {
                next[sourceKey] = SUGGESTED_SOURCE;
            }
        });
        setForm(next);
        setErrors(new Set());
        setRangeErrors({});
        setValidationMsg('');
        setStatusMsg('Suggested values applied');
        controller?.engine?._log('Financial: Suggested values applied.');
    };

    const handleClearAll = () => {
        if (!window.confirm('Clear all financial inputs? This cannot be undone.')) return;
        setForm(INITIAL_STATE);
        updateProjectData('financial_data', INITIAL_STATE);
        setErrors(new Set());
        setRangeErrors({});
        setValidationMsg('');
        setStatusMsg('');
        controller?.engine?._log('Financial: All fields cleared.');
    };

    const hasError = (key) => errors.has(key) || Boolean(rangeErrors[key]);

    // ── Validation ────────────────────────────────────────────────────────────
    const validate = () => {
        const messages = validateFinancialData(form);
        const newErrors = new Set();
        REQUIRED_KEYS.forEach((key) => {
            if (messages.some((message) => message.includes(key.replace(/_/g, ' ')))) newErrors.add(key);
        });

        // Out-of-range values are invalid even when the shared schema accepts them
        const newRangeErrors = {};
        NUMBER_FIELDS.forEach(({ key }) => {
            const message = getRangeError(key, form[key]);
            if (message) {
                newRangeErrors[key] = message;
                newErrors.add(key);
                if (!messages.includes(message)) messages.push(message);
            }
        });
        setRangeErrors(newRangeErrors);

        setErrors(newErrors);
        if (newErrors.size > 0) {
            const msg = `Financial data needs attention: ${messages.join(' ')}`;
            setValidationMsg(msg);
            controller?.engine?._log(msg);
            return { valid: false, errors: messages };
        }

        setValidationMsg('');
        return { valid: true, errors: [] };
    };



    // ---- Render --------------------------------------------------------------

    return (
        <div style={{ padding: '24px', color: 'var(--app-text-primary)' }}>
            <SectionHeader title="Economic Parameters" />

            {FINANCIAL_FIELDS.map((field) => (
                field.type === 'text' ? (
                    <TextField
                        key={field.key}
                        field={field}
                        value={form[field.key]}
                        onChange={handleChange}
                    />
                ) : (
                    <NumberField
                        key={field.key}
                        field={field}
                        value={form[field.key]}
                        onChange={handleChange}
                        onBlur={handleBlur}
                        hasError={hasError(field.key)}
                        errorMessage={rangeErrors[field.key] || ''}
                    />
                )
            ))}

            <div className="d-flex gap-3 mt-4 mb-3">
                <button
                    className="btn flex-grow-1 py-2 fw-bold"
                    style={{ backgroundColor: 'var(--app-primary-accent)', color: 'var(--app-btn-primary-text)', border: 'none', borderRadius: '8px', transition: 'all 0.2s' }}
                    onClick={handleLoadSuggested}
                    onMouseEnter={(e) => { e.target.style.opacity = '0.9'; e.target.style.transform = 'translateY(-1px)'; }}
                    onMouseLeave={(e) => { e.target.style.opacity = '1'; e.target.style.transform = 'none'; }}
                >
                    Load Suggested Values
                </button>
                <button
                    className="btn flex-grow-1 py-2 fw-bold"
                    style={{ backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-secondary)', border: '1px solid var(--app-border-mid)', borderRadius: '8px', transition: 'all 0.2s' }}
                    onClick={handleClearAll}
                    onMouseEnter={(e) => { e.target.style.backgroundColor = 'var(--app-border-light)'; e.target.style.color = 'var(--app-text-primary)'; }}
                    onMouseLeave={(e) => { e.target.style.backgroundColor = 'var(--app-bg-alt)'; e.target.style.color = 'var(--app-text-secondary)'; }}
                >
                    Clear All
                </button>
            </div>

            {statusMsg && (
                <div className="mb-3" style={{ fontSize: '0.85rem', color: 'var(--app-primary-accent)' }} role="status" aria-live="polite">
                    ✓ {statusMsg}
                </div>
            )}

            {validationMsg && (
                <div className="alert alert-danger p-2 mt-3 d-flex align-items-center" style={{ fontSize: '0.85rem', borderRadius: '8px' }} role="alert">
                    <span className="me-2">⚠️</span> {validationMsg}
                </div>
            )}
        </div>
    );
};

export { FinancialData as default };
export { REQUIRED_KEYS, INITIAL_STATE, SUGGESTED_VALUES };

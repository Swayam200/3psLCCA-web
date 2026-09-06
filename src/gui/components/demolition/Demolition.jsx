/* eslint-disable no-unused-vars */
import React, { useState, useCallback, useEffect } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import { normalizeDemolitionData, validateDemolitionData } from '../../../utils/projectPageSchema';
import '../financialdata/FinancialData.css';

// ── Constants ────────────────────────────────────────────────────────────────


const DEMOLITION_SECTIONS = [
    {
        title: "End of Life",
        fields: [
            {
                key: 'demolition_cost',
                label: 'Demolition & Disposal Cost (%)',
                hint: 'Demolition and disposal cost expressed as a percentage of initial construction cost.',
                type: 'float',
                min: 0.0,
                max: 100.0,
                step: 0.1,
                unit: '(%)',
                required: true,
                docSlug: 'demolition-cost',
            },
            {
                key: 'demolition_carbon_cost',
                label: 'Demolition & Disposal Carbon Cost (%)',
                hint: 'Carbon emission cost of demolition expressed as a percentage of initial carbon emission cost.',
                type: 'float',
                min: 0.0,
                max: 100.0,
                step: 0.1,
                unit: '(%)',
                required: true,
                docSlug: 'demolition-carbon-cost',
            },
            {
                key: 'demolition_duration',
                label: 'Demolition & Disposal Duration',
                hint: 'Time taken for demolition work in months',
                type: 'int',
                min: 0,
                max: 120,
                step: 1,
                unit: '(months)',
                required: true,
                docSlug: 'demolition-duration',
            },
            {
                key: 'demolition_method',
                label: 'Demolition Method',
                hint: 'Type of demolition method used.',
                type: 'select',
                options: ['Implosion', 'Mechanical Demolition', 'Deconstruction', 'Wrecking Ball'],
                required: false,
                docSlug: 'demolition-method',
            }
        ]
    }
];

const SUGGESTED_VALUES = {
    demolition_cost: 10.0,
    demolition_carbon_cost: 10.0,
    demolition_duration: 1,
    demolition_method: 'Implosion',
};

// Flatten fields for easy processing
const ALL_FIELDS = DEMOLITION_SECTIONS.flatMap(section => section.fields);

const INITIAL_STATE = Object.fromEntries(
    ALL_FIELDS.map((f) => [f.key, ''])
);

const REQUIRED_KEYS = new Set(
    ALL_FIELDS.filter((f) => f.required).map((f) => f.key)
);

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({ title }) {
    return (
        <h5 className="mb-4 fw-bold pb-2 mt-4" style={{ borderBottom: '1px solid var(--app-border-dark)', fontSize: '1rem', color: 'var(--app-text-primary)', transition: 'all 0.3s' }}>
            {title}
        </h5>
    );
}

function FieldHint({ text }) {
    return (
        <div style={{ fontSize: '0.8rem', color: 'var(--app-text-muted)', marginBottom: '8px' }}>
            {text}
        </div>
    );
}

function InputField({ field, value, onChange, hasError }) {
    const { key, label, hint, docSlug, required, type, min, max, step, unit, options } = field;
    return (
        <div className="mb-4">
            <label htmlFor={key} className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>
                {label}{required && <span className="text-danger"> *</span>}
            </label>
            <FieldHint text={hint} docSlug={docSlug} />
            
            {type === 'select' ? (
                <select
                    id={key}
                    value={value}
                    onChange={(e) => onChange(key, e.target.value)}
                    className={`form-select ${hasError ? 'is-invalid' : ''}`}
                    style={{ backgroundColor: 'var(--app-input-bg)', borderColor: 'var(--app-input-border)', color: 'var(--app-input-text)' }}
                >
                    <option value="" disabled>Select {label}</option>
                    {options.map(opt => (
                        <option key={opt} value={opt}>{opt}</option>
                    ))}
                </select>
            ) : (
                <div className={`input-group ${hasError ? 'is-invalid' : ''}`}>
                    <input
                        id={key}
                        type="number"
                        min={min}
                        max={max}
                        step={step}
                        value={value}
                        onChange={(e) => onChange(key, e.target.value)}
                        className={`form-control ${hasError ? 'is-invalid' : ''}`}
                    />
                    {unit && (
                        <span className="input-group-text border-start-0" style={{ fontSize: '0.8rem', backgroundColor: 'var(--app-input-bg)', borderColor: 'var(--app-input-border)' }}>
                            {unit}
                        </span>
                    )}
                </div>
            )}
        </div>
    );
}

// ── Main Component ────────────────────────────────────────────────────────────

const Demolition = ({ controller, engine }) => {
    const { projectData, updateProjectData } = useProjectData();
    const [form, setForm] = useState(() => {
        const saved = projectData.demolition_data;
        return normalizeDemolitionData((saved && Object.keys(saved).length > 0) ? { ...INITIAL_STATE, ...saved } : INITIAL_STATE);
    });

    useEffect(() => {
        const next = normalizeDemolitionData({ ...INITIAL_STATE, ...(projectData.demolition_data || {}) });
        setForm(prev => JSON.stringify(next) !== JSON.stringify(prev) ? next : prev);
    }, [projectData.demolition_data]);

    useEffect(() => {
        updateProjectData('demolition_data', {
            ...form,
            demolition_cost_pct: parseFloat(form.demolition_cost) || 0,
            demolition_carbon_cost_pct: parseFloat(form.demolition_carbon_cost) || 0,
        });
    }, [form, updateProjectData]);

    const [errors, setErrors] = useState(new Set());
    const [validationMsg, setValidationMsg] = useState('');
    const [statusMsg, setStatusMsg] = useState('');

    // Auto-dismiss the transient status line
    useEffect(() => {
        if (!statusMsg) return undefined;
        const timer = setTimeout(() => setStatusMsg(''), 3000);
        return () => clearTimeout(timer);
    }, [statusMsg]);

    // ── Handlers ─────────────────────────────────────────────────────────────

    const handleChange = useCallback((key, value) => {
        setForm((prev) => ({ ...prev, [key]: value }));
        setErrors((prev) => {
            if (!prev.has(key)) return prev;
            const next = new Set(prev);
            next.delete(key);
            return next;
        });
        setValidationMsg('');
    }, []);

    const handleLoadSuggested = () => {
        setForm((prev) => ({
            ...prev, ...Object.fromEntries(
                Object.entries(SUGGESTED_VALUES).map(([k, v]) => [k, String(v)])
            )
        }));
        setErrors(new Set());
        setValidationMsg('');
        setStatusMsg('Suggested values applied');
        if (engine && engine._log) {
            engine._log('Demolition: Suggested values applied.');
        } else if (controller && controller.engine) {
            controller.engine._log('Demolition: Suggested values applied.');
        }
    };

    const handleClearAll = () => {
        if (!window.confirm('Clear all demolition inputs? This cannot be undone.')) return;
        setForm(INITIAL_STATE);
        setErrors(new Set());
        setValidationMsg('');
        setStatusMsg('');
        if (engine && engine._log) {
            engine._log('Demolition: All fields cleared.');
        } else if (controller && controller.engine) {
            controller.engine._log('Demolition: All fields cleared.');
        }
    };

    // ── Validation ────────────────────────────────────────────────────────────

    const validate = () => {
        const messages = validateDemolitionData(form);
        const newErrors = new Set();
        REQUIRED_KEYS.forEach((key) => {
            if (messages.some((message) => message.includes(key.replace(/_/g, ' ')))) newErrors.add(key);
        });

        setErrors(newErrors);
        if (newErrors.size > 0) {
            const msg = `Demolition data needs attention: ${messages.join(' ')}`;
            setValidationMsg(msg);
            if (engine && engine._log) engine._log(msg);
            else if (controller && controller.engine) controller.engine._log(msg);
            return { valid: false, errors: messages };
        }

        setValidationMsg('');
        return { valid: true, errors: [] };
    };

    const hasError = (key) => errors.has(key);

    // ── Render ────────────────────────────────────────────────────────────────

    return (
        <div style={{ padding: '24px', color: 'var(--app-text-primary)' }}>
            
            {DEMOLITION_SECTIONS.map((section, idx) => (
                <div key={idx}>
                    <SectionHeader title={section.title} />
                    {section.fields.map((field) => (
                        <InputField
                            key={field.key}
                            field={field}
                            value={form[field.key]}
                            onChange={handleChange}
                            hasError={hasError(field.key)}
                        />
                    ))}
                </div>
            ))}

            {/* ── Buttons ─────────────────────────────────────────────────── */}
            <div className="d-flex gap-2 mt-4 mb-3">
                <button
                    className="btn flex-grow-1"
                    style={{ backgroundColor: 'var(--app-primary-accent)', color: '#fff', border: '1px solid var(--app-primary-accent)' }}
                    onClick={handleLoadSuggested}
                    onMouseEnter={(e) => { e.target.style.opacity = '0.9'; }}
                    onMouseLeave={(e) => { e.target.style.opacity = '1'; }}
                >
                    Load Suggested Values
                </button>
                <button
                    className="btn flex-grow-1"
                    style={{ backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-secondary)', border: '1px solid var(--app-border-mid)' }}
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

            {/* Validation message */}
            {validationMsg && (
                <div className="alert alert-danger p-2" style={{ fontSize: '0.8rem' }} role="alert">
                    ⚠ {validationMsg}
                </div>
            )}
        </div>
    );
};

export { Demolition as default };
export { REQUIRED_KEYS, INITIAL_STATE, SUGGESTED_VALUES, ALL_FIELDS as DEMOLITION_FIELDS };

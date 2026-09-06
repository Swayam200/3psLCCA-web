/* eslint-disable no-unused-vars */
import React, { useState, useCallback, useEffect } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import { normalizeMaintenanceData, validateMaintenanceData } from '../../../utils/projectPageSchema';
import '../financialdata/FinancialData.css';

// ── Constants ────────────────────────────────────────────────────────────────


const MAINTENANCE_SECTIONS = [
    {
        title: "Routine Maintenance",
        fields: [
            {
                key: 'routine_inspection_cost',
                label: 'Routine Inspection Cost',
                hint: 'Cost incurred for routine inspection expressed as percentage of initial construction cost',
                type: 'float',
                min: 0.0,
                max: 100.0,
                step: 0.001,
                unit: '(% of initial construction cost)',
                required: true,
                docSlug: 'routine-inspection-cost',
            },
            {
                key: 'routine_inspection_freq',
                label: 'Routine Inspection Frequency',
                hint: 'Interval between routine inspections.',
                type: 'int',
                min: 0,
                max: 50,
                step: 1,
                unit: '(yr)',
                required: true,
                docSlug: 'routine-inspection-freq',
            }
        ]
    },
    {
        title: "Periodic Maintenance",
        fields: [
            {
                key: 'periodic_maintenance_cost',
                label: 'Periodic Maintenance Cost',
                hint: 'Cost incurred for periodic maintenance expressed as percentage of initial construction cost',
                type: 'float',
                min: 0.0,
                max: 100.0,
                step: 0.001,
                unit: '(% of initial construction cost)',
                required: true,
                docSlug: 'periodic-maintenance-cost',
            },
            {
                key: 'periodic_maintenance_carbon_cost',
                label: 'Periodic Maintenance Carbon Cost',
                hint: 'Carbon emission cost of periodic maintenance expressed as a percentage of initial carbon emission cost.',
                type: 'float',
                min: 0.0,
                max: 100.0,
                step: 0.001,
                unit: '(%)',
                required: true,
                docSlug: 'periodic-maintenance-carbon-cost',
            },
            {
                key: 'periodic_maintenance_freq',
                label: 'Periodic Maintenance Frequency',
                hint: 'Interval between periodic maintenance works.',
                type: 'int',
                min: 0,
                max: 100,
                step: 1,
                unit: '(yr)',
                required: true,
                docSlug: 'periodic-maintenance-freq',
            }
        ]
    },
    {
        title: "Major Works",
        fields: [
            {
                key: 'major_inspection_cost',
                label: 'Major Inspection Cost',
                hint: 'Cost of major inspection expressed as a percentage of initial construction cost.',
                type: 'float',
                min: 0.0,
                max: 100.0,
                step: 0.001,
                unit: '(%)',
                required: true,
                docSlug: 'major-inspection-cost',
            },
            {
                key: 'major_inspection_freq',
                label: 'Major Inspection Frequency',
                hint: 'Interval between major inspections.',
                type: 'int',
                min: 0,
                max: 100,
                step: 1,
                unit: '(yr)',
                required: true,
                docSlug: 'major-inspection-freq',
            },
            {
                key: 'major_repair_cost',
                label: 'Major Repair Cost',
                hint: 'Cost of major repair expressed as a percentage of initial construction cost.',
                type: 'float',
                min: 0.0,
                max: 100.0,
                step: 0.001,
                unit: '(%)',
                required: true,
                docSlug: 'major-repair-cost',
            },
            {
                key: 'major_repair_carbon_cost',
                label: 'Major Repair Carbon Cost',
                hint: 'Carbon emission cost of major repair expressed as a percentage of initial carbon emission cost.',
                type: 'float',
                min: 0.0,
                max: 100.0,
                step: 0.001,
                unit: '(%)',
                required: true,
                docSlug: 'major-repair-carbon-cost',
            },
            {
                key: 'major_repair_freq',
                label: 'Major Repair Frequency',
                hint: 'Interval between major repair works.',
                type: 'int',
                min: 0,
                max: 100,
                step: 1,
                unit: '(yr)',
                required: true,
                docSlug: 'major-repair-freq',
            },
            {
                key: 'major_repair_duration',
                label: 'Major Repair Duration',
                hint: 'Duration of major repair works, in months.',
                type: 'int',
                min: 0,
                max: 60,
                step: 1,
                unit: '(months)',
                required: true,
                docSlug: 'major-repair-duration',
            }
        ]
    },
    {
        title: "Bearings & Expansion Joints",
        fields: [
            {
                key: 'bearing_exp_joint_cost',
                label: 'Bearing & Expansion Joint Replacement Cost',
                hint: 'Cost of bearing and expansion joint replacement expressed as a percentage of superstructure cost.',
                type: 'float',
                min: 0.0,
                max: 100.0,
                step: 0.001,
                unit: '(%)',
                required: true,
                docSlug: 'bearing-exp-joint-cost',
            },
            {
                key: 'bearing_exp_joint_freq',
                label: 'Bearing & Expansion Joint Replacement Frequency',
                hint: 'Interval between bearing and expansion joint replacements.',
                type: 'int',
                min: 0,
                max: 100,
                step: 1,
                unit: '(yr)',
                required: true,
                docSlug: 'bearing-exp-joint-freq',
            },
            {
                key: 'bearing_exp_joint_duration',
                label: 'Bearing & Expansion Joint Replacement Duration',
                hint: 'Duration of bearing and expansion joint replacement works, in days.',
                type: 'int',
                min: 0,
                max: 365,
                step: 1,
                unit: '(days)',
                required: true,
                docSlug: 'bearing-exp-joint-duration',
            }
        ]
    }
];

const SUGGESTED_VALUES = {
    routine_inspection_cost: 0.1,
    routine_inspection_freq: 1,
    periodic_maintenance_cost: 0.55,
    periodic_maintenance_carbon_cost: 0.55,
    periodic_maintenance_freq: 5,
    major_inspection_cost: 0.5,
    major_inspection_freq: 5,
    major_repair_cost: 10.0,
    major_repair_carbon_cost: 0.55,
    major_repair_freq: 20,
    major_repair_duration: 3,
    bearing_exp_joint_cost: 12.5,
    bearing_exp_joint_freq: 25,
    bearing_exp_joint_duration: 2,
};

// Flatten fields for easy processing
const ALL_FIELDS = MAINTENANCE_SECTIONS.flatMap(section => section.fields);

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

function NumberField({ field, value, onChange, hasError }) {
    const { key, label, hint, docSlug, required, min, max, step, unit } = field;
    return (
        <div className="mb-4">
            <label htmlFor={key} className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>
                {label}{required && <span className="text-danger"> *</span>}
            </label>
            <FieldHint text={hint} docSlug={docSlug} />
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
        </div>
    );
}

// ── Main Component ────────────────────────────────────────────────────────────

const MaintenanceAndRepair = ({ controller, engine }) => {
    const { projectData, updateProjectData } = useProjectData();
    const [form, setForm] = useState(() => {
        const saved = projectData.maintenance_repair_data;
        return normalizeMaintenanceData((saved && Object.keys(saved).length > 0) ? { ...INITIAL_STATE, ...saved } : INITIAL_STATE);
    });

    useEffect(() => {
        const next = normalizeMaintenanceData({ ...INITIAL_STATE, ...(projectData.maintenance_repair_data || {}) });
        setForm(prev => JSON.stringify(next) !== JSON.stringify(prev) ? next : prev);
    }, [projectData.maintenance_repair_data]);

    useEffect(() => {
        updateProjectData('maintenance_repair_data', form);
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
            engine._log('Maintenance: Suggested values applied.');
        } else if (controller && controller.engine) {
            controller.engine._log('Maintenance: Suggested values applied.');
        }
    };

    const handleClearAll = () => {
        if (!window.confirm('Clear all maintenance and repair inputs? This cannot be undone.')) return;
        setForm(INITIAL_STATE);
        setErrors(new Set());
        setValidationMsg('');
        setStatusMsg('');
        if (engine && engine._log) {
            engine._log('Maintenance: All fields cleared.');
        } else if (controller && controller.engine) {
            controller.engine._log('Maintenance: All fields cleared.');
        }
    };

    // ── Validation ────────────────────────────────────────────────────────────

    const validate = () => {
        const messages = validateMaintenanceData(form);
        const newErrors = new Set();
        REQUIRED_KEYS.forEach((key) => {
            if (messages.some((message) => message.includes(key.replace(/_/g, ' ')))) newErrors.add(key);
        });

        setErrors(newErrors);
        if (newErrors.size > 0) {
            const msg = `Maintenance data needs attention: ${messages.join(' ')}`;
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
            
            {MAINTENANCE_SECTIONS.map((section, idx) => (
                <div key={idx}>
                    <SectionHeader title={section.title} />
                    {section.fields.map((field) => (
                        <NumberField
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
                    style={{ backgroundColor: 'var(--app-primary-accent)', color: 'var(--app-bg-card)', border: '1px solid var(--app-primary-accent)' }}
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

export { MaintenanceAndRepair as default };
export { REQUIRED_KEYS, INITIAL_STATE, SUGGESTED_VALUES, ALL_FIELDS as MAINTENANCE_FIELDS };

/* eslint-disable no-unused-vars */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { data as countriesData } from '../utils/countriesdata';
import { materialCatalog } from '../utils/materialCatalog';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import { Dropdown } from 'react-bootstrap';
import { backfillGeneralInfo } from '../../../utils/projectCreation';
import { normalizeGeneralInfo, validateGeneralInfoData } from '../../../utils/projectPageSchema';
import { getProfiles, getActiveProfile } from '../../utils/profileStorage';
import ProfileAvatar from '../ProfileAvatar';

// ── Constants ────────────────────────────────────────────────────────────────

const BASE_DOCS_URL = 'https://yourdocs.com/general/';

const COUNTRIES = countriesData.map((c) => c.COUNTRY);

const INITIAL_STATE = {
    // Project Information
    project_name: '',
    project_code: '',
    project_description: '',
    remarks: '',
    // Assessing Organisation
    agency_logo: null,
    agency_name: '',
    contact_person: '',
    agency_address: '',
    agency_country: '',
    agency_email: '',
    agency_phone: '',
    // Reviewer
    reviewer_name: '',
    reviewer_organization: '',
    reviewer_address: '',
    reviewer_country: '',
    reviewer_email: '',
    reviewer_phone: '',
    // Project Settings (read-only / locked — shown but not editable)
    project_country: '',
    project_currency: '',
    unit_system: '',
    sor_database: '',
};

const REQUIRED_KEYS = new Set(['project_name']);

// Fields that are display-only (locked)
const LOCKED_KEYS = new Set(['project_country', 'project_currency', 'unit_system']);

// ── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({ title, rightElement }) {
    return (
        <div className="d-flex align-items-center justify-content-between mb-4 mt-4 pb-2" style={{ borderBottom: '1px solid var(--app-border-dark)' }}>
            <h5 className="mb-0 fw-bold" style={{ fontSize: '1rem', color: 'var(--app-text-primary)' }}>
                {title}
            </h5>
            {rightElement && <div>{rightElement}</div>}
        </div>
    );
}

function FieldHint({ text }) {
    return (
        <div style={{ fontSize: '0.8rem', color: 'var(--app-text-muted)', marginBottom: '8px' }}>
            {text}
        </div>
    );
}

function TextField({ id, label, hint, required, value, onChange, hasError, disabled }) {
    return (
        <div className="mb-4">
            <label htmlFor={id} className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>
                {label}{required && <span className="text-danger"> *</span>}
            </label>
            <FieldHint text={hint} />
            <input
                id={id}
                type="text"
                value={value}
                onChange={(e) => onChange && onChange(id, e.target.value)}
                disabled={disabled}
                className={`form-control ${hasError ? 'is-invalid' : ''}`}
                style={disabled ? { opacity: 0.6, cursor: 'not-allowed' } : {}}
            />
        </div>
    );
}

function TextAreaField({ id, label, hint, required, value, onChange, hasError }) {
    return (
        <div className="mb-4">
            <label htmlFor={id} className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>
                {label}{required && <span className="text-danger"> *</span>}
            </label>
            <FieldHint text={hint} />
            <textarea
                id={id}
                rows={4}
                value={value}
                onChange={(e) => onChange(id, e.target.value)}
                className={`form-control ${hasError ? 'is-invalid' : ''}`}
                style={{ resize: 'vertical' }}
            />
        </div>
    );
}

function PhoneField({ id, label, hint, value, onChange, hasError }) {
    return (
        <div className="mb-4">
            <label htmlFor={id} className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>
                {label}
            </label>
            <FieldHint text={hint} />
            <input
                id={id}
                type="tel"
                value={value}
                onChange={(e) => onChange(id, e.target.value)}
                className={`form-control ${hasError ? 'is-invalid' : ''}`}
                placeholder="+1 234 567 8900"
            />
        </div>
    );
}

function SelectField({ id, label, hint, required, options, value, onChange, hasError }) {
    const [open, setOpen] = useState(false);
    const ref = useRef(null);

    useEffect(() => {
        if (!open) return;
        const handler = (e) => {
            if (ref.current && !ref.current.contains(e.target)) setOpen(false);
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [open]);

    const select = (opt) => {
        onChange(id, opt);
        setOpen(false);
    };

    return (
        <div className="mb-4">
            <label className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>
                {label}{required && <span className="text-danger"> *</span>}
            </label>
            <FieldHint text={hint} />
            <div className="position-relative" ref={ref}>
                <button
                    type="button"
                    id={id}
                    className={`form-control d-flex align-items-center justify-content-between text-start ${hasError ? 'is-invalid' : ''}`}
                    onClick={() => setOpen((o) => !o)}
                    aria-haspopup="listbox"
                    aria-expanded={open}
                >
                    <span className={value ? '' : 'text-muted fst-italic'}>
                        {value || '- Select -'}
                    </span>
                    <span className="text-muted ms-2" style={{ fontSize: '0.75rem', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s ease' }}>▾</span>
                </button>
                {open && (
                    <ul className="dropdown-menu show w-100 p-1 shadow-sm overflow-y-auto" role="listbox" style={{ maxHeight: '250px', backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-input-border)' }}>
                        <li
                            className="dropdown-item text-muted fst-italic"
                            style={{ cursor: 'pointer', fontSize: '0.875rem' }}
                            onClick={() => select('')}
                        >
                            - Select -
                        </li>
                        {options.map((opt) => (
                            <li
                                key={opt}
                                role="option"
                                aria-selected={value === opt}
                                className={`dropdown-item ${value === opt ? 'active fw-bold' : ''}`}
                                style={{
                                    cursor: 'pointer',
                                    fontSize: '0.875rem',
                                    backgroundColor: value === opt ? 'var(--app-accent-bg, rgba(115, 165, 175, 0.15))' : 'transparent',
                                    color: value === opt ? 'var(--app-primary-accent)' : 'var(--app-text-primary)',
                                }}
                                onClick={() => select(opt)}
                                onMouseEnter={(e) => { if (value !== opt) e.target.style.backgroundColor = 'var(--app-bg-alt)'; }}
                                onMouseLeave={(e) => { if (value !== opt) e.target.style.backgroundColor = 'transparent'; }}
                            >
                                {opt}
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}

// ── Main Component ────────────────────────────────────────────────────────────

const ProjectInformationPlaceholder = ({ controller }) => {
    const { projectData, updateProjectData } = useProjectData();
    const containerRef = useRef(null);
    const [form, setForm] = useState(() => {
        const filled = backfillGeneralInfo(projectData);
        const saved = filled.general_info || {};
        const activeProfile = getActiveProfile() || {};
        const merged = {
            ...INITIAL_STATE,
            ...saved,
            agency_logo: saved.agency_logo || activeProfile.agency_logo || null,
            agency_name: saved.agency_name || activeProfile.agency_name || '',
            contact_person: saved.contact_person || activeProfile.contact_person || '',
            agency_address: saved.agency_address || activeProfile.agency_address || '',
            agency_country: saved.agency_country || activeProfile.agency_country || '',
            agency_email: saved.agency_email || activeProfile.agency_email || '',
            agency_phone: saved.agency_phone || activeProfile.agency_phone || '',
        };
        return normalizeGeneralInfo(merged, filled);
    });

    // Sync local state if context data changes (e.g. from global storage)
    useEffect(() => {
        const filled = backfillGeneralInfo(projectData);
        const saved = filled.general_info;
        if (saved) {
            if (containerRef.current && containerRef.current.contains(document.activeElement)) {
                return;
            }
            const activeProfile = getActiveProfile() || {};
            const merged = {
                ...INITIAL_STATE,
                ...saved,
                agency_logo: saved.agency_logo || activeProfile.agency_logo || null,
                agency_name: saved.agency_name || activeProfile.agency_name || '',
                contact_person: saved.contact_person || activeProfile.contact_person || '',
                agency_address: saved.agency_address || activeProfile.agency_address || '',
                agency_country: saved.agency_country || activeProfile.agency_country || '',
                agency_email: saved.agency_email || activeProfile.agency_email || '',
                agency_phone: saved.agency_phone || activeProfile.agency_phone || '',
            };
            const next = normalizeGeneralInfo(merged, filled);
            setForm(prev => JSON.stringify(next) !== JSON.stringify(prev) ? next : prev);
        }
    }, [projectData.general_info, projectData.country, projectData.currency, projectData.unitSystem, projectData.name]);

    const [errors, setErrors] = useState(new Set());
    const [validationMsg, setValidationMsg] = useState('');

    // Sync form to context whenever it changes (updateProjectData is stable via useCallback)
    useEffect(() => {
        updateProjectData('general_info', form);
    }, [form, updateProjectData]);

    // ── Handlers ─────────────────────────────────────────────────────────────

    const handleChange = useCallback((key, value) => {
        setForm(prev => ({ ...prev, [key]: value }));

        setErrors(prev => {
            if (!prev.has(key)) return prev;
            const next = new Set(prev);
            next.delete(key);
            return next;
        });

        if (REQUIRED_KEYS.has(key)) {
            setErrors((prev) => {
                const next = new Set(prev);
                if (!value || !value.toString().trim()) next.add(key);
                else next.delete(key);
                return next;
            });
        }
        setValidationMsg('');
    }, []);

    const handleClearAll = () => {
        // Never clear locked or sor_database fields
        const skipKeys = new Set([...LOCKED_KEYS, 'sor_database']);
        const next = { ...form };
        Object.keys(INITIAL_STATE).forEach((k) => {
            if (!skipKeys.has(k)) {
                next[k] = k === 'agency_logo' ? null : '';
            }
        });
        setForm(next);
        setErrors(new Set());
        setValidationMsg('');
        controller?.engine?._log('General Info: All fields cleared.');
    };

    const handleLoadProfile = (profileName) => {
        const profiles = getProfiles();
        const profile = profiles[profileName];
        if (profile) {
            setForm(prev => ({
                ...prev,
                agency_logo: profile.agency_logo || null,
                agency_name: profile.agency_name || '',
                contact_person: profile.contact_person || '',
                agency_address: profile.agency_address || '',
                agency_country: profile.agency_country || '',
                agency_email: profile.agency_email || '',
                agency_phone: profile.agency_phone || '',
            }));
            controller?.engine?._log(`General Info: Loaded agency profile '${profileName}'.`);
        }
    };

    // ── Validation ────────────────────────────────────────────────────────────

    const validate = () => {
        const messages = validateGeneralInfoData(form);
        const newErrors = new Set(messages.length ? ['project_name'] : []);

        setErrors(newErrors);
        if (newErrors.size > 0) {
            const msg = messages.join(' ');
            setValidationMsg(msg);
            controller?.engine?._log(msg);
            return { valid: false, errors: messages };
        }

        setValidationMsg('');
        return { valid: true, errors: [] };
    };

    const hasError = (key) => errors.has(key);

    // ── Render ────────────────────────────────────────────────────────────────

    return (
        <div ref={containerRef} style={{ padding: '24px', color: 'var(--app-text-primary)' }}>

            {/* ── Project Information ──────────────────────────────────────── */}
            <SectionHeader title="Project Information" />

            <TextField
                id="project_name"
                label="Project Name"
                hint="Official name or title of the bridge/infrastructure project."
                required
                value={form.project_name}
                onChange={handleChange}
                hasError={hasError('project_name')}
            />

            <TextField
                id="project_code"
                label="Project Code"
                hint="Unique reference code assigned to this project."
                value={form.project_code}
                onChange={handleChange}
                hasError={hasError('project_code')}
            />

            <TextAreaField
                id="project_description"
                label="Project Description"
                hint="Brief description of the project scope, objectives, or background."
                value={form.project_description}
                onChange={handleChange}
                hasError={hasError('project_description')}
            />

            <TextAreaField
                id="remarks"
                label="Remarks"
                hint="Any additional notes, assumptions, or comments relevant to this evaluation."
                value={form.remarks}
                onChange={handleChange}
                hasError={hasError('remarks')}
            />

            {/* ── Assessing Organisation ────────────────────────────────────────── */}
            <SectionHeader 
                title="Assessing Organisation" 
                rightElement={
                    <Dropdown align="end">
                        <Dropdown.Toggle 
                            variant="light" 
                            size="sm" 
                            style={{ backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', border: '1px solid var(--app-border-mid)', fontSize: '0.85rem' }}
                        >
                            Load Agency Profile
                        </Dropdown.Toggle>
                        <Dropdown.Menu style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-mid)' }}>
                            {Object.keys(getProfiles()).length > 0 ? (
                                Object.keys(getProfiles()).map(name => (
                                    <Dropdown.Item 
                                        key={name} 
                                        onClick={() => handleLoadProfile(name)}
                                        style={{ color: 'var(--app-text-primary)' }}
                                        onMouseEnter={(e) => { e.target.style.backgroundColor = 'var(--app-bg-alt)' }}
                                        onMouseLeave={(e) => { e.target.style.backgroundColor = 'transparent' }}
                                    >
                                        {name}
                                    </Dropdown.Item>
                                ))
                            ) : (
                                <Dropdown.Item disabled style={{ color: 'var(--app-text-muted)' }}>
                                    No profiles found
                                </Dropdown.Item>
                            )}
                        </Dropdown.Menu>
                    </Dropdown>
                }
            />

            <TextField
                id="contact_person"
                label="Assessor's Name"
                hint="Primary contact handling this project."
                value={form.contact_person}
                onChange={handleChange}
                hasError={hasError('contact_person')}
            />

            <div className="mb-4">
                <label className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)' }}>
                    Organisation's Logo
                </label>
                <FieldHint text="Appears on the report cover page. PNG or JPG recommended." />
                <ProfileAvatar 
                    size={60} 
                    profileName={form.agency_name || 'Agency'} 
                    logoData={form.agency_logo} 
                    onLogoChange={(base64) => handleChange('agency_logo', base64)} 
                />
            </div>

            <TextField
                id="agency_name"
                label="Organisation's Name"
                hint="Name of the organization responsible for this evaluation."
                value={form.agency_name}
                onChange={handleChange}
                hasError={hasError('agency_name')}
            />

            <TextField
                id="agency_address"
                label="Organisation's Address"
                hint="Appears in the report footer."
                value={form.agency_address}
                onChange={handleChange}
                hasError={hasError('agency_address')}
            />

            <SelectField
                id="agency_country"
                label="Country"
                hint="Country where the evaluating agency is based. Used for report localisation."
                options={COUNTRIES}
                value={form.agency_country}
                onChange={handleChange}
                hasError={hasError('agency_country')}
            />

            <TextField
                id="agency_email"
                label="Email"
                hint="Official email address for correspondence."
                value={form.agency_email}
                onChange={handleChange}
                hasError={hasError('agency_email')}
            />

            <PhoneField
                id="agency_phone"
                label="Phone"
                hint="Contact phone number."
                value={form.agency_phone}
                onChange={handleChange}
                hasError={hasError('agency_phone')}
            />

            {/* ── Reviewer ────────────────────────────────────────────────────── */}
            <SectionHeader title="Reviewer" />

            <TextField
                id="reviewer_name"
                label="Reviewer's Name"
                hint=""
                value={form.reviewer_name}
                onChange={handleChange}
                hasError={hasError('reviewer_name')}
            />

            <TextField
                id="reviewer_organization"
                label="Reviewer's Organisation"
                hint=""
                value={form.reviewer_organization}
                onChange={handleChange}
                hasError={hasError('reviewer_organization')}
            />

            <TextField
                id="reviewer_address"
                label="Reviewer's Address"
                hint=""
                value={form.reviewer_address}
                onChange={handleChange}
                hasError={hasError('reviewer_address')}
            />

            <SelectField
                id="reviewer_country"
                label="Country"
                hint="Country where the reviewing agency is located."
                options={COUNTRIES}
                value={form.reviewer_country}
                onChange={handleChange}
                hasError={hasError('reviewer_country')}
            />

            <TextField
                id="reviewer_email"
                label="Email"
                hint=""
                value={form.reviewer_email}
                onChange={handleChange}
                hasError={hasError('reviewer_email')}
            />

            <PhoneField
                id="reviewer_phone"
                label="Phone"
                hint=""
                value={form.reviewer_phone}
                onChange={handleChange}
                hasError={hasError('reviewer_phone')}
            />

            {/* ── Project Settings (locked, read-only) ─────────────────────── */}
            <SectionHeader title="Project Settings" />

            <TextField
                id="project_country"
                label="Country"
                hint="Country where the bridge project is located. Set at project creation."
                value={form.project_country}
                disabled
            />

            <TextField
                id="project_currency"
                label="Currency"
                hint="Currency used for all cost figures. Set at project creation."
                value={form.project_currency}
                disabled
            />

            <TextField
                id="unit_system"
                label="Unit System"
                hint="Measurement unit system (Metric or Imperial). Set at project creation."
                value={form.unit_system}
                disabled
            />

            <SelectField
                id="sor_database"
                label="Material Suggestions"
                hint="Schedule of Rates database used to auto-suggest material names, rates, and emission factors."
                options={Object.keys(materialCatalog)}
                value={form.sor_database}
                onChange={handleChange}
                hasError={hasError('sor_database')}
            />

            {/* ── Buttons ──────────────────────────────────────────────────── */}
            <div className="d-flex gap-2 mt-4 mb-3">
                <button
                    className="btn w-100"
                    style={{ backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-secondary)', border: '1px solid var(--app-border-mid)', borderRadius: 'var(--app-radius-sm)', transition: 'all 0.2sease' }}
                    onClick={handleClearAll}
                    onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--app-border-light)'; e.currentTarget.style.color = 'var(--app-text-primary)'; e.currentTarget.style.borderColor = 'var(--app-border-dark)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'var(--app-bg-alt)'; e.currentTarget.style.color = 'var(--app-text-secondary)'; e.currentTarget.style.borderColor = 'var(--app-border-mid)'; }}
                >
                    Clear All
                </button>
            </div>

            {validationMsg && (
                <div className="alert alert-danger p-2" style={{ fontSize: '0.8rem' }} role="alert">
                    ⚠️ {validationMsg}
                </div>
            )}
        </div>
    );
};

export default ProjectInformationPlaceholder;
export { REQUIRED_KEYS, INITIAL_STATE };

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import wpiDb from '../../../data/wpi_db.json';

// ── Constants & Static Data ──────────────────────────────────────────────────

const LANE_TYPES = [
    { code: 'SL', name: 'Single Lane', width: 3.75, capacity: 435 },
    { code: 'IL', name: 'Intermediate Lane', width: 5.5, capacity: 1158 },
    { code: '2L', name: 'Two Lane (Two Way)', width: 7.0, capacity: 2400 },
    { code: '2L_1W', name: 'Two Lane (One Way)', width: 7.0, capacity: 2700 },
    { code: '3L_1W', name: 'Three Lane (One Way)', width: 10.5, capacity: 4200 },
    { code: '4L', name: 'Four Lane (Two Way)', width: 7.0, capacity: 5400 },
    { code: '6L', name: 'Six Lane (Two Way)', width: 10.5, capacity: 8400 },
    { code: '8L', name: 'Eight Lane (Two Way)', width: 14.0, capacity: 13600 },
    { code: 'EW4', name: '4 Lane Expressway (Two Way)', width: 0, capacity: 5000 },
    { code: 'EW6', name: '6 Lane Expressway (Two Way)', width: 0, capacity: 7500 },
    { code: 'EW8', name: '8 Lane Expressway (Two Way)', width: 0, capacity: 9200 },
];

const VEHICLES = [
    { key: 'small_cars', label: 'Small Car', hasPwr: false },
    { key: 'big_cars', label: 'Big Car', hasPwr: false },
    { key: 'two_wheelers', label: 'Two Wheeler', hasPwr: false },
    { key: 'o_buses', label: 'Ordinary Buses', hasPwr: false },
    { key: 'd_buses', label: 'Deluxe Buses', hasPwr: false },
    { key: 'lcv', label: 'LCV', hasPwr: false },
    { key: 'hcv', label: 'HCV', hasPwr: true, defaultPwr: 7.22 },
    { key: 'mcv', label: 'MCV', hasPwr: true, defaultPwr: 8.0 },
];

const WPI_COLUMNS = [
    { key: 'grease', label: 'Grease' },
    { key: 'property_damage', label: 'Prop. Damage' },
    { key: 'tyre_cost', label: 'Tyre Cost' },
    { key: 'spare_parts', label: 'Spare Parts' },
    { key: 'fixed_depreciation', label: 'Fixed Depr.' },
    { key: 'commodity_holding_cost', label: 'Hold. Cost' },
    { key: 'passenger_cost', label: 'Passenger' },
    { key: 'crew_cost', label: 'Crew' },
    { key: 'fatal', label: 'Fatal' },
    { key: 'major', label: 'Major' },
    { key: 'minor', label: 'Minor' },
    { key: 'vot_cost', label: 'VOT Cost' },
];

// Load WPI Database from local JSON
const WPI_DATABASE = {};
if (wpiDb && wpiDb.entries) {
    wpiDb.entries.forEach(entry => {
        WPI_DATABASE[entry.metadata.name] = {
            metadata: entry.metadata,
            data: entry.data
        };
    });
}

const INITIAL_STATE = {
    calculation_mode: 'INDIA',
    vehicles: Object.fromEntries(VEHICLES.map(v => [v.key, { vehicles_per_day: 0, accident_percentage: 0, pwr: v.defaultPwr || 0 }])),
    force_free_flow: true,
    alternate_road: {
        alternate_road_carriageway: '',
        carriage_width_in_m: 0,
        hourly_capacity: 0,
    },
    severity: {
        severity_minor: 0,
        severity_major: 0,
        severity_fatal: 0,
    },
    road_params: {
        road_roughness_mm_per_km: 2000,
        road_rise_m_per_km: 0,
        road_fall_m_per_km: 0,
        additional_reroute_distance_km: 0,
        additional_travel_time_min: 0,
        crash_rate_accidents_per_million_km: 0,
        work_zone_multiplier: 1.0,
    },
    num_peak_hours: 0,
    peak_distribution: {},
    wpi_profile: '2024',
    wpi_data: WPI_DATABASE['2024']?.data || {},
    road_user_cost_per_day: 0,
    remarks: '',
};

// ── Helper Components ────────────────────────────────────────────────────────

function SectionHeader({ title }) { return <h5 className="mb-4 fw-bold pb-2 mt-4" style={{ borderBottom: '1px solid var(--app-border-dark)', fontSize: '1rem', color: 'var(--app-text-primary)', transition: 'all 0.3s' }}>{title}</h5>; }

function Dropdown({ id, options, value, onChange, placeholder = '— Select —' }) {
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

    const select = (opt) => { onChange(opt); setOpen(false); };

    return (
        <div className="position-relative" ref={ref}>
            <button
                type="button"
                id={id}
                className="form-control d-flex align-items-center justify-content-between text-start"
                onClick={() => setOpen((o) => !o)}
                aria-haspopup="listbox"
                aria-expanded={open}
            >
                <span className={value ? '' : 'text-muted fst-italic'}>
                    {value || placeholder}
                </span>
                <span className="text-muted ms-2" style={{ fontSize: '0.75rem', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s ease' }}>▾</span>
            </button>
            {open && (
                <ul className="dropdown-menu show w-100 p-1 shadow-sm overflow-y-auto" role="listbox" style={{ maxHeight: '250px', backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-input-border)' }}>
                    <li className="dropdown-item text-muted fst-italic" style={{ cursor: 'pointer', fontSize: '0.875rem' }} onClick={() => select('')}>
                        {placeholder}
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
                                color: value === opt ? 'var(--app-primary-accent)' : 'var(--app-text-primary)'
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
    );
}

function InputField({ label, hint, value, onChange, unit, required }) {
    return (
        <div className="mb-4">
            <label className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>
                {label}{required && <span className="text-danger"> *</span>}
            </label>
            {hint && <div style={{ fontSize: '0.8rem', color: 'var(--app-text-muted)', marginBottom: '8px' }}>{hint}</div>}
            <div className="input-group">
                <input type="number" className="form-control" value={value || ''} onChange={(e) => onChange(e.target.value)} />
                {unit && <span className="input-group-text border-start-0" style={{ fontSize: '0.8rem', backgroundColor: 'var(--app-input-bg)', borderColor: 'var(--app-input-border)' }}>{unit}</span>}
            </div>
        </div>
    );
}

function RoadUserCostField({ value, onChange }) {
    return (
        <div className="mb-4">
            <label className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>Road User Cost per Day *</label>
            <div className="input-group">
                <input
                    type="number"
                    min={0}
                    step={0.01}
                    value={value || ''}
                    onChange={(e) => onChange(e.target.value)}
                    className="form-control"
                    placeholder="0.00"
                />
                <span className="input-group-text border-start-0" style={{ fontSize: '0.8rem', backgroundColor: 'var(--app-input-bg)', borderColor: 'var(--app-input-border)' }}>/ day</span>
            </div>
        </div>
    );
}

const TOOLBAR_DEFS = [
    { label: 'B', title: 'Bold', action: 'bold', style: { fontWeight: 'bold' } },
    { label: 'I', title: 'Italic', action: 'italic', style: { fontStyle: 'italic' } },
    { label: 'U', title: 'Underline', action: 'underline', style: { textDecoration: 'underline' } },
    { label: 'S', title: 'Strikethrough', action: 'strikeThrough', style: { textDecoration: 'line-through' } },
    null,
    { label: 'Left', title: 'Align Left', action: 'justifyLeft' },
    { label: 'Center', title: 'Align Center', action: 'justifyCenter' },
    { label: 'Right', title: 'Align Right', action: 'justifyRight' },
    { label: 'Justify', title: 'Justify', action: 'justifyFull' },
    null,
    { label: '• List', title: 'Bullet List', action: 'insertUnorderedList' },
    { label: '1. List', title: 'Numbered List', action: 'insertOrderedList' },
    null,
    { label: '+ Table', title: 'Insert 3×3 Table', action: 'insertTable' },
    { label: '+ Row', title: 'Insert Row Below', action: 'insertRow' },
    { label: '+ Col', title: 'Insert Column Right', action: 'insertCol' },
    { label: 'Clear', title: 'Clear Formatting', action: 'removeFormat' },
];

function RichTextEditor({ value, onChange }) {
    const editorRef = useRef(null);

    useEffect(() => {
        if (editorRef.current && editorRef.current.innerHTML !== value) {
            editorRef.current.innerHTML = value || '';
        }
    }, [value]);

    const handleInput = () => {
        onChange(editorRef.current?.innerHTML ?? '');
    };

    const handleToolbarAction = (actionName) => {
        editorRef.current?.focus();
        if (actionName === 'insertTable') {
            const rows = 3, cols = 3;
            let html = '<table border="1" style="border-collapse:collapse;width:100%">';
            for (let r = 0; r < rows; r++) {
                html += '<tr>';
                for (let c = 0; c < cols; c++) {
                    html += r === 0 ? '<th style="padding:4px 8px;background:var(--app-bg-alt)">&nbsp;</th>' : '<td style="padding:4px 8px">&nbsp;</td>';
                }
                html += '</tr>';
            }
            html += '</table><br>';
            document.execCommand('insertHTML', false, html);
            onChange(editorRef.current?.innerHTML ?? '');
        } else if (actionName === 'insertRow') {
            const sel = window.getSelection();
            if (!sel || sel.rangeCount === 0) return;
            const cell = sel.anchorNode?.parentElement?.closest('td, th');
            const row = cell?.closest('tr');
            if (!row) return;
            const colCount = row.cells.length;
            const newRow = document.createElement('tr');
            for (let i = 0; i < colCount; i++) {
                const td = document.createElement('td');
                td.style.padding = '4px 8px';
                td.innerHTML = '&nbsp;';
                newRow.appendChild(td);
            }
            row.parentElement.insertBefore(newRow, row.nextSibling);
            onChange(editorRef.current?.innerHTML ?? '');
        } else if (actionName === 'insertCol') {
            const sel = window.getSelection();
            if (!sel || sel.rangeCount === 0) return;
            const cell = sel.anchorNode?.parentElement?.closest('td, th');
            const row = cell?.closest('tr');
            const table = row?.closest('table');
            if (!table) return;
            const cellIndex = cell ? Array.from(row.cells).indexOf(cell) + 1 : -1;
            Array.from(table.rows).forEach((tr, rowIdx) => {
                const newCell = rowIdx === 0 ? document.createElement('th') : document.createElement('td');
                newCell.style.padding = '4px 8px';
                if (rowIdx === 0) newCell.style.background = 'var(--app-bg-alt)';
                newCell.innerHTML = '&nbsp;';
                if (cellIndex >= 0 && cellIndex < tr.cells.length) {
                    tr.insertBefore(newCell, tr.cells[cellIndex]);
                } else {
                    tr.appendChild(newCell);
                }
            });
            onChange(editorRef.current?.innerHTML ?? '');
        } else {
            document.execCommand(actionName, false, null);
        }
    };

    return (
        <div className="mb-4">
            <label className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>Remarks / Notes</label>
            <div className="border rounded" style={{ borderColor: 'var(--app-input-border)', backgroundColor: 'var(--app-input-bg)' }}>
                <div className="d-flex flex-wrap align-items-center gap-1 p-2 border-bottom" style={{ borderColor: 'var(--app-input-border)', backgroundColor: 'var(--app-bg-alt)' }}>
                    {TOOLBAR_DEFS.map((btn, i) =>
                        btn === null ? <div key={`div-${i}`} style={{ width: '1px', height: '16px', backgroundColor: 'var(--app-border-mid)', margin: '0 4px' }} /> : (
                            <button key={btn.label} type="button" title={btn.title} className="btn btn-sm border-0 px-2 py-1" style={{ ...btn.style, fontSize: '0.8rem', backgroundColor: 'transparent' }} onMouseDown={(e) => { e.preventDefault(); handleToolbarAction(btn.action); }}>{btn.label}</button>
                        )
                    )}
                </div>
                <div ref={editorRef} className="p-2" style={{ minHeight: '120px', color: 'var(--app-text-primary)' }} contentEditable suppressContentEditableWarning data-placeholder="Add notes or remarks here..." onInput={handleInput} />
            </div>
        </div>
    );
}

// ── Main Component ──────────────────────────────────────────────────────────

const TrafficData = ({ controller }) => {
    const { projectData, updateProjectData } = useProjectData();
    const [form, setForm] = useState(() => {
        const saved = projectData.traffic_data;
        return (saved && Object.keys(saved).length > 0) ? { ...INITIAL_STATE, ...saved } : INITIAL_STATE;
    });

    const [errors, setErrors] = useState(new Set());
    const [validationMsg, setValidationMsg] = useState('');
    const [showSaveAs, setShowSaveAs] = useState(false);
    const [saveAsForm, setSaveAsForm] = useState({ name: '', year: '2024', remark: '' });
    const [showInfoModal, setShowInfoModal] = useState(false);
    const [infoMessage, setInfoMessage] = useState('');
    const [showImportModal, setShowImportModal] = useState(false);
    const [importSelected, setImportSelected] = useState('');
    const libraryProfiles = JSON.parse(localStorage.getItem('my_wpi_library') || '{}');
    const [localCustomProfiles, setLocalCustomProfiles] = useState({});

    useEffect(() => {
        updateProjectData('traffic_data', form);
    }, [form, updateProjectData]);

    const handleModeChange = (val) => setForm(prev => ({ ...prev, calculation_mode: val }));
    const handleCostChange = (val) => setForm(prev => ({ ...prev, road_user_cost_per_day: val }));
    const handleRemarksChange = (html) => setForm(prev => ({ ...prev, remarks: html }));

    const handleClearAll = () => {
        setForm(INITIAL_STATE);
        setErrors(new Set());
        setValidationMsg('');
    };

    const handleWpiProfileChange = (profileName) => {
        let newData = {};
        if (WPI_DATABASE[profileName]) newData = WPI_DATABASE[profileName].data;
        else if (localCustomProfiles[profileName]) newData = localCustomProfiles[profileName].data;
        else if (libraryProfiles[profileName]) newData = libraryProfiles[profileName].data;
        setForm(prev => ({ ...prev, wpi_profile: profileName, wpi_data: newData }));
    };

    const handleWpiCellChange = (vehicleKey, colKey, val) => {
        setForm(prev => {
            const nextWpi = { ...prev.wpi_data };
            if (!nextWpi[vehicleKey]) nextWpi[vehicleKey] = {};
            nextWpi[vehicleKey][colKey] = Number(val);
            return { ...prev, wpi_data: nextWpi };
        });
    };

    const handleNewWpi = () => {
        const emptyData = Object.fromEntries(VEHICLES.map(v => [v.key, Object.fromEntries(WPI_COLUMNS.map(c => [c.key, 0]))]));
        const newName = 'Custom (New)';
        setLocalCustomProfiles(prev => ({ ...prev, [newName]: { metadata: { name: newName, year: new Date().getFullYear(), remark: 'New custom profile' }, data: emptyData } }));
        setForm(prev => ({ ...prev, wpi_profile: newName, wpi_data: emptyData }));
    };

    const handleSaveAsSubmit = () => {
        if (!saveAsForm.name) return;
        const newProfile = { metadata: { name: saveAsForm.name, year: saveAsForm.year, remark: saveAsForm.remark }, data: form.wpi_data };
        setLocalCustomProfiles(prev => ({ ...prev, [saveAsForm.name]: newProfile }));
        setForm(prev => ({ ...prev, wpi_profile: saveAsForm.name }));
        setShowSaveAs(false);
    };

    const handleDeleteWpi = () => {
        if (WPI_DATABASE[form.wpi_profile]) return alert("Cannot delete official profiles.");
        if (window.confirm(`Delete profile "${form.wpi_profile}"?`)) {
            const nextCustom = { ...localCustomProfiles };
            delete nextCustom[form.wpi_profile];
            setLocalCustomProfiles(nextCustom);
            handleWpiProfileChange("2024");
        }
    };

    const handleSaveToLibrary = () => {
        const currentData = { metadata: { name: form.wpi_profile, year: new Date().getFullYear(), remark: 'Saved from project' }, data: form.wpi_data };
        localStorage.setItem('my_wpi_library', JSON.stringify({ ...libraryProfiles, [form.wpi_profile]: currentData }));
        setInfoMessage(`'${form.wpi_profile}' saved to library.`);
        setShowInfoModal(true);
    };

    const handleImportSubmit = () => {
        if (importSelected && libraryProfiles[importSelected]) {
            setLocalCustomProfiles(prev => ({ ...prev, [importSelected]: libraryProfiles[importSelected] }));
            setForm(prev => ({ ...prev, wpi_profile: importSelected, wpi_data: libraryProfiles[importSelected].data }));
            setShowImportModal(false);
        }
    };

    const handleRemoveFromLibrary = () => {
        if (importSelected && window.confirm(`Remove '${importSelected}'?`)) {
            const lib = { ...libraryProfiles };
            delete lib[importSelected];
            localStorage.setItem('my_wpi_library', JSON.stringify(lib));
            setImportSelected('');
        }
    };

    const validate = () => {
        if (!form.calculation_mode) {
            setValidationMsg("Calculation mode is required.");
            return false;
        }
        setValidationMsg('');
        return true;
    };

    const renderIndiaMode = () => (
        <div className="d-flex flex-column gap-2">
            <SectionHeader title="Vehicle Traffic Data" />
            <div className="table-responsive mb-4">
                <table className="table table-bordered table-sm text-center align-middle" style={{ backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-mid)', marginBottom: 0 }}>
                    <thead><tr><th style={{ width: '30%', backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px' }}>Vehicle Type</th><th style={{ backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px' }}>Vehicles / Day</th><th style={{ backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px' }}>Accident %</th><th style={{ backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px' }}>PWR</th></tr></thead>
                    <tbody>
                        {VEHICLES.map(v => (
                            <tr key={v.key}>
                                <td className="text-start ps-3 fw-bold">{v.label}</td>
                                <td className="p-0"><input type="number" className="form-control text-end px-2 py-1" style={{ width: '100%', border: 'none', backgroundColor: 'var(--app-input-bg)', color: 'var(--app-text-primary)', height: '36px', outline: 'none' }} onFocus={e => e.target.style.backgroundColor = 'var(--app-bg-alt)'} onBlur={e => e.target.style.backgroundColor = 'var(--app-input-bg)'} value={form.vehicles[v.key]?.vehicles_per_day || 0} onChange={(e) => {
                                    const nextVehicles = { ...form.vehicles, [v.key]: { ...form.vehicles[v.key], vehicles_per_day: Number(e.target.value) } };
                                    setForm(prev => ({ ...prev, vehicles: nextVehicles }));
                                }} /></td>
                                <td className="p-0"><input type="number" step="0.01" className="form-control text-end px-2 py-1" style={{ width: '100%', border: 'none', backgroundColor: 'var(--app-input-bg)', color: 'var(--app-text-primary)', height: '36px', outline: 'none' }} onFocus={e => e.target.style.backgroundColor = 'var(--app-bg-alt)'} onBlur={e => e.target.style.backgroundColor = 'var(--app-input-bg)'} value={(form.vehicles[v.key]?.accident_percentage || 0).toFixed(2)} onChange={(e) => {
                                    const nextVehicles = { ...form.vehicles, [v.key]: { ...form.vehicles[v.key], accident_percentage: Number(e.target.value) } };
                                    setForm(prev => ({ ...prev, vehicles: nextVehicles }));
                                }} /></td>
                                <td className="p-0">{v.hasPwr ? <input type="number" step="0.01" className="form-control text-end px-2 py-1" style={{ width: '100%', border: 'none', backgroundColor: 'var(--app-input-bg)', color: 'var(--app-text-primary)', height: '36px', outline: 'none' }} onFocus={e => e.target.style.backgroundColor = 'var(--app-bg-alt)'} onBlur={e => e.target.style.backgroundColor = 'var(--app-input-bg)'} value={(form.vehicles[v.key]?.pwr || 0).toFixed(2)} onChange={(e) => {
                                    const nextVehicles = { ...form.vehicles, [v.key]: { ...form.vehicles[v.key], pwr: Number(e.target.value) } };
                                    setForm(prev => ({ ...prev, vehicles: nextVehicles }));
                                }} /> : <div className="text-muted">-</div>}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="mb-4 d-flex align-items-center gap-3">
                <input type="checkbox" id="force_free_flow" className="form-check-input m-0" style={{ width: '18px', height: '18px', cursor: 'pointer', accentColor: 'var(--app-primary-accent)' }} checked={form.force_free_flow} onChange={(e) => setForm(prev => ({ ...prev, force_free_flow: e.target.checked }))} />
                <label htmlFor="force_free_flow" className="mb-0 fw-bold small" style={{ cursor: 'pointer' }}>Force free-flow conditions off-peak</label>
            </div>

            <SectionHeader title="Alternate Road Configuration" />
            <div className="mb-4">
                <label className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>Alternate Road Carriageway *</label>
                <div style={{ fontSize: '0.8rem', color: 'var(--app-text-muted)', marginBottom: '8px' }}>Lane configuration of the alternate route.</div>
                <select className="form-select" value={form.alternate_road.alternate_road_carriageway} onChange={(e) => {
                    const lane = LANE_TYPES.find(l => l.name === e.target.value);
                    setForm(prev => ({ ...prev, alternate_road: { alternate_road_carriageway: e.target.value, carriage_width_in_m: lane ? lane.width : 0, hourly_capacity: lane ? lane.capacity : 0 } }));
                }}><option value="">- Select -</option>{LANE_TYPES.map(l => <option key={l.code} value={l.name}>{l.name}</option>)}</select>
            </div>
            <InputField label="Carriageway Width" unit="(m)" required value={form.alternate_road.carriage_width_in_m} onChange={(v) => setForm(prev => ({ ...prev, alternate_road: { ...prev.alternate_road, carriage_width_in_m: Number(v) } }))} />
            <InputField label="Hourly Capacity" unit="(veh/hr)" required value={form.alternate_road.hourly_capacity} onChange={(v) => setForm(prev => ({ ...prev, alternate_road: { ...prev.alternate_road, hourly_capacity: Number(v) } }))} />

            <SectionHeader title="Accident Severity Distribution" />
            <InputField label="Minor Injury" unit="(%)" value={form.severity.severity_minor} onChange={(v) => {
                const num = Number(v);
                let next = { ...form.severity, severity_minor: num };
                next.severity_major = Math.min(100 - num, next.severity_major);
                next.severity_fatal = 100 - num - next.severity_major;
                setForm(prev => ({ ...prev, severity: next }));
            }} />
            <InputField label="Major Injury" unit="(%)" value={form.severity.severity_major} onChange={(v) => {
                const num = Number(v);
                let next = { ...form.severity, severity_major: num };
                next.severity_minor = Math.min(100 - num, next.severity_minor);
                next.severity_fatal = 100 - num - next.severity_minor;
                setForm(prev => ({ ...prev, severity: next }));
            }} />
            <InputField label="Fatal Accident" unit="(%)" value={form.severity.severity_fatal} onChange={(v) => {
                const num = Number(v);
                let next = { ...form.severity, severity_fatal: num };
                next.severity_minor = Math.min(100 - num, next.severity_minor);
                next.severity_major = 100 - num - next.severity_minor;
                setForm(prev => ({ ...prev, severity: next }));
            }} />

            <SectionHeader title="Road Parameters" />
            <InputField label="Road Roughness" unit="(mm/km)" value={form.road_params.road_roughness_mm_per_km} onChange={(v) => setForm(prev => ({ ...prev, road_params: { ...prev.road_params, road_roughness_mm_per_km: Number(v) } }))} />
            <InputField label="Road Rise" unit="(m/km)" required value={form.road_params.road_rise_m_per_km} onChange={(v) => setForm(prev => ({ ...prev, road_params: { ...prev.road_params, road_rise_m_per_km: Number(v) } }))} />
            <InputField label="Road Fall" unit="(m/km)" required value={form.road_params.road_fall_m_per_km} onChange={(v) => setForm(prev => ({ ...prev, road_params: { ...prev.road_params, road_fall_m_per_km: Number(v) } }))} />
            <InputField label="Additional Reroute Distance" unit="(km)" value={form.road_params.additional_reroute_distance_km} onChange={(v) => setForm(prev => ({ ...prev, road_params: { ...prev.road_params, additional_reroute_distance_km: Number(v) } }))} />
            <InputField label="Additional Travel Time" unit="(min)" value={form.road_params.additional_travel_time_min} onChange={(v) => setForm(prev => ({ ...prev, road_params: { ...prev.road_params, additional_travel_time_min: Number(v) } }))} />
            <InputField label="Crash Rate" unit="(acc / M km)" required value={form.road_params.crash_rate_accidents_per_million_km} onChange={(v) => setForm(prev => ({ ...prev, road_params: { ...prev.road_params, crash_rate_accidents_per_million_km: Number(v) } }))} />

            <SectionHeader title="Traffic Flow" />
            <InputField label="Number of Peak Hours" required value={form.num_peak_hours} onChange={(v) => {
                const count = Math.min(24, Math.max(0, Number(v)));
                const nextDist = { ...form.peak_distribution };
                for (let i = 1; i <= count; i++) if (!nextDist[`peak_hour_${i}`]) nextDist[`peak_hour_${i}`] = 0.04;
                setForm(prev => ({ ...prev, num_peak_hours: count, peak_distribution: nextDist }));
            }} />

            <div className="mb-4">
                <div className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>Peak Hour Distribution</div>
                <div className="table-responsive">
                    <table className="table table-bordered table-sm text-center align-middle" style={{ backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-mid)', marginBottom: 0 }}>
                        <thead><tr><th style={{ width: '60%', backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px' }}>Hour Category</th><th style={{ backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px' }}>Traffic Proportion (%)</th></tr></thead>
                        <tbody>
                            {[...Array(form.num_peak_hours || 1)].map((_, i) => (
                                <tr key={i}><td className="text-start ps-3 fw-bold">{form.num_peak_hours > 0 ? `Peak Hour ${i + 1}` : 'Peak Hour 1'}</td><td className="p-0">
                                    <input type="number" step="0.01" className="form-control text-end px-2 py-1" style={{ width: '100%', border: 'none', backgroundColor: 'var(--app-input-bg)', color: 'var(--app-text-primary)', height: '36px', outline: 'none' }} onFocus={e => e.target.style.backgroundColor = 'var(--app-bg-alt)'} onBlur={e => e.target.style.backgroundColor = 'var(--app-input-bg)'} value={((form.peak_distribution[`peak_hour_${i + 1}`] || 0.04) * 100).toFixed(2)} onChange={(e) => setForm(prev => ({ ...prev, peak_distribution: { ...prev.peak_distribution, [`peak_hour_${i + 1}`]: Number(e.target.value) / 100 } }))} /></td></tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            <SectionHeader title="WPI Adjustment Factors" />
            <div className="d-flex flex-wrap gap-2 mb-3 align-items-center">
                <label className="fw-bold mb-0" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>WPI Profile:</label>
                <select className="form-select w-auto" value={form.wpi_profile} onChange={(e) => handleWpiProfileChange(e.target.value)}>
                    {Object.keys(WPI_DATABASE).map(y => <option key={y} value={y}>{y}</option>)}
                    {Object.keys(localCustomProfiles).map(p => <option key={p} value={p}>{p}</option>)}
                </select>
                <div className="btn-group btn-group-sm">
                    <button className="btn btn-outline-secondary" onClick={handleNewWpi}>+ New</button>
                    <button className="btn btn-outline-secondary" onClick={() => setShowSaveAs(true)}>Save As</button>
                </div>
                <div className="ms-auto d-flex gap-2">
                    <button className="btn btn-sm btn-outline-primary" onClick={handleSaveToLibrary}>Save to Library</button>
                    <button className="btn btn-sm btn-outline-primary" onClick={() => setShowImportModal(true)}>Import</button>
                </div>
            </div>

            <div className="table-responsive mb-4" style={{ maxHeight: '500px', overflow: 'auto', border: '1px solid var(--app-border-mid)', borderRadius: '4px' }}>
                <table className="table table-bordered table-sm text-center align-middle" style={{ backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-mid)', marginBottom: 0 }}>
                    <thead>
                        <tr><th rowSpan="2" className="text-start ps-2 border-end-0" style={{ position: 'sticky', top: 0, zIndex: 2, backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px', minWidth: '130px' }}></th><th colSpan="4" style={{ position: 'sticky', top: 0, zIndex: 2, backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px', whiteSpace: 'nowrap' }}>Vehicle Cost</th><th colSpan="1" style={{ position: 'sticky', top: 0, zIndex: 2, backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px', whiteSpace: 'nowrap' }}>Commodity</th><th colSpan="2" style={{ position: 'sticky', top: 0, zIndex: 2, backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px', whiteSpace: 'nowrap' }}>Pass. & Crew</th><th colSpan="3" style={{ position: 'sticky', top: 0, zIndex: 2, backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px', whiteSpace: 'nowrap' }}>Medical Cost</th><th colSpan="1" style={{ position: 'sticky', top: 0, zIndex: 2, backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px', whiteSpace: 'nowrap' }}>VOT Cost</th></tr>
                        <tr>{WPI_COLUMNS.map(col => <th key={col.key} style={{ position: 'sticky', top: 0, zIndex: 2, backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px', whiteSpace: 'nowrap', minWidth: '120px' }}>{col.label}</th>)}</tr>
                    </thead>
                    <tbody>
                        {['Common', ...VEHICLES.map(v => v.label)].map((rowLabel, rIdx) => {
                            const vKey = rIdx === 0 ? 'small_cars' : VEHICLES[rIdx - 1].key;
                            return (
                                <tr key={rowLabel}><td className="fw-bold text-start ps-3" style={{ whiteSpace: 'nowrap' }}>{rowLabel}</td>
                                    {WPI_COLUMNS.map(col => (
                                        <td key={col.key} className="p-0">
                                            <input type="number" step="0.0001" className="form-control form-control-sm text-end px-1 py-1" style={{ width: '100%', minWidth: '120px', border: 'none', backgroundColor: 'var(--app-input-bg)', color: 'var(--app-text-primary)', height: '36px', outline: 'none' }} onFocus={e => e.target.style.backgroundColor = 'var(--app-bg-alt)'} onBlur={e => e.target.style.backgroundColor = 'var(--app-input-bg)'} value={(form.wpi_data?.[vKey]?.[col.key] || 0).toFixed(4)} onChange={(e) => handleWpiCellChange(vKey, col.key, e.target.value)} />
                                        </td>
                                    ))}
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </div>
    );

    return (
        <div style={{ padding: '24px', color: 'var(--app-text-primary)', maxWidth: '1400px', animation: 'fadeIn 0.4s ease-out', backgroundColor: 'var(--app-bg-main)' }}>
            <div className="mb-4"><label className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>Calculation Mode</label>
                <select className="form-select" style={{ maxWidth: '300px' }} value={form.calculation_mode} onChange={(e) => handleModeChange(e.target.value)}>
                    <option value="INDIA">INDIA</option><option value="GLOBAL">GLOBAL</option>
                </select>
            </div>
            {form.calculation_mode === 'INDIA' ? renderIndiaMode() : (
                <div className="d-flex flex-column gap-2"><SectionHeader title="Global Parameters" />
                    <RoadUserCostField value={form.road_user_cost_per_day} onChange={handleCostChange} />
                </div>
            )}
            <RichTextEditor value={form.remarks} onChange={handleRemarksChange} />
            <div className="d-flex gap-3 mt-5 pb-5">
                <button
                    className="btn flex-grow-1 py-3 fw-bold"
                    style={{ backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-secondary)', border: '1px solid var(--app-border-mid)', borderRadius: '8px', transition: 'all 0.2s' }}
                    onClick={handleClearAll}
                    onMouseEnter={(e) => { e.target.style.backgroundColor = 'var(--app-border-light)'; e.target.style.color = 'var(--app-text-primary)'; }}
                    onMouseLeave={(e) => { e.target.style.backgroundColor = 'var(--app-bg-alt)'; e.target.style.color = 'var(--app-text-secondary)'; }}
                >
                    Clear All
                </button>
                <button
                    className="btn py-3 fw-bold px-5"
                    style={{ backgroundColor: 'var(--app-primary-accent)', color: 'var(--app-btn-primary-text)', border: 'none', borderRadius: '8px', transition: 'all 0.2s' }}
                    onClick={() => validate()}
                    onMouseEnter={(e) => { e.target.style.opacity = '0.9'; e.target.style.transform = 'translateY(-1px)'; }}
                    onMouseLeave={(e) => { e.target.style.opacity = '1'; e.target.style.transform = 'none'; }}
                >
                    Validate this page
                </button>
            </div>

            {/* Custom Modals */}
            {showSaveAs && (
                <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0, 0, 0, 0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
                    <div style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-mid)', borderRadius: '8px', width: '400px', color: 'var(--app-text-primary)', boxShadow: '0 10px 25px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
                        <div style={{ backgroundColor: 'var(--app-bg-alt)', padding: '12px 16px', borderBottom: '1px solid var(--app-border-mid)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <h6 className="m-0 fw-bold d-flex align-items-center gap-2">Save Profile As</h6>
                            <button style={{ background: 'transparent', border: 'none', color: 'var(--app-text-muted)', fontSize: '1.2rem', cursor: 'pointer' }} onMouseEnter={e => e.target.style.color = 'var(--app-text-primary)'} onMouseLeave={e => e.target.style.color = 'var(--app-text-muted)'} onClick={() => setShowSaveAs(false)}>×</button>
                        </div>
                        <div style={{ padding: '20px' }}>
                            <div className="mb-3">
                                <label className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>Profile Name</label>
                                <input type="text" className="form-control" value={saveAsForm.name} onChange={e => setSaveAsForm({...saveAsForm, name: e.target.value})} />
                            </div>
                        </div>
                        <div style={{ padding: '16px', display: 'flex', justifyContent: 'flex-end', borderTop: 'none', backgroundColor: 'var(--app-bg-card)', gap: '8px' }}>
                            <button className="btn" style={{ borderColor: 'transparent', color: 'var(--app-text-primary)', backgroundColor: 'transparent' }} onMouseEnter={e => e.target.style.backgroundColor = 'rgba(255,255,255,0.1)'} onMouseLeave={e => e.target.style.backgroundColor = 'transparent'} onClick={() => setShowSaveAs(false)}>Cancel</button>
                            <button className="btn" style={{ backgroundColor: 'var(--app-primary-accent)', borderColor: 'var(--app-primary-accent)', color: 'var(--app-btn-primary-text)', borderRadius: '6px', padding: '6px 20px' }} onMouseEnter={e => e.target.style.filter = 'brightness(0.9)'} onMouseLeave={e => e.target.style.filter = 'none'} onClick={handleSaveAsSubmit}>OK</button>
                        </div>
                    </div>
                </div>
            )}

            {showInfoModal && (
                <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0, 0, 0, 0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
                    <div style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-mid)', borderRadius: '8px', width: '400px', color: 'var(--app-text-primary)', boxShadow: '0 10px 25px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
                        <div style={{ backgroundColor: 'var(--app-bg-alt)', padding: '12px 16px', borderBottom: '1px solid var(--app-border-mid)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><h6>Info</h6><button style={{ background: 'transparent', border: 'none', color: 'var(--app-text-muted)', fontSize: '1.2rem', cursor: 'pointer' }} onMouseEnter={e => e.target.style.color = 'var(--app-text-primary)'} onMouseLeave={e => e.target.style.color = 'var(--app-text-muted)'} onClick={() => setShowInfoModal(false)}>×</button></div>
                        <div style={{ padding: '20px' }}>{infoMessage}</div>
                        <div style={{ padding: '16px', display: 'flex', justifyContent: 'flex-end', borderTop: 'none', backgroundColor: 'var(--app-bg-card)', gap: '8px' }}><button className="btn" style={{ backgroundColor: 'var(--app-primary-accent)', borderColor: 'var(--app-primary-accent)', color: 'var(--app-btn-primary-text)', borderRadius: '6px', padding: '6px 20px' }} onMouseEnter={e => e.target.style.filter = 'brightness(0.9)'} onMouseLeave={e => e.target.style.filter = 'none'} onClick={() => setShowInfoModal(false)}>OK</button></div>
                    </div>
                </div>
            )}

            {showImportModal && (
                <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0, 0, 0, 0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
                    <div style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-mid)', borderRadius: '8px', width: '400px', color: 'var(--app-text-primary)', boxShadow: '0 10px 25px rgba(0,0,0,0.5)', overflow: 'hidden' }}>
                        <div style={{ backgroundColor: 'var(--app-bg-alt)', padding: '12px 16px', borderBottom: '1px solid var(--app-border-mid)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}><h6>Import from Library</h6><button style={{ background: 'transparent', border: 'none', color: 'var(--app-text-muted)', fontSize: '1.2rem', cursor: 'pointer' }} onMouseEnter={e => e.target.style.color = 'var(--app-text-primary)'} onMouseLeave={e => e.target.style.color = 'var(--app-text-muted)'} onClick={() => setShowImportModal(false)}>×</button></div>
                        <div style={{ padding: '20px' }}>
                            <select className="form-select" value={importSelected} onChange={e => setImportSelected(e.target.value)}>
                                <option value="">- Select Profile -</option>
                                {Object.keys(libraryProfiles).map(k => <option key={k} value={k}>{k}</option>)}
                            </select>
                        </div>
                        <div style={{ padding: '16px', display: 'flex', justifyContent: 'flex-end', borderTop: 'none', backgroundColor: 'var(--app-bg-card)', gap: '8px' }}>
                            <button className="btn" style={{ backgroundColor: 'var(--app-primary-accent)', borderColor: 'var(--app-primary-accent)', color: 'var(--app-btn-primary-text)', borderRadius: '6px', padding: '6px 20px' }} onMouseEnter={e => e.target.style.filter = 'brightness(0.9)'} onMouseLeave={e => e.target.style.filter = 'none'} onClick={handleImportSubmit}>Import</button>
                        </div>
                    </div>
                </div>
            )}

            {validationMsg && (
                <div className="alert alert-danger p-2 mt-3" style={{ fontSize: '0.8rem' }} role="alert">⚠️ {validationMsg}</div>
            )}
          <style>{`\n@keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }\n`}</style>
        </div>
    );
};

export default TrafficData;
export { INITIAL_STATE };
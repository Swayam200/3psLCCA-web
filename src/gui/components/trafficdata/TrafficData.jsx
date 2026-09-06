import { useState, useEffect, useRef } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import { normalizeTrafficData, validateTrafficData } from '../../../utils/projectPageSchema';
import wpiDb from '../../../data/wpi_db.json';
import HelpModal from '../HelpModal';

// ── Constants & Static Data ──────────────────────────────────────────────────

const LANE_TYPES = [
    { code: 'SL', name: 'Single Lane', width: 3.75, capacity: 435 },
    { code: 'IL', name: 'Intermediate Lane', width: 5.5, capacity: 1158 },
    { code: '2L', name: 'Two Lane', width: 7.0, capacity: 1200 },
    { code: '4L', name: 'Four Lane', width: 14.0, capacity: 2900 },
    { code: '6L', name: 'Six Lane', width: 21.0, capacity: 4300 },
    { code: '8L', name: 'Eight Lane', width: 28.0, capacity: 7200 },
    { code: 'EW8', name: 'Expressway', width: 0, capacity: 9200 },
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
    { key: 'petrol', label: 'Petrol Cost', group: 'Fuel Cost (INR)' },
    { key: 'diesel', label: 'Diesel Cost', group: 'Fuel Cost (INR)' },
    { key: 'engine_oil', label: 'Engine Oil Cost', group: 'Fuel Cost (INR)' },
    { key: 'other_oil', label: 'Other Oil Cost', group: 'Fuel Cost (INR)' },
    { key: 'grease', label: 'Grease Cost', group: 'Fuel Cost (INR)' },
    { key: 'property_damage', label: 'Property Damage Cost', group: 'Vehicle Cost (INR)' },
    { key: 'tyre_cost', label: 'Tyre Cost', group: 'Vehicle Cost (INR)' },
    { key: 'spare_parts', label: 'Spare Parts Cost', group: 'Vehicle Cost (INR)' },
    { key: 'fixed_depreciation', label: 'Fixed Depreciation', group: 'Vehicle Cost (INR)' },
    { key: 'commodity_holding_cost', label: 'Commodity Holding Cost', group: 'Commodity Cost (INR)' },
    { key: 'passenger_cost', label: 'Passenger Cost', group: 'Passenger and Crew Cost (INR)' },
    { key: 'crew_cost', label: 'Crew Cost', group: 'Passenger and Crew Cost (INR)' },
    { key: 'fatal', label: 'Fatal Injury Cost', group: 'Medical Cost (INR)' },
    { key: 'major', label: 'Major Injury Cost', group: 'Medical Cost (INR)' },
    { key: 'minor', label: 'Minor Injury Cost', group: 'Medical Cost (INR)' },
    { key: 'vot_cost', label: 'Value of Time Cost', group: 'Value of Time Cost (INR)' },
];

const WPI_GROUPS = [
    { label: 'Fuel Cost (INR)', span: 5 },
    { label: 'Vehicle Cost (INR)', span: 4 },
    { label: 'Commodity Cost (INR)', span: 1 },
    { label: 'Passenger and Crew Cost (INR)', span: 2 },
    { label: 'Medical Cost (INR)', span: 3 },
    { label: 'Value of Time Cost (INR)', span: 1 },
];

// The WPI table is wider than any viewport and taller than the fold, so it
// lives in a fixed-size shell that scrolls both ways internally while the
// group header, column header, Common-to-All row, and vehicle-name column
// all stay pinned. Deterministic header heights (42 + 66 → pin at 108) are
// what keep the sticky offsets honest — the previous hardcoded 49px drifted
// from the real row height and left a broken hollow band. border-collapse
// must be `separate`: collapsed borders detach from sticky cells on scroll.
const WPI_TABLE_CSS = `
.wpi-table-shell { max-height: 560px; overflow: auto; border: 1px solid var(--app-border-mid); border-radius: 4px; }
.wpi-sticky-table { border-collapse: separate; border-spacing: 0; table-layout: fixed; min-width: 1900px; background: var(--app-bg-card); color: var(--app-text-primary); font-size: 0.85rem; margin: 0; }
.wpi-sticky-table th, .wpi-sticky-table td { border-right: 1px solid var(--app-border-mid); border-bottom: 1px solid var(--app-border-mid); }
.wpi-sticky-table thead th { background: var(--app-bg-alt); color: var(--app-text-primary); text-align: center; vertical-align: middle; }
.wpi-corner { position: sticky; left: 0; top: 0; z-index: 6; width: 150px; min-width: 150px; background: var(--app-bg-alt); }
.wpi-group { position: sticky; top: 0; z-index: 3; height: 42px; font-weight: 600; padding: 4px 8px; white-space: nowrap; }
.wpi-col { position: sticky; top: 42px; z-index: 3; height: 66px; width: 108px; font-weight: 500; padding: 4px 6px; font-size: 0.8rem; line-height: 1.25; overflow: hidden; }
.wpi-rowlabel { position: sticky; left: 0; z-index: 2; width: 150px; min-width: 150px; background: var(--app-bg-card); font-weight: 700; text-align: left; padding: 6px 6px 6px 12px; white-space: nowrap; vertical-align: middle; }
.wpi-pin td { position: sticky; top: 108px; z-index: 2; background: var(--app-bg-alt); }
.wpi-pin td.wpi-rowlabel { z-index: 4; background: var(--app-bg-alt); }
.wpi-value { text-align: right; padding: 7px 12px; color: var(--app-text-secondary); font-variant-numeric: tabular-nums; }
.wpi-check { display: flex; align-items: center; justify-content: center; height: 34px; }
.wpi-sticky-table input.form-control { min-width: 108px; }
`;

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

const cloneData = (value) => JSON.parse(JSON.stringify(value));
const emptyWpiData = () => Object.fromEntries(
    VEHICLES.map(({ key }) => [
        key,
        Object.fromEntries(WPI_COLUMNS.map(({ key: columnKey }) => [columnKey, 1])),
    ]),
);
const normalizeWpiMatrix = (value) => {
    const data = emptyWpiData();
    VEHICLES.forEach(({ key: vehicleKey }) => {
        WPI_COLUMNS.forEach(({ key: columnKey }) => {
            const valueAtCell = Number(value?.[vehicleKey]?.[columnKey]);
            if (Number.isFinite(valueAtCell)) data[vehicleKey][columnKey] = valueAtCell;
        });
    });
    return data;
};
const officialWpiProfile = (name) => WPI_DATABASE[name];
const getWpiValue = (data, vehicleKey, columnKey) => Number(data?.[vehicleKey]?.[columnKey] ?? 0);
const deriveCommonState = (data) => Object.fromEntries(
    WPI_COLUMNS.map(({ key }) => {
        const values = VEHICLES.map(({ key: vehicleKey }) => getWpiValue(data, vehicleKey, key));
        return [key, values.every((value) => Math.abs(value - values[0]) < 1e-9)];
    }),
);
const computeWpiRatio = (selected, base) => Object.fromEntries(
    VEHICLES.map(({ key: vehicleKey }) => [
        vehicleKey,
        Object.fromEntries(WPI_COLUMNS.map(({ key: columnKey }) => {
            const baseValue = getWpiValue(base, vehicleKey, columnKey);
            return [columnKey, baseValue > 0 ? getWpiValue(selected, vehicleKey, columnKey) / baseValue : 1];
        })),
    ]),
);

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
    wpi_profile: '2019',
    wpi_data: WPI_DATABASE['2019']?.data || {},
    road_user_cost_per_day: 0,
    remarks: '',
};

// ── Helper Components ────────────────────────────────────────────────────────

const FIELD_INFO = {
    minor_injury: {
        title: 'Minor Injury',
        message: 'A minor injury can be defined as a non-fatal, non-permanent injury requiring minimal medical intervention or resulting in temporary/short-term loss of working time. It covers a wide range of non-emergency events such as cuts, wounds, bruises, swelling, and more. These injuries are generally defined as physical harms that are not life-threatening, do not cause permanent disability, and do not require extensive hospitalization or surgical interventions. They are typically treatable with first aid or primary care and generally allow for full recovery within a short period, often within a few days or weeks.',
    },
    major_injury: {
        title: 'Major Injury',
        message: 'A major injury can be defined as grievous hurt or dangerous injury which poses an immediate or potential threat to life, causes severe bodily pain, or results in permanent impairment of body function. These injuries endanger life such as severe head trauma, internal organ damage, or extensive hemorrhage necessitating urgent hospital care, resuscitation, or surgical intervention. The recovery period typically ranges from 3 to 24 months.',
    },
    fatal_accident: {
        title: 'Fatal Accident',
        message: 'A fatal accident can be defined as an unforeseen, unexpected, and undesirable event, such as a trauma or a collision, which results in the direct, immediate, or delayed death of one or more individuals. A fatal accident is typically classified as one where death occurs immediately or within 30 days of the injury sustained in the incident. Death occurs through intracranial hemorrhage, laceration of vital organs, or traumatic asphyxia. It requires an autopsy to determine if the death was caused by the injury or other underlying factors.',
    },
};

function InfoIcon({ title, message }) {
    const [show, setShow] = useState(false);
    return (
        <>
            <button
                type="button"
                className="btn btn-link p-0 ms-1 align-baseline border-0"
                style={{ color: 'var(--app-primary-accent)', fontSize: '0.75rem', textDecoration: 'none', lineHeight: 1 }}
                onClick={() => setShow(true)}
                aria-label={`More information about ${title}`}
            >
                ⓘ
            </button>
            <HelpModal show={show} onHide={() => setShow(false)} title={title} message={message} />
        </>
    );
}

function SectionHeader({ title }) { return <h5 className="mb-4 fw-bold pb-2 mt-4" style={{ borderBottom: '1px solid var(--app-border-dark)', fontSize: '1rem', color: 'var(--app-text-primary)', transition: 'all 0.3s' }}>{title}</h5>; }

function InputField({ label, hint, infoTitle, infoMessage, value, onChange, unit, required, step, decimals }) {
    const inputId = `traffic-${String(label).toLowerCase().replace(/[^a-z0-9]+/g, '-')}`;
    const displayValue = value === null || value === undefined || value === ''
        ? ''
        : decimals != null
            ? Number(value).toFixed(decimals)
            : value;

    return (
        <div className="mb-4">
            <label htmlFor={inputId} className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>
                {label}{required && <span className="text-danger"> *</span>}
            </label>
            {hint && (
                <div style={{ fontSize: '0.8rem', color: 'var(--app-text-muted)', marginBottom: '8px' }}>
                    {hint}
                    {infoTitle && infoMessage && <InfoIcon title={infoTitle} message={infoMessage} />}
                </div>
            )}
            <div className="input-group">
                <input id={inputId} type="number" step={step} className="form-control" value={displayValue} onChange={(e) => onChange(e.target.value)} />
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
            <label className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>Notes</label>
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

const LEGACY_LANE_NAMES = {
    'Two Lane (Two Way)': 'Two Lane',
    'Four Lane (Two Way)': 'Four Lane',
    'Six Lane (Two Way)': 'Six Lane',
    'Eight Lane (Two Way)': 'Eight Lane',
    '8 Lane Expressway (Two Way)': 'Expressway',
};

const buildTrafficForm = (value) => {
    const normalized = normalizeTrafficData({ ...INITIAL_STATE, ...(value || {}) });
    const laneValue = normalized.alternate_road.alternate_road_carriageway;
    const lane = LANE_TYPES.find((item) => item.code === laneValue || item.name === laneValue);
    const wpiProfile = normalized.wpi_profile || '2019';
    const officialProfile = officialWpiProfile(wpiProfile);
    const customProfiles = Array.isArray(normalized.wpi?.custom_profiles)
        ? normalized.wpi.custom_profiles
        : [];
    const selectedCustom = customProfiles.find((profile) => profile?.metadata?.name === wpiProfile);
    const selectedData = officialProfile?.data
        || selectedCustom?.data
        || normalized.wpi_data;
    return {
        ...normalized,
        alternate_road: {
            ...normalized.alternate_road,
            alternate_road_carriageway: lane?.name || LEGACY_LANE_NAMES[laneValue] || '',
        },
        wpi_profile: wpiProfile,
        wpi_year: String(
            officialProfile?.metadata?.year
            || selectedCustom?.metadata?.year
            || normalized.wpi_year
            || 2019,
        ),
        wpi_data: normalizeWpiMatrix(
            Object.keys(selectedData || {}).length > 0
                ? selectedData
                : WPI_DATABASE['2019'].data,
        ),
        wpi_custom_profiles: customProfiles,
        wpi_common_state: normalized.wpi?.common_state || deriveCommonState(selectedData),
    };
};

const serializeTrafficForm = (form) => {
    const {
        wpi_custom_profiles: customProfiles,
        wpi_common_state: commonState,
        ...projectForm
    } = form;
    const selectedOfficial = officialWpiProfile(form.wpi_profile);
    const selectedCustom = customProfiles.find(
        (profile) => profile?.metadata?.name === form.wpi_profile,
    );
    const selectedMetadata = selectedOfficial?.metadata || selectedCustom?.metadata || {};
    const baseData = WPI_DATABASE['2019'].data;
    const selectedData = cloneData(form.wpi_data);

    // Mirror the form's sub-objects onto the flat keys the calculation
    // payload, desktop files and the report read, so the saved project has
    // one consistent set of values whichever shape a consumer looks at.
    const laneValue = form.alternate_road?.alternate_road_carriageway || '';
    const lane = LANE_TYPES.find((item) => item.name === laneValue || item.code === laneValue);
    const numberOrZero = (value) => (Number.isFinite(Number(value)) && value !== '' && value !== null ? Number(value) : 0);
    const flatMirror = {
        alternate_road_carriageway: lane?.code || laneValue,
        carriage_width_in_m: numberOrZero(form.alternate_road?.carriage_width_in_m),
        hourly_capacity: numberOrZero(form.alternate_road?.hourly_capacity),
        severity_minor: numberOrZero(form.severity?.severity_minor),
        severity_major: numberOrZero(form.severity?.severity_major),
        severity_fatal: numberOrZero(form.severity?.severity_fatal),
        ...Object.fromEntries(Object.entries(form.road_params || {}).map(([key, value]) => [key, numberOrZero(value)])),
        peak_hour_distribution: form.peak_distribution || {},
    };

    return {
        ...projectForm,
        ...flatMirror,
        force_free_flow_off_peak: Boolean(form.force_free_flow),
        wpi: {
            selected_profile_id: selectedMetadata.id || null,
            selected_profile_name: form.wpi_profile,
            selected_profile_year: Number(form.wpi_year || selectedMetadata.year || 2019),
            profile_type: selectedOfficial ? 'db' : 'custom',
            data_snapshot: {
                base: cloneData(baseData),
                selected: selectedData,
                ratio: computeWpiRatio(selectedData, baseData),
            },
            common_state: commonState,
            custom_profiles: customProfiles,
        },
    };
};

const TrafficData = () => {
    const { projectData, updateProjectData } = useProjectData();
    const [form, setForm] = useState(() => buildTrafficForm(projectData.traffic_data));

    const [validationMsg, setValidationMsg] = useState('');
    const [hasValidated, setHasValidated] = useState(false);
    const [wpiEditor, setWpiEditor] = useState(null);
    const reroutingSelectRef = useRef(null);
    const accidentShareTotal = VEHICLES.reduce((sum, v) => sum + (Number(form.vehicles?.[v.key]?.accident_percentage) || 0), 0);

    useEffect(() => {
        updateProjectData('traffic_data', serializeTrafficForm(form));
    }, [form, updateProjectData]);

    useEffect(() => {
        const next = buildTrafficForm(projectData.traffic_data);
        // Project imports can replace traffic data while this page remains mounted.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setForm(prev => JSON.stringify(next) !== JSON.stringify(prev) ? next : prev);
    }, [projectData.traffic_data]);

    const handleModeChange = (val) => setForm(prev => ({ ...prev, calculation_mode: val }));
    const handleCostChange = (val) => setForm(prev => ({ ...prev, road_user_cost_per_day: val }));
    const handleRemarksChange = (html) => setForm(prev => ({ ...prev, remarks: html }));

    const handleClearAll = () => {
        setForm(buildTrafficForm(INITIAL_STATE));
        setValidationMsg('');
        setHasValidated(false);
    };

    const handleWpiProfileChange = (profileName) => {
        const profile = officialWpiProfile(profileName)
            || form.wpi_custom_profiles.find((item) => item.metadata.name === profileName);
        const data = normalizeWpiMatrix(profile?.data);
        setForm(prev => ({
            ...prev,
            wpi_profile: profileName,
            wpi_year: String(profile?.metadata?.year || new Date().getFullYear()),
            wpi_data: data,
            wpi_common_state: deriveCommonState(data),
        }));
    };

    const handleNewWpi = () => {
        setWpiEditor({
            mode: 'new',
            template: 'scratch',
            metadata: {
                id: '',
                name: 'custom',
                year: new Date().getFullYear(),
                remark: '',
                is_custom: true,
            },
            data: emptyWpiData(),
            commonState: Object.fromEntries(WPI_COLUMNS.map(({ key }) => [key, true])),
        });
    };

    const handleEditWpi = () => {
        const profile = form.wpi_custom_profiles.find(
            (item) => item.metadata.name === form.wpi_profile,
        );
        if (!profile) return;
        setWpiEditor({
            mode: 'edit',
            template: profile.metadata.id,
            metadata: { ...profile.metadata },
            data: normalizeWpiMatrix(profile.data),
            commonState: deriveCommonState(profile.data),
        });
    };

    const handleDeleteWpi = () => {
        if (officialWpiProfile(form.wpi_profile)) return;
        if (window.confirm(`Delete profile "${form.wpi_profile}"?`)) {
            const nextProfiles = form.wpi_custom_profiles.filter(
                (profile) => profile.metadata.name !== form.wpi_profile,
            );
            const data = cloneData(WPI_DATABASE['2019'].data);
            setForm(prev => ({
                ...prev,
                wpi_profile: '2019',
                wpi_year: '2019',
                wpi_data: data,
                wpi_common_state: deriveCommonState(data),
                wpi_custom_profiles: nextProfiles,
            }));
        }
    };

    const saveWpiEditor = () => {
        const name = wpiEditor.metadata.name.trim();
        if (!name) {
            setValidationMsg('WPI profile name is required.');
            return;
        }
        const duplicate = [
            ...Object.keys(WPI_DATABASE),
            ...form.wpi_custom_profiles
                .filter((profile) => profile.metadata.id !== wpiEditor.metadata.id)
                .map((profile) => profile.metadata.name),
        ].some((profileName) => profileName.toLowerCase() === name.toLowerCase());
        if (duplicate) {
            setValidationMsg(`A WPI profile named "${name}" already exists.`);
            return;
        }

        const profile = {
            metadata: {
                ...wpiEditor.metadata,
                id: wpiEditor.metadata.id || `wpi_custom_${crypto.randomUUID().slice(0, 8)}`,
                name,
                year: Number(wpiEditor.metadata.year),
                is_custom: true,
                hash: '',
                is_shared: false,
            },
            data: cloneData(wpiEditor.data),
        };
        const nextProfiles = wpiEditor.mode === 'edit'
            ? form.wpi_custom_profiles.map((item) => (
                item.metadata.id === profile.metadata.id ? profile : item
            ))
            : [...form.wpi_custom_profiles, profile];

        setForm(prev => ({
            ...prev,
            wpi_profile: profile.metadata.name,
            wpi_year: String(profile.metadata.year),
            wpi_data: cloneData(profile.data),
            wpi_common_state: wpiEditor.commonState,
            wpi_custom_profiles: nextProfiles,
        }));
        setValidationMsg('');
        setWpiEditor(null);
    };

    const validate = () => {
        const messages = validateTrafficData(form);
        setHasValidated(true);
        if (messages.length > 0) {
            setValidationMsg(messages.join(' '));
            if (!form.alternate_road.alternate_road_carriageway) {
                reroutingSelectRef.current?.focus();
                reroutingSelectRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
            return { valid: false, errors: messages };
        }
        setValidationMsg('');
        return { valid: true, errors: [] };
    };

    const renderIndiaMode = () => (
        <div className="d-flex flex-column gap-2">
            <SectionHeader title="Vehicle Traffic Data" />
            <div className="table-responsive mb-4">
                <table className="table table-bordered table-sm text-center align-middle" style={{ backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-mid)', marginBottom: 0 }}>
                    <thead><tr><th style={{ width: '35%', backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px' }}>Vehicle Type</th><th style={{ width: '25%', backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px' }}>Vehicles / Day</th><th style={{ width: '20%', backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px' }}>Share of accidents (%)</th><th style={{ width: '20%', backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', borderColor: 'var(--app-border-mid)', fontWeight: 500, padding: '12px 8px' }}>Power to weight ratio (PWR)</th></tr></thead>
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
                                <td className="p-0">{v.hasPwr ? <input type="number" step="0.01" className="form-control text-end px-2 py-1" style={{ width: '100%', border: 'none', backgroundColor: 'var(--app-input-bg)', color: 'var(--app-text-primary)', height: '36px', outline: 'none' }} onFocus={e => e.target.style.backgroundColor = 'var(--app-bg-alt)'} onBlur={e => e.target.style.backgroundColor = 'var(--app-input-bg)'} value={Number(form.vehicles[v.key]?.pwr ?? v.defaultPwr).toFixed(2)} onChange={(e) => {
                                    const nextVehicles = { ...form.vehicles, [v.key]: { ...form.vehicles[v.key], pwr: Number(e.target.value) } };
                                    setForm(prev => ({ ...prev, vehicles: nextVehicles }));
                                }} /> : <div className="text-muted">-</div>}</td>
                            </tr>
                        ))}
                    </tbody>
                    <tfoot>
                        <tr>
                            <td className="text-start ps-3" style={{ fontSize: '0.8rem', color: 'var(--app-text-muted)' }}>Share of accidents by vehicle type — must total 100 %</td>
                            <td />
                            <td className="text-end pe-2 fw-bold" data-testid="accident-share-total" style={{ color: Math.abs(accidentShareTotal - 100) > 0.1 ? '#dc3545' : 'var(--app-text-primary)' }}>{accidentShareTotal.toFixed(2)} %</td>
                            <td />
                        </tr>
                    </tfoot>
                </table>
            </div>

            <SectionHeader title="Rerouting Road Configuration" />
            <div className="mb-4">
                <label className="fw-bold mb-1 d-block" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>
                    Rerouting Road Configuration <span className="text-danger">*</span>
                </label>
                <div style={{ fontSize: '0.8rem', color: 'var(--app-text-muted)', marginBottom: '8px' }}>Lane configuration (auto-fills capacity and width).</div>
                <select
                    ref={reroutingSelectRef}
                    required
                    aria-required="true"
                    aria-invalid={hasValidated && !form.alternate_road.alternate_road_carriageway ? 'true' : 'false'}
                    className={`form-select ${hasValidated && !form.alternate_road.alternate_road_carriageway ? 'is-invalid' : ''}`}
                    value={form.alternate_road.alternate_road_carriageway}
                    onChange={(e) => {
                        const lane = LANE_TYPES.find(l => l.name === e.target.value);
                        setForm(prev => ({ ...prev, alternate_road: { alternate_road_carriageway: e.target.value, carriage_width_in_m: lane ? lane.width : 0, hourly_capacity: lane ? lane.capacity : 0 } }));
                    }}
                >
                    <option value="">- Select -</option>
                    {LANE_TYPES.map(l => <option key={l.code} value={l.name}>{l.name}</option>)}
                </select>
                {hasValidated && !form.alternate_road.alternate_road_carriageway && (
                    <div className="invalid-feedback d-block">
                        Alternate Road Carriageway type is not selected - choose the carriageway configuration available for traffic diversion during construction.
                    </div>
                )}
            </div>
            <InputField label="Carriageway Width" unit="(m)" required step="0.01" decimals={2} value={form.alternate_road.carriage_width_in_m} onChange={(v) => setForm(prev => ({ ...prev, alternate_road: { ...prev.alternate_road, carriage_width_in_m: Number(v) } }))} />
            <InputField label="Road Hourly Capacity" unit="(PCU/hr)" required decimals={0} value={form.alternate_road.hourly_capacity} onChange={(v) => setForm(prev => ({ ...prev, alternate_road: { ...prev.alternate_road, hourly_capacity: Number(v) } }))} />

            <SectionHeader title="Accident Severity Distribution" />
            <InputField label="Minor Injury" hint="Percentage of accidents resulting in minor injury" infoTitle={FIELD_INFO.minor_injury.title} infoMessage={FIELD_INFO.minor_injury.message} unit="(%)" step="0.01" decimals={2} value={form.severity.severity_minor} onChange={(v) => {
                const num = Number(v);
                let next = { ...form.severity, severity_minor: num };
                next.severity_major = Math.min(100 - num, next.severity_major);
                next.severity_fatal = 100 - num - next.severity_major;
                setForm(prev => ({ ...prev, severity: next }));
            }} />
            <InputField label="Major Injury" hint="Percentage of accidents resulting in major injury" infoTitle={FIELD_INFO.major_injury.title} infoMessage={FIELD_INFO.major_injury.message} unit="(%)" step="0.01" decimals={2} value={form.severity.severity_major} onChange={(v) => {
                const num = Number(v);
                let next = { ...form.severity, severity_major: num };
                next.severity_minor = Math.min(100 - num, next.severity_minor);
                next.severity_fatal = 100 - num - next.severity_minor;
                setForm(prev => ({ ...prev, severity: next }));
            }} />
            <InputField label="Fatal Accident" hint="Percentage of accidents resulting in fatal injury" infoTitle={FIELD_INFO.fatal_accident.title} infoMessage={FIELD_INFO.fatal_accident.message} unit="(%)" step="0.01" decimals={2} value={form.severity.severity_fatal} onChange={(v) => {
                const num = Number(v);
                let next = { ...form.severity, severity_fatal: num };
                next.severity_minor = Math.min(100 - num, next.severity_minor);
                next.severity_major = 100 - num - next.severity_minor;
                setForm(prev => ({ ...prev, severity: next }));
            }} />

            <SectionHeader title="Road Parameters" />
            <InputField label="Road Roughness" hint="Indicates the smoothness of the road surface; lower values mean smoother ride quality, higher values mean more unevenness measured in mm/km" unit="(mm/km)" required decimals={0} value={form.road_params.road_roughness_mm_per_km} onChange={(v) => setForm(prev => ({ ...prev, road_params: { ...prev.road_params, road_roughness_mm_per_km: Number(v) } }))} />
            <InputField label="Road Rise" hint="Upward gradient of the road, expressed as vertical increase in meters per kilometer (m/km)." unit="(m/km)" required step="0.001" decimals={3} value={form.road_params.road_rise_m_per_km} onChange={(v) => setForm(prev => ({ ...prev, road_params: { ...prev.road_params, road_rise_m_per_km: Number(v) } }))} />
            <InputField label="Road Fall" hint="Downward gradient of the road, expressed as vertical decrease in meters per kilometer (m/km)." unit="(m/km)" required step="0.001" decimals={3} value={form.road_params.road_fall_m_per_km} onChange={(v) => setForm(prev => ({ ...prev, road_params: { ...prev.road_params, road_fall_m_per_km: Number(v) } }))} />
            <InputField label="Rerouting Distance" hint="Distance travel by the road users due to rerouting during construction." unit="(km)" step="0.001" decimals={3} value={form.road_params.additional_reroute_distance_km} onChange={(v) => setForm(prev => ({ ...prev, road_params: { ...prev.road_params, additional_reroute_distance_km: Number(v) } }))} />
            <InputField label="Rerouting Time" hint="Travel time incurred by road users due to rerouting during construction." unit="(min)" step="0.001" decimals={3} value={form.road_params.additional_travel_time_min} onChange={(v) => setForm(prev => ({ ...prev, road_params: { ...prev.road_params, additional_travel_time_min: Number(v) } }))} />
            <InputField label="Crash Rate along Rerouting Route" hint="Number of accidents per million kilometers of road length per day." unit="(acc / M km)" required step="0.01" decimals={2} value={form.road_params.crash_rate_accidents_per_million_km} onChange={(v) => setForm(prev => ({ ...prev, road_params: { ...prev.road_params, crash_rate_accidents_per_million_km: Number(v) } }))} />
            <InputField label="Work Zone Multiplier" hint="Scales the work-zone accident adjustment: 1 applies the full work-zone accident risk (default), 0 switches it off. Values between 0 and 1 apply it partially." required step="0.0001" decimals={4} value={form.road_params.work_zone_multiplier} onChange={(v) => setForm(prev => ({ ...prev, road_params: { ...prev.road_params, work_zone_multiplier: Number(v) } }))} />

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
                            {[...Array(form.num_peak_hours)].map((_, i) => (
                                <tr key={i}><td className="text-start ps-3 fw-bold">{`Peak Hour ${i + 1}`}</td><td className="p-0">
                                    <input type="number" step="0.01" className="form-control text-end px-2 py-1" style={{ width: '100%', border: 'none', backgroundColor: 'var(--app-input-bg)', color: 'var(--app-text-primary)', height: '36px', outline: 'none' }} onFocus={e => e.target.style.backgroundColor = 'var(--app-bg-alt)'} onBlur={e => e.target.style.backgroundColor = 'var(--app-input-bg)'} value={((form.peak_distribution[`peak_hour_${i + 1}`] ?? 0.04) * 100).toFixed(2)} onChange={(e) => setForm(prev => ({ ...prev, peak_distribution: { ...prev.peak_distribution, [`peak_hour_${i + 1}`]: Number(e.target.value) / 100 } }))} /></td></tr>
                            ))}
                            <tr>
                                <td className="text-start ps-3 fw-bold">Other Hours (Average)</td>
                                <td className="text-end pe-3 fw-bold">
                                    {(Math.max(0, 100 - Object.entries(form.peak_distribution)
                                        .filter(([key]) => key.startsWith('peak_hour_'))
                                        .slice(0, form.num_peak_hours)
                                        .reduce((sum, [, value]) => sum + Number(value || 0) * 100, 0)) / Math.max(1, 24 - form.num_peak_hours)).toFixed(2)} %
                                </td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <SectionHeader title="Wholesale Price Index (WPI) Adjustment Factors" />
            <div className="d-flex flex-wrap gap-2 mb-3 align-items-center">
                <label className="fw-bold mb-0" style={{ fontSize: '0.9rem', color: 'var(--app-text-secondary)', transition: 'color 0.3s' }}>WPI Profile:</label>
                <select className="form-select w-auto" value={form.wpi_profile} onChange={(e) => handleWpiProfileChange(e.target.value)}>
                    {Object.keys(WPI_DATABASE).map(y => <option key={y} value={y}>{y}</option>)}
                    {form.wpi_custom_profiles.map(({ metadata }) => (
                        <option key={metadata.id} value={metadata.name}>★ {metadata.name}</option>
                    ))}
                </select>
                <span className="text-success" title="Official profile loaded">✓</span>
                <div className="ms-auto d-flex gap-2">
                    <button className="btn btn-sm btn-outline-secondary" onClick={handleNewWpi}>+ Add New</button>
                    <button className="btn btn-sm btn-outline-secondary" disabled={Boolean(officialWpiProfile(form.wpi_profile))} onClick={handleEditWpi}>Edit</button>
                    <button className="btn btn-sm btn-outline-secondary" disabled={Boolean(officialWpiProfile(form.wpi_profile))} onClick={handleDeleteWpi}>Delete</button>
                </div>
            </div>

            <div className="mb-4 wpi-table-shell">
                <style>{WPI_TABLE_CSS}</style>
                <table className="wpi-sticky-table">
                    <thead>
                        <tr>
                            <th rowSpan="2" className="wpi-corner" />
                            {WPI_GROUPS.map((group) => (
                                <th key={group.label} colSpan={group.span} className="wpi-group">{group.label}</th>
                            ))}
                        </tr>
                        <tr>{WPI_COLUMNS.map(col => <th key={col.key} className="wpi-col">{col.label}</th>)}</tr>
                    </thead>
                    <tbody>
                        {['Common to All', ...VEHICLES.map(v => v.label)].map((rowLabel, rIdx) => {
                            const vKey = rIdx === 0 ? null : VEHICLES[rIdx - 1].key;
                            return (
                                <tr key={rowLabel} className={vKey ? undefined : 'wpi-pin'}>
                                    <td className="wpi-rowlabel">{rowLabel}</td>
                                    {WPI_COLUMNS.map(col => (
                                        <td key={col.key} className="p-0">
                                            {vKey ? (
                                                <div className="wpi-value">
                                                    {getWpiValue(form.wpi_data, vKey, col.key).toFixed(4)}
                                                </div>
                                            ) : (
                                                <div className="wpi-check">
                                                    <input type="checkbox" aria-label={`Common to all ${col.label}`} checked={Boolean(form.wpi_common_state[col.key])} readOnly />
                                                </div>
                                            )}
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

            {wpiEditor && (
                <div style={{ position: 'fixed', inset: 0, padding: '3vh 3vw', backgroundColor: 'rgba(0, 0, 0, 0.65)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
                    <div style={{ display: 'flex', flexDirection: 'column', width: 'min(1500px, 94vw)', maxHeight: '94vh', backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-mid)', borderRadius: '8px', color: 'var(--app-text-primary)', boxShadow: '0 16px 40px rgba(0,0,0,0.55)', overflow: 'hidden' }}>
                        <div style={{ backgroundColor: 'var(--app-bg-alt)', padding: '14px 18px', borderBottom: '1px solid var(--app-border-mid)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <h5 className="m-0 fw-bold">WPI Profile Editor</h5>
                            <button type="button" aria-label="Close WPI editor" style={{ background: 'transparent', border: 'none', color: 'var(--app-text-muted)', fontSize: '1.4rem', cursor: 'pointer' }} onClick={() => setWpiEditor(null)}>×</button>
                        </div>
                        <div style={{ padding: '18px', overflow: 'auto' }}>
                            {wpiEditor.mode === 'new' && (
                                <div className="mb-3">
                                    <label className="fw-bold mb-1 d-block">Based on Template:</label>
                                    <select
                                        className="form-select"
                                        value={wpiEditor.template}
                                        onChange={(event) => {
                                            const template = event.target.value;
                                            const profile = officialWpiProfile(template)
                                                || form.wpi_custom_profiles.find((item) => item.metadata.id === template);
                                            const data = template === 'scratch'
                                                ? emptyWpiData()
                                                : cloneData(profile?.data || emptyWpiData());
                                            setWpiEditor(prev => ({
                                                ...prev,
                                                template,
                                                data,
                                                commonState: deriveCommonState(data),
                                            }));
                                        }}
                                    >
                                        <option value="scratch">Scratch (all 1.0)</option>
                                        {Object.entries(WPI_DATABASE).map(([name, profile]) => <option key={profile.metadata.id} value={name}>Clone: {name}</option>)}
                                        {form.wpi_custom_profiles.map((profile) => <option key={profile.metadata.id} value={profile.metadata.id}>Clone: {profile.metadata.name}</option>)}
                                    </select>
                                </div>
                            )}
                            <div className="row g-3 mb-3">
                                <div className="col-md-4">
                                    <label className="fw-bold mb-1 d-block">Profile Name:</label>
                                    <input className="form-control" value={wpiEditor.metadata.name} onChange={(event) => setWpiEditor(prev => ({ ...prev, metadata: { ...prev.metadata, name: event.target.value } }))} />
                                </div>
                                <div className="col-md-3">
                                    <label className="fw-bold mb-1 d-block">Year (metadata):</label>
                                    <input type="number" min="1900" max="2200" className="form-control" value={wpiEditor.metadata.year} onChange={(event) => setWpiEditor(prev => ({ ...prev, metadata: { ...prev.metadata, year: event.target.value } }))} />
                                </div>
                                <div className="col-md-5">
                                    <label className="fw-bold mb-1 d-block">Remark:</label>
                                    <input className="form-control" placeholder="Optional remarks..." value={wpiEditor.metadata.remark || ''} onChange={(event) => setWpiEditor(prev => ({ ...prev, metadata: { ...prev.metadata, remark: event.target.value } }))} />
                                </div>
                            </div>
                            <div className="fw-bold mb-2">Adjust WPI Ratios:</div>
                            <div className="wpi-table-shell" style={{ maxHeight: '52vh' }}>
                                <style>{WPI_TABLE_CSS}</style>
                                <table className="wpi-sticky-table">
                                    <thead>
                                        <tr>
                                            <th rowSpan="2" className="wpi-corner" />
                                            {WPI_GROUPS.map((group) => <th key={group.label} colSpan={group.span} className="wpi-group">{group.label}</th>)}
                                        </tr>
                                        <tr>{WPI_COLUMNS.map((column) => <th key={column.key} className="wpi-col">{column.label}</th>)}</tr>
                                    </thead>
                                    <tbody>
                                        <tr className="wpi-pin">
                                            <td className="wpi-rowlabel">Common to All</td>
                                            {WPI_COLUMNS.map((column) => (
                                                <td key={column.key}>
                                                    <input
                                                        type="checkbox"
                                                        checked={Boolean(wpiEditor.commonState[column.key])}
                                                        onChange={(event) => {
                                                            const checked = event.target.checked;
                                                            const firstValue = getWpiValue(wpiEditor.data, VEHICLES[0].key, column.key);
                                                            setWpiEditor(prev => {
                                                                const data = cloneData(prev.data);
                                                                if (checked) {
                                                                    VEHICLES.forEach(({ key }) => {
                                                                        data[key][column.key] = firstValue;
                                                                    });
                                                                }
                                                                return {
                                                                    ...prev,
                                                                    data,
                                                                    commonState: { ...prev.commonState, [column.key]: checked },
                                                                };
                                                            });
                                                        }}
                                                    />
                                                </td>
                                            ))}
                                        </tr>
                                        {VEHICLES.map((vehicle, vehicleIndex) => (
                                            <tr key={vehicle.key}>
                                                <td className="wpi-rowlabel">{vehicle.label}</td>
                                                {WPI_COLUMNS.map((column) => {
                                                    const locked = wpiEditor.commonState[column.key] && vehicleIndex > 0;
                                                    return (
                                                        <td key={column.key} className="p-0">
                                                            <input
                                                                type="number"
                                                                min="0"
                                                                step="0.0001"
                                                                readOnly={locked}
                                                                className="form-control text-end px-2 py-2 rounded-0 border-0"
                                                                style={{ minWidth: '108px', opacity: locked ? 0.65 : 1 }}
                                                                value={getWpiValue(wpiEditor.data, vehicle.key, column.key)}
                                                                onChange={(event) => {
                                                                    const value = Number(event.target.value);
                                                                    setWpiEditor(prev => {
                                                                        const data = cloneData(prev.data);
                                                                        data[vehicle.key][column.key] = value;
                                                                        if (vehicleIndex === 0 && prev.commonState[column.key]) {
                                                                            VEHICLES.forEach(({ key }) => {
                                                                                data[key][column.key] = value;
                                                                            });
                                                                        }
                                                                        return { ...prev, data };
                                                                    });
                                                                }}
                                                            />
                                                        </td>
                                                    );
                                                })}
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                        <div style={{ padding: '14px 18px', display: 'flex', justifyContent: 'flex-end', borderTop: '1px solid var(--app-border-mid)', gap: '8px', backgroundColor: 'var(--app-bg-alt)' }}>
                            <button className="btn btn-outline-secondary" onClick={() => setWpiEditor(null)}>Cancel</button>
                            <button className="btn" style={{ backgroundColor: 'var(--app-primary-accent)', color: 'var(--app-btn-primary-text)' }} onClick={saveWpiEditor}>Save</button>
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

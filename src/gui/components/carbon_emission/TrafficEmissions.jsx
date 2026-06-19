/* eslint-disable no-unused-vars */
import React, { useState, useEffect, useMemo } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';

const VEHICLE_TYPES = [
    { key: "small_cars", label: "Small Car", defaultEf: 0.1030 },
    { key: "big_cars", label: "Big Car", defaultEf: 0.2690 },
    { key: "two_wheelers", label: "Two Wheeler", defaultEf: 0.0351 },
    { key: "o_buses", label: "Ordinary Buses", defaultEf: 0.4548 },
    { key: "d_buses", label: "Deluxe Buses", defaultEf: 0.6064 },
    { key: "lcv", label: "LCV", defaultEf: 0.3070 },
    { key: "hcv", label: "HCV", defaultEf: 0.5928 },
    { key: "mcv", label: "MCV", defaultEf: 0.7375 },
];

const TrafficEmissions = ({ controller }) => {
    const { projectData, updateProjectData } = useProjectData();
    const [mode, setMode] = useState('calculate');
    const [rerouteKm, setRerouteKm] = useState(0);
    const [factors, setFactors] = useState(
        VEHICLE_TYPES.reduce((acc, v) => ({ ...acc, [v.key]: v.defaultEf }), {})
    );
    const [aadt, setAadt] = useState(
        VEHICLE_TYPES.reduce((acc, v) => ({ ...acc, [v.key]: 0 }), {})
    );
    const [directValue, setDirectValue] = useState(0);
    const [remarks, setRemarks] = useState('');

    useEffect(() => {
        const trafficData = projectData.traffic_data || {};
        const vpd = trafficData.vehicles_per_day || {};
        setAadt(prev => ({ ...prev, ...vpd }));

        const carbonData = projectData.carbon_emission_data || {};
        const diversionData = carbonData.diversion_emissions_data || {};
        if (diversionData.mode) setMode(diversionData.mode);
        if (diversionData.reroute_km) setRerouteKm(diversionData.reroute_km);
        if (diversionData.factors) setFactors(prev => ({ ...prev, ...diversionData.factors }));
        if (diversionData.direct_value) setDirectValue(diversionData.direct_value);
        if (diversionData.remarks) setRemarks(diversionData.remarks);
    }, [projectData]);

    const handleUpdateFactor = (key, val) => {
        const updated = { ...factors, [key]: parseFloat(val) || 0 };
        setFactors(updated);
        saveToEngine(mode, rerouteKm, updated, directValue, remarks);
    };

    const saveToEngine = (newMode, km, f, direct, rem) => {
        const totalPerDay = newMode === 'calculate' ?
            VEHICLE_TYPES.reduce((sum, v) => sum + ((aadt[v.key] || 0) * km * (f[v.key] || 0)), 0) :
            direct;
        const desktopMode = newMode === 'calculate' ? 'Calculate by Vehicle' : 'Enter Directly';

        const prev = projectData.carbon_emission_data || {};
        updateProjectData('carbon_emission_data', {
            ...prev,
            diversion_emissions_data: {
                mode: newMode,
                calculation_mode: desktopMode,
                reroute_km: km,
                factors: f,
                direct_value: direct,
                remarks: rem,
                total_kgCO2e_per_day: totalPerDay,
                total_calculated_emissions: newMode === 'calculate' ? totalPerDay : 0,
                total_direct_emissions: newMode === 'direct' ? totalPerDay : 0,
            }
        });
    };

    const handleClearAll = () => {
        setMode('direct');
        setRerouteKm(0);
        setDirectValue(0);
        setRemarks('');
        saveToEngine('direct', 0, factors, 0, '');
    };

    const calculatedTotal = useMemo(() => {
        return VEHICLE_TYPES.reduce((sum, v) => sum + ((aadt[v.key] || 0) * rerouteKm * (factors[v.key] || 0)), 0);
    }, [aadt, rerouteKm, factors]);

    useEffect(() => {
        const totalPerDay = mode === 'calculate' ? calculatedTotal : directValue;
        const desktopMode = mode === 'calculate' ? 'Calculate by Vehicle' : 'Enter Directly';
        const prev = projectData.carbon_emission_data || {};
        const previousDiversion = prev.diversion_emissions_data || {};
        const nextDiversion = {
            ...previousDiversion,
            mode,
            calculation_mode: desktopMode,
            reroute_km: rerouteKm,
            factors,
            direct_value: directValue,
            remarks,
            total_kgCO2e_per_day: totalPerDay,
            total_calculated_emissions: mode === 'calculate' ? totalPerDay : 0,
            total_direct_emissions: mode === 'direct' ? totalPerDay : 0,
        };
        if (JSON.stringify(previousDiversion) === JSON.stringify(nextDiversion)) return;

        updateProjectData('carbon_emission_data', {
            ...prev,
            diversion_emissions_data: nextDiversion,
        });
    }, [mode, rerouteKm, factors, directValue, remarks, calculatedTotal, updateProjectData]);

    return (
        <div className="traffic-emissions d-flex flex-column text-light ps-3 pe-3 pt-3" style={{ backgroundColor: 'var(--app-bg-main)', color: 'var(--app-text-primary)', fontFamily: '"Segoe UI", sans-serif' }}>
            {/* Calculation Mode */}
            <div className="mb-4">
                <div className="fw-bold mb-2" style={{ fontSize: '0.85rem' }}>Calculation Mode</div>
                <select
                    className="form-select form-select-sm bg-dark text-light border-secondary"
                    style={{ maxWidth: '300px', backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)', fontSize: '0.85rem' }}
                    value={mode}
                    onChange={(e) => { setMode(e.target.value); saveToEngine(e.target.value, rerouteKm, factors, directValue, remarks); }}
                >
                    <option value="direct">Enter Directly</option>
                    <option value="calculate">Impact Calculation</option>
                </select>
            </div>

            {/* Total Diversion Emissions */}
            <div className="mb-4">
                <div className="fw-bold mb-1" style={{ fontSize: '0.85rem' }}>Total Diversion Emissions</div>
                <div className="text-secondary small mb-2">Enter the total carbon emissions from traffic diversion per day of construction.</div>
                <div className="position-relative">
                    <input
                        type="number"
                        className="form-control bg-dark text-light border-secondary py-3 px-4 font-monospace"
                        style={{ fontSize: '1.1rem', backgroundColor: 'var(--app-bg-card) !important', color: 'var(--app-text-primary)', borderRadius: '8px' }}
                        value={mode === 'calculate' ? calculatedTotal : directValue}
                        readOnly={mode === 'calculate'}
                        onChange={e => {
                            const val = parseFloat(e.target.value) || 0;
                            setDirectValue(val);
                            saveToEngine(mode, rerouteKm, factors, val, remarks);
                        }}
                        placeholder="0.000"
                    />
                    <span className="position-absolute end-0 top-50 translate-middle-y pe-4 text-secondary">kgCO₂e/day</span>
                </div>
            </div>

            {/* Impact Calculation View (only if mode is calculate) */}
            {mode === 'calculate' && (
                <div className="calculate-view mb-4">
                    <div className="card shadow-sm border-secondary-subtle mb-4 overflow-hidden" style={{ maxWidth: '450px', backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-mid)' }}>
                        <div className="card-header py-2 px-3 border-bottom border-secondary-subtle" style={{ backgroundColor: 'var(--app-bg-alt)' }}>
                            <span className="small fw-bold text-secondary text-uppercase tracking-wider">Diversion Parameters</span>
                        </div>
                        <div className="card-body p-3">
                            <label className="form-label text-secondary extra-small mb-1">ADDITIONAL REROUTE DISTANCE</label>
                            <div className="input-group input-group-sm">
                                <input
                                    type="number"
                                    className="form-control bg-dark text-light border-secondary"
                                    value={rerouteKm}
                                    onChange={e => { setRerouteKm(parseFloat(e.target.value) || 0); saveToEngine(mode, parseFloat(e.target.value) || 0, factors, directValue, remarks); }}
                                    placeholder="0.00"
                                />
                                <span className="input-group-text bg-dark border-secondary text-secondary">km</span>
                            </div>
                        </div>
                    </div>

                    <div className="table-responsive rounded border border-secondary-subtle">
                        <table className="table table-sm table-hover mb-0" style={{ fontSize: '0.8rem', backgroundColor: 'var(--app-bg-card)', color: 'var(--app-text-primary)' }}>
                            <thead className="sticky-top" style={{ backgroundColor: 'var(--app-bg-alt)', zIndex: 1 }}>
                                <tr className="text-secondary">
                                    <th className="ps-3 py-2 border-0" style={{ width: '35%' }}>Vehicle Classification</th>
                                    <th className="text-end py-2 border-0">Source AADT</th>
                                    <th className="text-end py-2 border-0" style={{ width: '25%' }}>EF (kgCO₂e/km)</th>
                                    <th className="text-end py-2 border-0 pe-4">Subtotal (kg/day)</th>
                                </tr>
                            </thead>
                            <tbody className="border-0">
                                {VEHICLE_TYPES.map(v => {
                                    const emissionsPerDay = (aadt[v.key] || 0) * rerouteKm * (factors[v.key] || 0);
                                    return (
                                        <tr key={v.key} className="border-secondary-subtle align-middle">
                                            <td className="ps-3 py-1 text-light">{v.label}</td>
                                            <td className="text-end py-1 font-monospace text-secondary">{aadt[v.key] || 0} veh/day</td>
                                            <td className="py-1">
                                                <input
                                                    type="number"
                                                    step="0.0001"
                                                    className="form-control form-control-sm border-0 bg-transparent text-end text-light px-0"
                                                    value={factors[v.key]}
                                                    onChange={e => handleUpdateFactor(v.key, e.target.value)}
                                                />
                                            </td>
                                            <td className="text-end py-1 pe-4 fw-bold font-monospace" style={{ color: '#9adc32' }}>
                                                {emissionsPerDay.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Remarks Section */}
            <div className="mb-4">
                <div className="fw-bold mb-2" style={{ fontSize: '0.85rem' }}>Remarks / Notes</div>
                <div className="remarks-toolbar d-flex align-items-center gap-1 p-1 bg-dark border border-secondary rounded-top">
                    <button className="remarks-btn fw-bold">B</button>
                    <button className="remarks-btn fst-italic">I</button>
                    <button className="remarks-btn text-decoration-underline">U</button>
                    <button className="remarks-btn text-decoration-line-through">S</button>
                    <div className="vr mx-1 bg-secondary opacity-25" style={{ height: '14px' }}></div>
                    <button className="remarks-btn">Left</button>
                    <button className="remarks-btn">Center</button>
                    <button className="remarks-btn">Right</button>
                    <button className="remarks-btn">Justify</button>
                    <div className="vr mx-1 bg-secondary opacity-25" style={{ height: '14px' }}></div>
                    <button className="remarks-btn">• List</button>
                    <button className="remarks-btn">1. List</button>
                    <div className="vr mx-1 bg-secondary opacity-25" style={{ height: '14px' }}></div>
                    <button className="remarks-btn">+ Table</button>
                    <button className="remarks-btn">+ Row</button>
                    <button className="remarks-btn">+ Col</button>
                    <button className="remarks-btn ms-auto" onClick={() => { setRemarks(''); saveToEngine(mode, rerouteKm, factors, directValue, ''); }}>Clear</button>
                </div>
                <textarea
                    className="w-100 p-3 text-light border-secondary border-top-0 rounded-bottom"
                    rows="4"
                    placeholder="Add notes or remarks here. These will appear in the generated report."
                    style={{ fontSize: '0.85rem', resize: 'none', backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)' }}
                    value={remarks}
                    onChange={e => { setRemarks(e.target.value); saveToEngine(mode, rerouteKm, factors, directValue, e.target.value); }}
                ></textarea>
            </div>

            {/* Clear All Button */}
            <div className="mb-5 pb-5">
                <button
                    className="btn btn-sm w-100 py-2 border-secondary text-secondary"
                    style={{ backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-secondary)' }}
                    onClick={handleClearAll}
                >
                    Clear All
                </button>
            </div>

            {/* Sticky Summary Bar */}
            <div className="traffic-sticky-summary">
                <div className="d-flex align-items-center justify-content-between">
                    <div className="d-flex align-items-center gap-4">
                        <div style={{ fontSize: '0.9rem' }}>
                            <span className="text-secondary text-uppercase small tracking-wider">Total Diversion Emissions:</span>
                            <span className="ms-2 fw-bold" style={{ color: '#9adc32', fontSize: '1.2rem' }}>
                                {(mode === 'calculate' ? calculatedTotal : directValue).toLocaleString(undefined, { minimumFractionDigits: 3, maximumFractionDigits: 3 })}
                            </span>
                            <span className="text-secondary small ms-1">kgCO₂e/day</span>
                        </div>
                    </div>
                </div>
            </div>

            <style>{`
                .extra-small { font-size: 0.65rem; }
                .tracking-wider { letter-spacing: 0.04rem; }
                .shadow-xs { box-shadow: 0 1px 3px rgba(0,0,0,0.3); }
                .form-control:focus, .form-select:focus {
                    border-color: #9adc32 !important;
                    box-shadow: 0 0 0 2px rgba(154, 205, 50, 0.25) !important;
                    outline: none !important;
                }
                .traffic-sticky-summary {
                    position: sticky;
                    bottom: -15px;
                    left: 0;
                    right: 0;
                    background-color: var(--app-bg-card);
                    color: var(--app-text-primary);
                    padding: 12px 20px;
                    border-radius: 4px;
                    z-index: 100;
                    margin-top: 25px;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                    border: 1px solid var(--app-border-mid);
                }
                .remarks-btn {
                    background: transparent;
                    border: none;
                    color: #bbb;
                    font-size: 0.75rem;
                    padding: 4px 8px;
                    border-radius: 3px;
                }
                .remarks-btn:hover {
                    color: #fff;
                    background-color: #333;
                }
            `}</style>
        </div>
    );
};

export default TrafficEmissions;

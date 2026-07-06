/* eslint-disable no-unused-vars */
/* eslint-disable react-hooks/set-state-in-effect */
import React, { useState, useEffect, useMemo } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import { computeMachineryDetailedTotal, computeMachineryLumpsumTotal, DEFAULT_MACHINERY_DATA, ENERGY_SOURCES, normalizeMachineryData } from './carbonUtils';

const MachineryEmissions = ({ controller }) => {
    const { projectData, updateProjectData } = useProjectData();
    const [mode, setMode] = useState('detailed'); 
    const [detailedEntries, setDetailedEntries] = useState([]);
    const [lumpSum, setLumpSum] = useState({
        elec_kwh_per_day: 0,
        elec_days: 0,
        elec_ef: 0.71,
        fuel_litres_per_day: 0,
        fuel_days: 0,
        fuel_ef: 2.69
    });
    const [remarks, setRemarks] = useState('');
    const [applyDaysVal, setApplyDaysVal] = useState(1);

    useEffect(() => {
        const carbonData = projectData.carbon_emission_data || {};
        const rawMachineryData = carbonData.machinery_emissions_data || {};
        const machineryData = normalizeMachineryData(rawMachineryData);
        const hasSavedDetailedRows = machineryData.detailed.rows.length > 0
            || rawMachineryData.detailed_entries
            || rawMachineryData.detailed?.rows;
        if (machineryData.mode) setMode(machineryData.mode);
        setDetailedEntries(
            hasSavedDetailedRows
                ? machineryData.detailed.rows.map((row) => ({ ...row, hours: row.hrs }))
                : DEFAULT_MACHINERY_DATA.map((row) => ({ ...row, hours: 8, days: 1 }))
        );
        setLumpSum({
            elec_kwh_per_day: machineryData.lumpsum.elec_consumption_per_day,
            elec_days: machineryData.lumpsum.elec_days,
            elec_ef: machineryData.lumpsum.elec_ef,
            fuel_litres_per_day: machineryData.lumpsum.fuel_consumption_per_day,
            fuel_days: machineryData.lumpsum.fuel_days,
            fuel_ef: machineryData.lumpsum.fuel_ef,
        });
        if (machineryData.remarks) setRemarks(machineryData.remarks);
    }, [projectData]);

    const handleAddEntry = (template = null) => {
        const newEntry = template ? { ...template, hours: 8, days: 1 } : {
            name: '',
            source: 'Diesel',
            rate: 0,
            ef: 2.69,
            hours: 8,
            days: 1
        };
        const updated = [...detailedEntries, newEntry];
        setDetailedEntries(updated);
        saveToEngine(mode, updated, lumpSum, remarks);
    };

    const handleLoadDefaults = () => {
        const defaults = DEFAULT_MACHINERY_DATA.map(d => ({ ...d, hours: 8, days: 1 }));
        setDetailedEntries(defaults);
        saveToEngine(mode, defaults, lumpSum, remarks);
    };

    const handleClearAll = () => {
        setDetailedEntries([]);
        saveToEngine(mode, [], lumpSum, remarks);
    };

    const handleApplyDays = () => {
        const updated = detailedEntries.map(e => ({ ...e, days: applyDaysVal }));
        setDetailedEntries(updated);
        saveToEngine(mode, updated, lumpSum, remarks);
    };

    const handleUpdateEntry = (index, field, value) => {
        const updated = [...detailedEntries];
        updated[index][field] = value;
        if (field === 'source') {
            const src = ENERGY_SOURCES.find(s => s.label === value);
            if (src) updated[index].ef = src.ef;
        }
        setDetailedEntries(updated);
        saveToEngine(mode, updated, lumpSum, remarks);
    };

    const handleDeleteEntry = (index) => {
        const updated = detailedEntries.filter((_, i) => i !== index);
        setDetailedEntries(updated);
        saveToEngine(mode, updated, lumpSum, remarks);
    };

    const handleUpdateLumpSum = (field, value) => {
        const updated = { ...lumpSum, [field]: parseFloat(value) || 0 };
        setLumpSum(updated);
        saveToEngine(mode, detailedEntries, updated, remarks);
    };

    const saveToEngine = (newMode, entries, ls, rem) => {
        const detailedRows = entries.map((entry) => ({
            name: entry.name || '',
            source: entry.source || 'Diesel',
            rate: parseFloat(entry.rate) || 0,
            hrs: parseFloat(entry.hrs ?? entry.hours) || 0,
            days: parseFloat(entry.days) || 0,
            ef: parseFloat(entry.ef) || 0,
        }));
        const lumpsum = {
            elec_consumption_per_day: parseFloat(ls.elec_consumption_per_day ?? ls.elec_kwh_per_day) || 0,
            elec_days: parseFloat(ls.elec_days) || 0,
            elec_ef: parseFloat(ls.elec_ef) || 0,
            fuel_consumption_per_day: parseFloat(ls.fuel_consumption_per_day ?? ls.fuel_litres_per_day) || 0,
            fuel_days: parseFloat(ls.fuel_days) || 0,
            fuel_ef: parseFloat(ls.fuel_ef) || 0,
        };
        const desktopMode = newMode === 'lump_sum' ? 'lumpsum' : newMode;
        const total = desktopMode === 'detailed'
            ? computeMachineryDetailedTotal(detailedRows)
            : computeMachineryLumpsumTotal(lumpsum);
        const prev = projectData.carbon_emission_data || {};
        updateProjectData('carbon_emission_data', {
            ...prev,
            machinery_emissions_data: {
                mode: desktopMode,
                detailed: { rows: detailedRows },
                lumpsum,
                detailed_entries: entries,
                lump_sum: ls,
                remarks: rem,
                total_kgCO2e: total,
            }
        });
    };

    const detailedTotal = useMemo(() => {
        return computeMachineryDetailedTotal(detailedEntries);
    }, [detailedEntries]);

    const detailedDieselTotal = useMemo(() => {
        return detailedEntries.filter(e => e.source === 'Diesel').reduce((sum, e) => sum + (e.rate * (e.hrs ?? e.hours) * e.days * e.ef), 0);
    }, [detailedEntries]);

    const detailedElecTotal = useMemo(() => {
        return detailedEntries.filter(e => e.source.startsWith('Electricity')).reduce((sum, e) => sum + (e.rate * (e.hrs ?? e.hours) * e.days * e.ef), 0);
    }, [detailedEntries]);

    const lumpSumTotal = useMemo(() => {
        return computeMachineryLumpsumTotal({
            elec_consumption_per_day: lumpSum.elec_kwh_per_day,
            elec_days: lumpSum.elec_days,
            elec_ef: lumpSum.elec_ef,
            fuel_consumption_per_day: lumpSum.fuel_litres_per_day,
            fuel_days: lumpSum.fuel_days,
            fuel_ef: lumpSum.fuel_ef,
        });
    }, [lumpSum]);

    return (
        <div className="machinery-emissions carbon-desktop-page d-flex flex-column" style={{ backgroundColor: 'var(--app-bg-main)', fontFamily: '"Segoe UI", sans-serif', color: 'var(--app-text-primary)' }}>
            <style>{`
                .machinery-summary-bar {
                    background-color: var(--app-bg-card);
                    border: 1px solid var(--app-border-light);
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                .machinery-info-hint {
                    color: var(--app-text-muted);
                    font-size: 0.8rem;
                    font-style: italic;
                }
                .machinery-section-title {
                    font-size: 0.9rem;
                    font-weight: 700;
                    margin-bottom: 4px;
                    color: var(--app-text-primary);
                }
                .machinery-section-subtitle {
                    font-size: 0.75rem;
                    color: var(--app-text-secondary);
                    margin-bottom: 12px;
                }
                .machinery-qgroupbox {
                    background-color: var(--app-bg-card);
                    border: 1px solid var(--app-border-light);
                    border-radius: 4px;
                    padding: 12px;
                    margin-bottom: 16px;
                }
                .machinery-table-header {
                    font-size: 0.75rem;
                    color: var(--app-text-secondary);
                    font-weight: bold;
                    padding: 8px;
                    border-bottom: 1px solid var(--app-border-light);
                }
                .machinery-table-row {
                    background-color: var(--app-bg-card);
                    border: 1px solid var(--app-border-mid);
                    border-radius: 8px;
                    margin-bottom: 6px;
                    padding: 2px 4px;
                    transition: border-color 0.2s;
                }
                .machinery-table-row:hover {
                    border-color: #444;
                }
                .machinery-input-field {
                    background-color: var(--app-bg-alt);
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-primary);
                    border-radius: 6px;
                    font-size: 0.82rem;
                    padding: 6px 10px;
                    width: 100%;
                }
                .machinery-input-field:focus {
                    border-color: #9adc32;
                    outline: none;
                    box-shadow: 0 0 0 2px rgba(154, 205, 50, 0.25);
                }
                .unit-overlay {
                    position: absolute;
                    right: 12px;
                    top: 50%;
                    transform: translateY(-50%);
                    color: var(--app-text-muted);
                    font-size: 0.75rem;
                    pointer-events: none;
                }
                .machinery-divider {
                    height: 1px;
                    background: linear-gradient(to right, #444, transparent);
                    margin: 12px 0;
                    width: 100%;
                }
                .machinery-btn-secondary {
                    background-color: var(--app-bg-alt);
                    color: var(--app-text-primary);
                    border: 1px solid var(--app-border-mid);
                    font-size: 0.8rem;
                    padding: 6px 12px;
                    border-radius: 3px;
                }
                .machinery-btn-secondary:hover {
                    background-color: var(--app-bg-card);
                    border-color: #9adc32;
                }
                .custom-radio {
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    font-size: 0.85rem;
                }
                .custom-radio input {
                    accent-color: #9adc32;
                    width: 14px;
                    height: 14px;
                }
                .lump-sum-field-label {
                    font-size: 0.8rem;
                    font-weight: 600;
                    color: var(--app-text-primary);
                    margin-bottom: 2px;
                }
                .lump-sum-field-subtext {
                    font-size: 0.72rem;
                    color: var(--app-text-secondary);
                    margin-bottom: 6px;
                }
                .remarks-toolbar {
                    background-color: var(--app-bg-alt);
                    border: 1px solid var(--app-border-mid);
                    border-bottom: none;
                    border-radius: 4px 4px 0 0;
                    padding: 4px 8px;
                    display: flex;
                    gap: 12px;
                }
                .remarks-btn {
                    background: transparent;
                    border: none;
                    color: var(--app-text-muted);
                    font-size: 0.75rem;
                    padding: 2px 4px;
                }
                .remarks-btn:hover { color: var(--app-text-primary); }

            `}</style>

            <div className="carbon-summary-strip mb-3 d-flex justify-content-end">
                <strong>Total Machinery/Equipment Emissions: {(mode === 'detailed' ? detailedTotal : lumpSumTotal).toFixed(3)} kg CO₂e</strong>
            </div>

            {/* Mode Toggle Section */}
            <div className="mb-3 d-flex align-items-center gap-4">
                <span className="carbon-label mb-0">Input Method:</span>
                <div className="d-flex gap-4">
                    <label className="custom-radio" style={{ color: 'var(--app-text-primary)' }}>
                        <input type="radio" checked={mode === 'detailed'} onChange={() => { setMode('detailed'); saveToEngine('detailed', detailedEntries, lumpSum, remarks); }} />
                        Detailed Equipment List
                    </label>
                    <label className="custom-radio" style={{ color: 'var(--app-text-primary)' }}>
                        <input type="radio" checked={mode === 'lumpsum'} onChange={() => { setMode('lumpsum'); saveToEngine('lumpsum', detailedEntries, lumpSum, remarks); }} />
                        Lump Sum
                    </label>
                </div>
            </div>

            <div className="d-flex flex-column">
                {mode === 'detailed' ? (
                    <>
                        <div className="carbon-section-title">Detailed Equipment List</div>

                        {/* Grouped Table Header */}
                        <div className="machinery-table-header-container" style={{ border: '1px solid var(--app-border-mid)', borderRadius: '4px 4px 0 0', backgroundColor: 'var(--app-bg-alt)' }}>
                            <div className="row g-0 align-items-center text-center fw-bold" style={{ fontSize: '0.75rem', color: 'var(--app-text-secondary)', minHeight: '36px' }}>
                                <div className="col-3 border-end p-2 text-start">Equipment Name</div>
                                <div className="col-2 border-end p-2">Energy Source</div>
                                <div className="col-2 border-end p-2">Rating</div>
                                <div className="col-1 border-end p-2">Usage (Hrs/Day)</div>
                                <div className="col-1 border-end p-2">Days</div>
                                <div className="col-1 border-end p-2">EF</div>
                                <div className="col-2 p-2">Consumption</div>
                            </div>
                        </div>

                        {/* Table Content */}
                        <div className="machinery-table-body" style={{ border: '1px solid var(--app-border-mid)', borderTop: 'none', borderRadius: '0 0 4px 4px', backgroundColor: 'var(--app-bg-card)' }}>
                            {detailedEntries.map((e, idx) => (
                                <div key={idx} className="row g-0 align-items-center border-bottom" style={{ minHeight: '40px' }}>
                                    <div className="col-3 border-end px-2">
                                        <input 
                                            type="text" 
                                            className="bg-transparent border-0 w-100 text-light py-1"
                                            style={{ fontSize: '0.85rem', color: 'var(--app-text-primary)', outline: 'none' }}
                                            value={e.name}
                                            onChange={evt => handleUpdateEntry(idx, 'name', evt.target.value)}
                                        />
                                    </div>
                                    <div className="col-2 border-end px-2">
                                        <select 
                                            className="bg-transparent border-0 w-100 text-light py-1"
                                            style={{ fontSize: '0.82rem', color: 'var(--app-text-primary)', appearance: 'none', outline: 'none' }}
                                            value={e.source}
                                            onChange={evt => handleUpdateEntry(idx, 'source', evt.target.value)}
                                        >
                                            {ENERGY_SOURCES.map(s => <option key={s.label} value={s.label} style={{ backgroundColor: 'var(--app-bg-card)', color: 'var(--app-text-primary)' }}>{s.label}</option>)}
                                        </select>
                                    </div>
                                    <div className="col-2 border-end px-2 d-flex align-items-center">
                                        <input 
                                            type="number" 
                                            className="bg-transparent border-0 flex-grow-1 text-light py-1"
                                            style={{ fontSize: '0.85rem', color: 'var(--app-text-primary)', outline: 'none' }}
                                            value={e.rate}
                                            onChange={evt => handleUpdateEntry(idx, 'rate', parseFloat(evt.target.value) || 0)}
                                        />
                                        <span className="text-secondary small" style={{ color: 'var(--app-text-muted)', fontSize: '0.7rem' }}>
                                            {ENERGY_SOURCES.find(s => s.label === e.source)?.unit || 'u/hr'}
                                        </span>
                                    </div>
                                    <div className="col-1 border-end px-2">
                                        <input 
                                            type="number" 
                                            className="bg-transparent border-0 w-100 text-center text-light py-1"
                                            style={{ fontSize: '0.85rem', color: 'var(--app-text-primary)', outline: 'none' }}
                                            value={e.hours}
                                            onChange={evt => handleUpdateEntry(idx, 'hours', parseFloat(evt.target.value) || 0)}
                                        />
                                    </div>
                                    <div className="col-1 border-end px-2">
                                        <input 
                                            type="number" 
                                            className="bg-transparent border-0 w-100 text-center text-light py-1"
                                            style={{ fontSize: '0.85rem', color: 'var(--app-text-primary)', outline: 'none' }}
                                            value={e.days}
                                            onChange={evt => handleUpdateEntry(idx, 'days', parseFloat(evt.target.value) || 0)}
                                        />
                                    </div>
                                    <div className="col-1 border-end px-2">
                                        <input 
                                            type="number" 
                                            className="bg-transparent border-0 w-100 text-center text-light py-1"
                                            style={{ fontSize: '0.85rem', color: 'var(--app-text-primary)', outline: 'none' }}
                                            value={e.ef}
                                            onChange={evt => handleUpdateEntry(idx, 'ef', parseFloat(evt.target.value) || 0)}
                                        />
                                    </div>
                                    <div className="col-2 px-2 d-flex align-items-center justify-content-between">
                                        <span className="fw-bold flex-grow-1 text-center" style={{ color: 'var(--app-text-primary)', fontSize: '0.85rem' }}>
                                            {(e.rate * (e.hrs ?? e.hours) * e.days * e.ef).toFixed(3)}
                                        </span>
                                        <button className="btn btn-link btn-sm text-danger p-0" title="Delete Row" onClick={() => handleDeleteEntry(idx)}>
                                            <i className="bi bi-trash"></i>
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* Statistical Summary & Action Buttons */}
                        <div className="d-flex flex-column mb-3">
                            {/* Top Stats Row: Diesel, Electricity, Subtotal */}
                            <div className="d-flex justify-content-between mb-2 px-1" style={{ fontSize: '12px', color: 'var(--app-text-primary)' }}>
                                <div className="d-flex gap-4">
                                    <span>Diesel: <span className="fw-bold">{detailedDieselTotal.toFixed(3)} kg CO₂e</span></span>
                                    <span>Electricity: <span className="fw-bold">{detailedElecTotal.toFixed(3)} kg CO₂e</span></span>
                                </div>
                                <div className="fw-bold">
                                    Subtotal: {detailedTotal.toFixed(3)} kg CO₂e
                                </div>
                            </div>

                            {/* Action Buttons Row */}
                            <div className="d-flex align-items-center gap-2">
                                <button className="machinery-btn-secondary px-3" style={{ fontSize: '13px' }} onClick={() => handleAddEntry()}>+ Add Equipment</button>
                                <button className="machinery-btn-secondary px-3" style={{ fontSize: '13px' }} onClick={handleLoadDefaults}>Load Defaults</button>
                                <button className="machinery-btn-secondary px-3" style={{ fontSize: '13px' }} onClick={handleClearAll}>Clear All</button>
                                
                                <div className="d-flex align-items-center gap-2 ms-2">
                                    <div className="position-relative" style={{ width: '80px' }}>
                                        <input 
                                            type="number" 
                                            className="machinery-input-field pe-4 py-1" 
                                            style={{ fontSize: '12px' }}
                                            value={applyDaysVal}
                                            onChange={e => setApplyDaysVal(parseInt(e.target.value) || 0)}
                                        />
                                        <span className="position-absolute end-0 top-50 translate-middle-y pe-2 text-secondary" style={{ fontSize: '10px' }}>d</span>
                                    </div>
                                    <button className="machinery-btn-secondary px-3" style={{ fontSize: '13px' }} onClick={handleApplyDays}>Apply Days to All Rows</button>
                                </div>
                            </div>
                        </div>
                    </>
                ) : (
                    <div className="pe-2 pb-4">
                        <div className="carbon-section-title">Lump Sum</div>
                        {/* Electricity Section */}
                        <div className="mb-4">
                            <div className="machinery-section-title">Electricity Consumption</div>
                            <div className="machinery-divider"></div>

                            <div className="mb-3">
                                <div className="lump-sum-field-label">Electricity Consumption per Day</div>
                                <div className="lump-sum-field-subtext">Total electricity consumed per working day across all equipment.</div>
                                <div className="position-relative" style={{ maxWidth: '400px' }}>
                                    <input 
                                        type="number" 
                                        className="machinery-input-field" 
                                        style={{ borderLeft: '3px solid #9adc32' }}
                                        value={lumpSum.elec_kwh_per_day}
                                        onChange={e => handleUpdateLumpSum('elec_kwh_per_day', e.target.value)}
                                    />
                                    <span className="position-absolute end-0 top-50 translate-middle-y pe-2 text-secondary small">kWh/day</span>
                                </div>
                            </div>

                            <div className="mb-3">
                                <div className="lump-sum-field-label">Number of Days</div>
                                <div className="lump-sum-field-subtext">Total number of working days for electricity consumption.</div>
                                <div className="position-relative" style={{ maxWidth: '400px' }}>
                                    <input 
                                        type="number" 
                                        className="machinery-input-field" 
                                        value={lumpSum.elec_days}
                                        onChange={e => handleUpdateLumpSum('elec_days', e.target.value)}
                                    />
                                    <span className="position-absolute end-0 top-50 translate-middle-y pe-2 text-secondary small">days</span>
                                </div>
                            </div>

                            <div className="mb-3">
                                <div className="lump-sum-field-label">Emission Factor</div>
                                <div className="lump-sum-field-subtext">Grid electricity emission factor (kg CO₂e per kWh).</div>
                                <div className="position-relative" style={{ maxWidth: '400px' }}>
                                    <input 
                                        type="number" 
                                        className="machinery-input-field" 
                                        value={lumpSum.elec_ef}
                                        onChange={e => handleUpdateLumpSum('elec_ef', e.target.value)}
                                    />
                                    <span className="position-absolute end-0 top-50 translate-middle-y pe-2 text-secondary small">kg CO₂e/kWh</span>
                                </div>
                            </div>
                        </div>

                        {/* Fuel Section */}
                        <div className="mb-2">
                            <div className="machinery-section-title">Fuel (Diesel) Consumption</div>
                            <div className="machinery-divider"></div>

                            <div className="mb-3">
                                <div className="lump-sum-field-label">Fuel Consumption per Day</div>
                                <div className="lump-sum-field-subtext">Total diesel/fuel consumed per working day across all equipment.</div>
                                <div className="position-relative" style={{ maxWidth: '400px' }}>
                                    <input 
                                        type="number" 
                                        className="machinery-input-field" 
                                        value={lumpSum.fuel_litres_per_day}
                                        onChange={e => handleUpdateLumpSum('fuel_litres_per_day', e.target.value)}
                                    />
                                    <span className="position-absolute end-0 top-50 translate-middle-y pe-2 text-secondary small">litres/day</span>
                                </div>
                            </div>

                            <div className="mb-3">
                                <div className="lump-sum-field-label">Number of Days</div>
                                <div className="lump-sum-field-subtext">Total number of working days for fuel consumption.</div>
                                <div className="position-relative" style={{ maxWidth: '400px' }}>
                                    <input 
                                        type="number" 
                                        className="machinery-input-field" 
                                        value={lumpSum.fuel_days}
                                        onChange={e => handleUpdateLumpSum('fuel_days', e.target.value)}
                                    />
                                    <span className="position-absolute end-0 top-50 translate-middle-y pe-2 text-secondary small">days</span>
                                </div>
                            </div>

                            <div className="mb-3">
                                <div className="lump-sum-field-label">Emission Factor</div>
                                <div className="lump-sum-field-subtext">Diesel emission factor (kg CO₂e per litre).</div>
                                <div className="position-relative" style={{ maxWidth: '400px' }}>
                                    <input 
                                        type="number" 
                                        className="machinery-input-field" 
                                        style={{ borderLeft: '3px solid #9adc32' }}
                                        value={lumpSum.fuel_ef}
                                        onChange={e => handleUpdateLumpSum('fuel_ef', e.target.value)}
                                    />
                                    <span className="position-absolute end-0 top-50 translate-middle-y pe-2 text-secondary small">kg CO₂e/litre</span>
                                </div>
                            </div>
                        </div>

                        <div className="text-end fw-bold mb-3" style={{ fontSize: '0.9rem' }}>
                            Lump Sum Subtotal: <span style={{ color: '#9adc32' }}>{lumpSumTotal.toFixed(3)}</span> kg CO₂e
                        </div>
                    </div>
                )}
            </div>

            {/* Final Total Summary - Full Width Box */}
            <div className="mb-3">
                <div className="carbon-summary-strip d-flex justify-content-end align-items-center">
                    <div className="fw-bold" style={{ fontSize: '13px', color: 'var(--app-text-primary)' }}>
                        Total Machinery/Equipment Emissions: {(mode === 'detailed' ? detailedTotal : lumpSumTotal).toFixed(3)} kg CO₂e
                    </div>
                </div>
            </div>

            {/* Remarks Section */}
            <div className="pb-3">
                <div className="carbon-section-title">Remarks / Notes</div>
                <div className="remarks-toolbar">
                    <button className="remarks-btn fw-bold">B</button>
                    <button className="remarks-btn fst-italic">I</button>
                    <button className="remarks-btn text-decoration-underline">U</button>
                    <button className="remarks-btn text-decoration-line-through">S</button>
                    <div className="vr mx-1" style={{ height: '14px', alignSelf: 'center', backgroundColor: 'var(--app-border-mid)' }}></div>
                    <button className="remarks-btn">Left</button>
                    <button className="remarks-btn">Center</button>
                    <button className="remarks-btn">Right</button>
                    <button className="remarks-btn">Justify</button>
                    <div className="vr mx-1" style={{ height: '14px', alignSelf: 'center', backgroundColor: '#555' }}></div>
                    <button className="remarks-btn">• List</button>
                    <button className="remarks-btn">1. List</button>
                    <div className="vr mx-1" style={{ height: '14px', alignSelf: 'center', backgroundColor: '#555' }}></div>
                    <button className="remarks-btn">+ Table</button>
                    <button className="remarks-btn">+ Row</button>
                    <button className="remarks-btn">+ Col</button>
                    <button className="remarks-btn" onClick={() => { setRemarks(''); saveToEngine(mode, detailedEntries, lumpSum, ''); }}>Clear</button>
                </div>
                <textarea 
                    className="w-100 p-3 bg-transparent text-light border-secondary-subtle rounded-bottom" 
                    rows="4" 
                    placeholder="Add notes or remarks here. These will appear in the generated report."
                    style={{ fontSize: '0.85rem', resize: 'none', border: '1px solid var(--app-border-mid)', backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-primary)' }}
                    value={remarks}
                    onChange={e => { setRemarks(e.target.value); saveToEngine(mode, detailedEntries, lumpSum, e.target.value); }}
                ></textarea>
            </div>
        </div>
    );
};

export default MachineryEmissions;

/* eslint-disable react-hooks/exhaustive-deps */
/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useMemo, useState } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import { computeTrafficReroutingData, formatNumber, parseNumber, VEHICLE_TYPES } from './carbonUtils';

const defaultFactors = () => VEHICLE_TYPES.reduce((acc, vehicle) => ({
    ...acc,
    [vehicle.key]: vehicle.defaultEf,
}), {});

const TrafficEmissions = () => {
    const { projectData, updateProjectData } = useProjectData();
    const computedContext = useMemo(() => computeTrafficReroutingData(projectData), [projectData]);
    const [factors, setFactors] = useState(computedContext.emission_factors || defaultFactors());
    const [directEntry, setDirectEntry] = useState(computedContext.direct_entry || { total_direct_emissions: 0, source: '', comments: '' });
    const [remarks, setRemarks] = useState(computedContext.remarks || '');

    useEffect(() => {
        setFactors(computedContext.emission_factors || defaultFactors());
        setDirectEntry(computedContext.direct_entry || { total_direct_emissions: 0, source: '', comments: '' });
        setRemarks(computedContext.remarks || '');
    }, [computedContext.mode]);

    const vehicles = projectData.traffic_data?.vehicles || projectData.traffic_data?.vehicle_data || {};
    const totalCalculated = VEHICLE_TYPES.reduce((sum, vehicle) => {
        const row = vehicles[vehicle.key] || {};
        return sum + parseNumber(row.vehicles_per_day ?? row.adt ?? row.ADT) *
            parseNumber(computedContext.reroute_km) *
            parseNumber(factors[vehicle.key]);
    }, 0);

    const totalPerDay = computedContext.mode === 'Calculate by Vehicle'
        ? totalCalculated
        : parseNumber(directEntry.total_direct_emissions);

    const saveData = (nextFactors = factors, nextDirect = directEntry, nextRemarks = remarks) => {
        const prev = projectData.carbon_emission_data || {};
        const total = computedContext.mode === 'Calculate by Vehicle'
            ? VEHICLE_TYPES.reduce((sum, vehicle) => {
                const row = vehicles[vehicle.key] || {};
                return sum + parseNumber(row.vehicles_per_day ?? row.adt ?? row.ADT) *
                    parseNumber(computedContext.reroute_km) *
                    parseNumber(nextFactors[vehicle.key]);
            }, 0)
            : parseNumber(nextDirect.total_direct_emissions);
        const next = {
            mode: computedContext.mode,
            webMode: computedContext.mode === 'Calculate by Vehicle' ? 'calculate' : 'direct',
            emission_factors: nextFactors,
            factors: nextFactors,
            reroute_km: computedContext.reroute_km,
            total_calculated_emissions: computedContext.mode === 'Calculate by Vehicle' ? total : 0,
            total_direct_emissions: computedContext.mode === 'Enter Directly' ? total : 0,
            direct_entry: {
                total_direct_emissions: parseNumber(nextDirect.total_direct_emissions),
                source: nextDirect.source || '',
                comments: nextDirect.comments || '',
            },
            remarks: nextRemarks,
            total_kgCO2e_per_day: total,
        };
        updateProjectData('carbon_emission_data', {
            ...prev,
            diversion_emissions_data: next,
            diversion_emissions: next,
        });
    };

    useEffect(() => {
        saveData(factors, directEntry, remarks);
    }, [computedContext.mode, computedContext.reroute_km, totalCalculated, totalPerDay]);

    const updateFactor = (key, value) => {
        const nextFactors = { ...factors, [key]: parseNumber(value) };
        setFactors(nextFactors);
        saveData(nextFactors, directEntry, remarks);
    };

    const updateDirect = (field, value) => {
        const nextDirect = { ...directEntry, [field]: value };
        setDirectEntry(nextDirect);
        saveData(factors, nextDirect, remarks);
    };

    const updateRemarks = (value) => {
        setRemarks(value);
        saveData(factors, directEntry, value);
    };

    const clearAll = () => {
        const clearedFactors = defaultFactors();
        const clearedDirect = { total_direct_emissions: 0, source: '', comments: '' };
        setFactors(clearedFactors);
        setDirectEntry(clearedDirect);
        setRemarks('');
        saveData(clearedFactors, clearedDirect, '');
    };

    return (
        <div className="traffic-emissions carbon-desktop-page">
            <div className="carbon-field" style={{ maxWidth: 360 }}>
                <label className="carbon-label">Calculation Mode</label>
                <div className="carbon-help">Locked from Traffic Data: India mode calculates by vehicle, global mode uses direct entry.</div>
                <select className="form-select form-select-sm" value={computedContext.mode} disabled>
                    <option>Calculate by Vehicle</option>
                    <option>Enter Directly</option>
                </select>
            </div>

            {computedContext.mode === 'Calculate by Vehicle' ? (
                <>
                    <div className="carbon-summary-strip mb-3">
                        Reroute Distance (from Traffic Data): <strong>{formatNumber(computedContext.reroute_km, 2)}</strong> km
                    </div>
                    {parseNumber(computedContext.reroute_km) === 0 && (
                        <div className="alert alert-warning py-2">Reroute distance is 0 km. Please fill in the Traffic Data tab first.</div>
                    )}
                    <div className="carbon-section-title">Vehicle Emission Factors</div>
                    <div className="table-responsive mb-3">
                        <table className="table table-sm table-dark carbon-desktop-table mb-0">
                            <thead>
                                <tr>
                                    <th>Vehicle Type</th>
                                    <th className="text-end">Vehicles / Day</th>
                                    <th className="text-end">Emission Factor (kgCO₂e / veh-km)</th>
                                    <th className="text-end">Emissions (kgCO2e/day)</th>
                                </tr>
                            </thead>
                            <tbody>
                                {VEHICLE_TYPES.map((vehicle) => {
                                    const row = vehicles[vehicle.key] || {};
                                    const vpd = parseNumber(row.vehicles_per_day ?? row.adt ?? row.ADT);
                                    const subtotal = vpd * parseNumber(computedContext.reroute_km) * parseNumber(factors[vehicle.key]);
                                    return (
                                        <tr key={vehicle.key}>
                                            <td>{vehicle.label}</td>
                                            <td className="text-end font-monospace">{vpd}</td>
                                            <td className="text-end">
                                                <input
                                                    className="form-control form-control-sm text-end"
                                                    type="number"
                                                    step="0.0001"
                                                    value={factors[vehicle.key] ?? 0}
                                                    onChange={(event) => updateFactor(vehicle.key, event.target.value)}
                                                />
                                            </td>
                                            <td className="text-end font-monospace">{formatNumber(subtotal)}</td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                    <div className="carbon-summary-strip text-end fw-bold mb-3">Total Daily Emissions: {formatNumber(totalCalculated)} kgCO2e/day</div>
                    <button className="btn btn-sm btn-outline-light mb-3" onClick={() => {
                        const next = defaultFactors();
                        setFactors(next);
                        saveData(next, directEntry, remarks);
                    }}>
                        Load Default Factors
                    </button>
                </>
            ) : (
                <div className="mb-3">
                    <div className="carbon-section-title">Direct Entry</div>
                    <div className="carbon-field">
                        <label className="carbon-label">Total Traffic Rerouting Emissions</label>
                        <div className="input-group input-group-sm">
                            <input
                                className="form-control"
                                type="number"
                                value={directEntry.total_direct_emissions}
                                onChange={(event) => updateDirect('total_direct_emissions', event.target.value)}
                            />
                            <span className="input-group-text">kgCO2e/day</span>
                        </div>
                    </div>
                    <div className="carbon-field">
                        <label className="carbon-label">Source</label>
                        <input className="form-control form-control-sm mb-3" value={directEntry.source} onChange={(event) => updateDirect('source', event.target.value)} />
                    </div>
                    <div className="carbon-field">
                        <label className="carbon-label">Comments</label>
                        <textarea className="form-control mb-3" rows="3" value={directEntry.comments} onChange={(event) => updateDirect('comments', event.target.value)} />
                    </div>
                </div>
            )}

            <div className="mb-3">
                <div className="carbon-section-title">Notes</div>
                <textarea className="form-control" rows="4" value={remarks} onChange={(event) => updateRemarks(event.target.value)} />
            </div>

            <button className="btn btn-sm btn-outline-light w-100 mb-3" onClick={clearAll}>Clear All</button>
            <div className="carbon-summary-strip text-end fw-bold">
                Total Traffic Rerouting Emissions: {formatNumber(totalPerDay)} kgCO2e/day
            </div>
        </div>
    );
};

export default TrafficEmissions;

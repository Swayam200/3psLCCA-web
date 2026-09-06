import { useMemo, useState } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import { computeMaterialEmissions, formatNumber, STRUCTURE_CHUNKS } from './carbonUtils';

const MaterialEmissions = () => {
    const { projectData, updateProjectData } = useProjectData();
    const [searchTerm, setSearchTerm] = useState('');
    const [detailsVisible, setDetailsVisible] = useState(false);

    // Display-only derivation. The persisted material_emissions_data is
    // maintained by normalizeCarbonEmissionData on every project write and by
    // deriveCarbonEmissionData at calculation time — writing this view-model
    // back from an effect fought the normalizer's shape and looped React
    // ("Maximum update depth exceeded", which froze sidebar navigation).
    const computed = useMemo(() => computeMaterialEmissions(projectData), [projectData]);

    const updateMaterialState = (materialId, include) => {
        const row = computed.rows.find((item) => item.id === materialId);
        if (!row) return;
        const sections = Array.isArray(projectData[row.chunkId]) ? projectData[row.chunkId] : [];
        const nextSections = sections.map((section) => ({
            ...section,
            rows: (section.rows || []).map((item) => {
                if ((item.id || '') !== row.rowId) return item;
                return {
                    ...item,
                    state: {
                        ...(item.state || {}),
                        included_in_carbon_emission: include,
                    },
                };
            }),
        }));
        updateProjectData(row.chunkId, nextSections);

        const prev = projectData.carbon_emission_data || {};
        const currentExcluded = new Set(prev.material_emissions_data?.excluded_ids || []);
        if (include) currentExcluded.delete(materialId);
        else currentExcluded.add(materialId);
        updateProjectData('carbon_emission_data', {
            ...prev,
            material_emissions_data: {
                ...(prev.material_emissions_data || {}),
                excluded_ids: Array.from(currentExcluded),
            },
        });
    };

    const matchesSearch = (row) => {
        const term = searchTerm.trim().toLowerCase();
        if (!term) return true;
        return [row.name, row.category, row.sectionName, row.unit]
            .some((value) => String(value || '').toLowerCase().includes(term));
    };

    const included = computed.includedRows.filter(matchesSearch);
    const excluded = computed.excludedRows.filter(matchesSearch);

    const renderRows = (rows, isIncluded) => (
        <div className="table-responsive mb-4">
            <table className="table table-sm table-dark carbon-desktop-table mb-0">
                <thead>
                    <tr>
                        <th rowSpan="2">Category</th>
                        <th rowSpan="2">Material</th>
                        <th colSpan="2" className="text-center">Quantity</th>
                        <th rowSpan="2" className="text-end">Conversion Factor</th>
                        <th colSpan="2" className="text-center">Emission</th>
                        <th rowSpan="2" className="text-end">Total Emissions (kgCO2e)</th>
                        <th rowSpan="2">{isIncluded ? 'Warning' : 'Reason'}</th>
                        <th rowSpan="2" className="text-center">Action</th>
                    </tr>
                    <tr>
                        <th className="text-end">Value</th>
                        <th>Unit</th>
                        <th className="text-end">Value</th>
                        <th>Unit</th>
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row) => (
                        <tr key={row.id} className={!isIncluded ? 'opacity-75' : ''}>
                            <td>{row.category}</td>
                            <td>
                                <div className="fw-semibold">{row.name}</div>
                                {row.sectionName && <div className="text-secondary small">{row.sectionName}</div>}
                            </td>
                            <td className="text-end font-monospace">{formatNumber(row.quantity)}</td>
                            <td>{row.unit || '-'}</td>
                            <td className="text-end font-monospace">{formatNumber(row.conversion_factor)}</td>
                            <td className="text-end font-monospace">{formatNumber(row.emission_factor)}</td>
                            <td>{row.emission_unit || '-'}</td>
                            <td className="text-end font-monospace fw-semibold">{isIncluded ? formatNumber(row.total_kgCO2e) : '-'}</td>
                            <td className="text-secondary small">
                                {isIncluded ? (row.warning || '') : row.reason}
                                {!isIncluded && row.reason === 'Unit mismatch' && (
                                    <div className="text-warning" style={{ fontSize: '0.75rem' }}>{row.conversion_note} Edit the material on its construction page.</div>
                                )}
                            </td>
                            <td className="text-center">
                                <button
                                    className={`btn btn-sm ${isIncluded ? 'btn-outline-danger' : 'btn-outline-success'}`}
                                    title={isIncluded ? 'Exclude from calculation' : 'Include in calculation'}
                                    onClick={() => updateMaterialState(row.id, !isIncluded)}
                                    disabled={!isIncluded && (row.reason === 'Incomplete Data' || row.reason === 'Unit mismatch')}
                                >
                                    <i className={`bi ${isIncluded ? 'bi-trash' : 'bi-plus-lg'}`} />
                                </button>
                            </td>
                        </tr>
                    ))}
                    {rows.length === 0 && (
                        <tr>
                            <td colSpan="10" className="text-center text-secondary py-4">No materials found</td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );

    return (
        <div className="material-emissions carbon-desktop-page">
            <div className="carbon-summary-strip mb-3 d-flex align-items-center justify-content-between gap-3">
                <div className="d-flex gap-4 flex-wrap" style={{ fontSize: '0.84rem' }}>
                    <span>Total Material Emissions: <strong>{formatNumber(computed.total_kgCO2e)}</strong> kgCO2e</span>
                    <span>Included: <strong>{computed.included_count}</strong> of <strong>{computed.total_count}</strong> items</span>
                </div>
                <button className="btn btn-sm btn-outline-light" onClick={() => setDetailsVisible((value) => !value)}>
                    {detailsVisible ? 'Hide Details ▲' : 'Show Details ▼'}
                </button>
            </div>

            {detailsVisible && (
                <div className="carbon-summary-strip mb-3 d-flex gap-4 flex-wrap" style={{ fontSize: '0.8rem' }}>
                    {STRUCTURE_CHUNKS.map(([, label]) => (
                        <span key={label}>{label}: <strong>{formatNumber(computed.cat_totals[label] || 0)}</strong></span>
                    ))}
                </div>
            )}

            <div className="carbon-field" style={{ maxWidth: 360 }}>
                <label className="carbon-label">Search Materials</label>
                <input
                    className="form-control form-control-sm"
                    placeholder="Search materials..."
                    value={searchTerm}
                    onChange={(event) => setSearchTerm(event.target.value)}
                />
            </div>

            <div className="carbon-section-title">Included in Carbon Emissions Calculation</div>
            {renderRows(included, true)}

            <div className="carbon-section-title">Excluded from Carbon Emissions Calculation</div>
            {renderRows(excluded, false)}
        </div>
    );
};

export default MaterialEmissions;

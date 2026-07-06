import { useEffect, useMemo, useState } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import { computeMaterialEmissions, formatNumber, STRUCTURE_CHUNKS } from './carbonUtils';

const MaterialEmissions = () => {
    const { projectData, updateProjectData } = useProjectData();
    const [searchTerm, setSearchTerm] = useState('');
    const [detailsVisible, setDetailsVisible] = useState(false);

    const computed = useMemo(() => computeMaterialEmissions(projectData), [projectData]);
    const serializeRow = (row) => {
        const next = { ...row };
        delete next.raw;
        return next;
    };

    useEffect(() => {
        const prev = projectData.carbon_emission_data || {};
        const nextMaterialData = {
            ...(prev.material_emissions_data || {}),
            rows: computed.rows.map(serializeRow),
            included_items: computed.includedRows.map(serializeRow),
            excluded_items: computed.excludedRows.map(serializeRow),
            excluded_ids: computed.excluded_ids,
            category_totals: computed.cat_totals,
            cat_totals: computed.cat_totals,
            total_kgCO2e: computed.total_kgCO2e,
            included_count: computed.included_count,
            total_count: computed.total_count,
        };
        if (JSON.stringify(prev.material_emissions_data || {}) === JSON.stringify(nextMaterialData)) return;
        updateProjectData('carbon_emission_data', {
            ...prev,
            material_emissions_data: nextMaterialData,
        });
    }, [computed, projectData.carbon_emission_data, updateProjectData]);

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
                            <td className="text-secondary small">{isIncluded ? (row.warning || '') : row.reason}</td>
                            <td className="text-center">
                                <button
                                    className={`btn btn-sm ${isIncluded ? 'btn-outline-danger' : 'btn-outline-success'}`}
                                    title={isIncluded ? 'Exclude from calculation' : 'Include in calculation'}
                                    onClick={() => updateMaterialState(row.id, !isIncluded)}
                                    disabled={!isIncluded && row.reason === 'Incomplete Data'}
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

/**
 * Recycling page — desktop parity (gui/components/recycling/main.py).
 *
 * Everything here is DERIVED from the construction material rows: each row
 * carries a recyclability % and scrap rate (from the material database or
 * user edits), and Recovered Value = quantity × recyclability%/100 × scrap
 * rate. The recycling_data chunk only stores the computed summary; manual
 * include/exclude lives on the row itself (state.included_in_recyclability),
 * exactly like desktop. The calculation recomputes this at "Calculate" time
 * regardless of whether this page was ever opened.
 */
import { useEffect, useMemo, useState } from 'react';
import { FaChevronDown, FaChevronUp, FaEdit } from 'react-icons/fa';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import {
    computeRecycling,
    calcRecyclableQty,
    recyclePct,
    recyclingChunkData,
    rowName,
    rowQuantity,
    rowUnit,
    scrapRate,
} from '../../../utils/recyclingDerivations';
import EditRecyclabilityModal from './EditRecyclabilityModal';

const fmt = (value, digits = 3) => new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: digits > 0 ? Math.min(digits, 3) : 0,
    maximumFractionDigits: digits,
}).format(value);

const Recycling = () => {
    const { projectData, updateProjectData } = useProjectData();
    const [editingItem, setEditingItem] = useState(null);

    const computed = useMemo(() => computeRecycling(projectData), [projectData]);
    const currency = projectData.general_info?.project_currency || projectData.currency || 'INR';

    // Persist the derived summary (desktop get_data) whenever it changes so
    // saved projects and the report always carry the current totals.
    useEffect(() => {
        const summary = recyclingChunkData(projectData, currency);
        const saved = projectData.recycling_data || {};
        if (Math.abs((saved.total_recovered_value ?? -1) - summary.total_recovered_value) > 1e-9
            || saved.included_count !== summary.included_count
            || saved.total_count !== summary.total_count) {
            updateProjectData('recycling_data', { ...saved, ...summary });
        }
    }, [projectData, currency, updateProjectData]);

    /** Update one material row inside its structure section chunk. */
    const updateRow = (item, mutate) => {
        const sections = projectData[item.sectionKey];
        if (!Array.isArray(sections)) return;
        const nextSections = sections.map((section) => {
            if (section.id !== item.sectionId) return section;
            return {
                ...section,
                rows: (section.rows || []).map((row) => (row.id === item.row.id ? mutate(row) : row)),
            };
        });
        updateProjectData(item.sectionKey, nextSections);
    };

    const setIncludedFlag = (item, included) => updateRow(item, (row) => ({
        ...row,
        state: { ...(row.state || {}), included_in_recyclability: included },
    }));

    const handleModalSave = (saved) => {
        const item = saved.__item;
        if (!item) return;
        const pct = parseFloat(String(saved.recoveryPercent).replace(/,/g, ''));
        const rate = parseFloat(String(saved.scrapRate).replace(/,/g, ''));
        updateRow(item, (row) => ({
            ...row,
            ...(Number.isFinite(rate) ? { scrapRate: rate } : {}),
            ...(Number.isFinite(pct) ? { postDemolitionRecoveryPercentage: pct } : {}),
            values: {
                ...(row.values || {}),
                ...(Number.isFinite(rate) ? { scrap_rate: rate } : {}),
                ...(Number.isFinite(pct) ? { post_demolition_recovery_percentage: pct } : {}),
            },
        }));
    };

    const headerStyle = {
        padding: '10px 16px',
        borderBottom: '1px solid var(--app-border-mid)',
        color: 'var(--app-text-secondary)',
        fontSize: '0.85rem',
        fontWeight: 'bold',
        backgroundColor: 'var(--app-bg-card)',
    };

    const cellStyle = {
        padding: '10px 16px',
        borderBottom: '1px solid var(--app-border-light)',
        fontSize: '0.85rem',
        color: 'var(--app-text-primary)',
        verticalAlign: 'middle',
    };

    const modalItem = editingItem && (() => {
        const row = editingItem.row;
        const values = row.values || {};
        const emission = row.carbonEmission || {};
        const orBlank = (value) => (value === undefined || value === null ? '' : String(value));
        return {
            __item: editingItem,
            material: rowName(row),
            qtyValue: String(rowQuantity(row)),
            qtyUnit: rowUnit(row),
            rateCost: orBlank(row.rate ?? values.rate),
            rateSource: orBlank(row.source ?? values.rate_source),
            emissionFactor: orBlank(emission.factor ?? values.carbon_emission),
            perUnit: orBlank(emission.perUnit ?? values.carbon_unit),
            conversionFactor: orBlank(row.conversionFactor ?? values.conversion_factor ?? 1),
            currency,
            scrapRate: scrapRate(row) ? String(scrapRate(row)) : '',
            recoveryPercent: recyclePct(row) ? String(recyclePct(row)) : '',
            recyclability: recyclePct(row) ? String(recyclePct(row)) : '',
        };
    })();

    return (
        <div className="h-100 d-flex flex-column overflow-hidden" style={{ backgroundColor: 'var(--app-bg-main)', color: 'var(--app-text-primary)' }}>
            {/* Header Area */}
            <div className="d-flex align-items-center justify-content-between p-3 border-bottom" style={{ backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-light) !important' }}>
                <div className="d-flex gap-4">
                    <span>
                        Total Recovered Value ({currency}):{' '}
                        <strong data-testid="recycling-total">{fmt(computed.totalRecoveredValue)}</strong>
                    </span>
                    <span className="text-muted">Included: {computed.includedCount} of {computed.totalCount} items</span>
                </div>
            </div>

            <div className="flex-grow-1 overflow-auto p-3 custom-scrollbar">
                {computed.totalCount === 0 && (
                    <div className="text-muted p-3">
                        No materials are available for recycling calculations — add material
                        entries in the Construction Work Data section first.
                    </div>
                )}

                {/* Included Table */}
                <h6 className="mb-3 mt-2 fw-bold">Included in Recyclability</h6>
                <div className="table-responsive rounded border border-secondary mb-4" style={{ backgroundColor: 'var(--app-bg-card)' }}>
                    <table className="table table-borderless table-hover m-0" style={{ '--bs-table-bg': 'transparent' }}>
                        <thead>
                            <tr>
                                <th style={headerStyle}>Category</th>
                                <th style={headerStyle}>Material</th>
                                <th style={headerStyle} className="text-end">Qty</th>
                                <th style={headerStyle}>Unit</th>
                                <th style={headerStyle} className="text-end">Recyclability %</th>
                                <th style={headerStyle} className="text-end">Recyclable Qty</th>
                                <th style={headerStyle} className="text-end">Scrap Rate ({currency})</th>
                                <th style={headerStyle} className="text-end">Recovered Value ({currency})</th>
                                <th style={headerStyle} className="text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {computed.includedItems.map((item) => (
                                <tr key={item.row.id}>
                                    <td style={cellStyle}>{item.category} — {item.sectionName}</td>
                                    <td style={cellStyle}>{rowName(item.row)}</td>
                                    <td style={cellStyle} className="text-end">{fmt(rowQuantity(item.row))}</td>
                                    <td style={cellStyle}>{rowUnit(item.row)}</td>
                                    <td style={cellStyle} className="text-end">{fmt(recyclePct(item.row), 2)}</td>
                                    <td style={cellStyle} className="text-end">{fmt(calcRecyclableQty(item.row))}</td>
                                    <td style={cellStyle} className="text-end">{fmt(scrapRate(item.row), 2)}</td>
                                    <td style={cellStyle} className="text-end">{fmt(item.value, 2)}</td>
                                    <td style={cellStyle} className="text-center">
                                        <div className="d-flex justify-content-center gap-3">
                                            <button type="button" className="btn btn-link p-0" aria-label={`Edit recyclability for ${rowName(item.row)}`} title="Edit recyclability" onClick={() => setEditingItem(item)} style={{ color: 'var(--app-text-muted)', lineHeight: 1 }}><FaEdit aria-hidden="true" /></button>
                                            <button type="button" className="btn btn-link p-0" aria-label={`Exclude ${rowName(item.row)} from the recycling calculation`} title="Exclude from calculation" onClick={() => setIncludedFlag(item, false)} style={{ color: '#dc3545', lineHeight: 1 }}><FaChevronDown aria-hidden="true" /></button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Excluded Table */}
                <h6 className="mb-3 mt-4 fw-bold">Excluded from Recyclability</h6>
                <div className="table-responsive rounded border border-secondary" style={{ backgroundColor: 'var(--app-bg-card)', marginBottom: '50px' }}>
                    <table className="table table-borderless table-hover m-0" style={{ '--bs-table-bg': 'transparent' }}>
                        <thead>
                            <tr>
                                <th style={headerStyle}>Category</th>
                                <th style={headerStyle}>Material</th>
                                <th style={headerStyle} className="text-end">Qty</th>
                                <th style={headerStyle}>Unit</th>
                                <th style={headerStyle} className="text-end">Recyclability %</th>
                                <th style={headerStyle} className="text-end">Scrap Rate</th>
                                <th style={headerStyle}>Reason</th>
                                <th style={headerStyle} className="text-center">Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {computed.excludedItems.map((item) => (
                                <tr key={item.row.id}>
                                    <td style={cellStyle}>{item.category} — {item.sectionName}</td>
                                    <td style={cellStyle}>{rowName(item.row)}</td>
                                    <td style={cellStyle} className="text-end">{fmt(rowQuantity(item.row))}</td>
                                    <td style={cellStyle}>{rowUnit(item.row)}</td>
                                    <td style={cellStyle} className="text-end">{fmt(recyclePct(item.row), 2)}</td>
                                    <td style={cellStyle} className="text-end">{fmt(scrapRate(item.row), 2)}</td>
                                    <td style={cellStyle}><span className="text-muted">{item.reason}</span></td>
                                    <td style={cellStyle} className="text-center">
                                        <div className="d-flex justify-content-center gap-3">
                                            <button type="button" className="btn btn-link p-0" aria-label={`Edit recyclability for ${rowName(item.row)}`} title="Edit recyclability" onClick={() => setEditingItem(item)} style={{ color: 'var(--app-text-muted)', lineHeight: 1 }}><FaEdit aria-hidden="true" /></button>
                                            {item.reason === 'Manually Excluded' && (
                                                <button type="button" className="btn btn-link p-0" aria-label={`Include ${rowName(item.row)} in the recycling calculation`} title="Include in calculation" onClick={() => setIncludedFlag(item, true)} style={{ color: '#198754', lineHeight: 1 }}><FaChevronUp aria-hidden="true" /></button>
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Modal */}
            <EditRecyclabilityModal
                show={!!editingItem}
                item={modalItem}
                onClose={() => setEditingItem(null)}
                onSave={handleModalSave}
            />

            <style>{`
                .custom-scrollbar::-webkit-scrollbar {
                    width: 10px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: var(--app-bg-main);
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: var(--app-border-mid);
                    border-radius: 5px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: var(--app-text-muted);
                }
            `}</style>
        </div>
    );
};

export default Recycling;

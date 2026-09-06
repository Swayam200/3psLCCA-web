import { useState } from 'react';
import MaterialAddModal from './MaterialAddModal';

const calcTotal = (row) => {
    const r = parseFloat(row.rate) || 0;
    const q = parseFloat(row.qty) || 0;
    return (r * q).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

const cellTextStyle = { color: 'var(--app-text-primary)' };
const emptyCellStyle = { color: 'var(--app-text-muted)', fontStyle: 'italic' };

const displayCell = (value, emptyLabel = '—') =>
    value !== '' && value != null ? (
        <span style={cellTextStyle}>{value}</span>
    ) : (
        <span style={emptyCellStyle}>{emptyLabel}</span>
    );

export default function MaterialTable({ section, onRowChange, onRowDelete, onRowUpdate, onAddRow, onSectionDelete, projectData }) {
    const [isAddModalOpen, setIsAddModalOpen] = useState(false);
    const [editRow, setEditRow] = useState(null);
    const activeRows = section.rows.filter((row) => !row?.state?.in_trash);
    return (
        <div className="border rounded mb-4 p-3" style={{ borderColor: 'var(--app-border-mid)', backgroundColor: 'var(--app-bg-card)' }}>
            <div className="d-flex align-items-center justify-content-between mb-3 border-bottom pb-2" style={{ borderColor: 'var(--app-border-mid)' }}>
                <h5 className="m-0 fw-bold fs-5 text-start w-100" style={{ color: 'var(--app-text-primary)' }}>
                    {section.name}
                </h5>
            </div>
            <div className="table-responsive border rounded mb-3" style={{ backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-mid)' }}>
                <table className="table table-sm table-borderless m-0 align-middle text-center" style={{ fontSize: '0.85rem' }}>
                    <thead style={{ backgroundColor: 'var(--app-bg-alt)' }}>
                        <tr>
                            <th rowSpan={2} className="text-start align-middle" style={{ width: '32%', color: 'var(--app-text-primary)', borderBottom: '1px solid var(--app-border-dark)', borderRight: '1px solid var(--app-border-mid)' }}>Work Name</th>
                            <th colSpan={2} style={{ width: '16%', color: 'var(--app-text-primary)', borderBottom: '1px solid var(--app-border-mid)', borderRight: '1px solid var(--app-border-mid)', paddingBottom: '4px' }}>Quantity</th>
                            <th rowSpan={2} className="align-middle" style={{ width: '12%', color: 'var(--app-text-primary)', borderBottom: '1px solid var(--app-border-dark)', borderRight: '1px solid var(--app-border-mid)' }}>Rate</th>
                            <th rowSpan={2} className="align-middle" style={{ width: '18%', color: 'var(--app-text-primary)', borderBottom: '1px solid var(--app-border-dark)', borderRight: '1px solid var(--app-border-mid)' }}>Source</th>
                            <th rowSpan={2} className="align-middle" style={{ width: '13%', color: 'var(--app-text-primary)', borderBottom: '1px solid var(--app-border-dark)', borderRight: '1px solid var(--app-border-mid)' }}>Total</th>
                            <th rowSpan={2} className="align-middle" style={{ width: '9%', color: 'var(--app-text-primary)', borderBottom: '1px solid var(--app-border-dark)' }}>Action</th>
                        </tr>
                        <tr>
                            <th className="align-middle" style={{ width: '8%', color: 'var(--app-text-secondary)', borderBottom: '1px solid var(--app-border-dark)', borderRight: '1px solid var(--app-border-mid)', fontSize: '0.8rem', fontWeight: '500', paddingTop: '2px', paddingBottom: '4px' }}>Value</th>
                            <th className="align-middle" style={{ width: '8%', color: 'var(--app-text-secondary)', borderBottom: '1px solid var(--app-border-dark)', borderRight: '1px solid var(--app-border-mid)', fontSize: '0.8rem', fontWeight: '500', paddingTop: '2px', paddingBottom: '4px' }}>Unit</th>
                        </tr>
                    </thead>
                    <tbody>
                        {activeRows.length === 0 ? (
                            <tr>
                                <td colSpan={7} className="text-center" style={{ color: 'var(--app-text-muted)', padding: '18px', fontStyle: 'italic', fontSize: '0.78rem' }}>
                                    No items yet. Click "Add Material" below.
                                </td>
                            </tr>
                        ) : (
                            activeRows.map((row) => (
                                <tr key={row.id} style={{ borderBottom: '1px solid var(--app-border-light)' }} onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-alt)'} onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}>
                                    <td className="text-start px-2" style={{ borderRight: '1px solid var(--app-border-light)' }}>
                                        {displayCell(row.workName)}
                                    </td>
                                    <td className="px-2" style={{ borderRight: '1px solid var(--app-border-light)' }}>
                                        {displayCell(row.qty)}
                                    </td>
                                    <td className="px-2" style={{ borderRight: '1px solid var(--app-border-light)' }}>
                                        {displayCell(row.unit)}
                                    </td>
                                    <td className="px-2" style={{ borderRight: '1px solid var(--app-border-light)' }}>
                                        {displayCell(row.rate)}
                                    </td>
                                    <td className="px-2" style={{ borderRight: '1px solid var(--app-border-light)' }}>
                                        {displayCell(row.source)}
                                    </td>
                                    <td style={{ borderRight: '1px solid var(--app-border-light)' }}>
                                        <span className="fw-medium" style={{ color: 'var(--app-text-primary)' }}>{calcTotal(row)}</span>
                                    </td>
                                    <td>
                                        <div className="d-flex align-items-center justify-content-center gap-2">
                                            <button
                                                type="button"
                                                className="btn btn-sm px-2 py-1 border-0"
                                                style={{ color: 'var(--app-text-secondary)', transition: 'all 0.2s', backgroundColor: 'transparent' }}
                                                title="Edit row"
                                                onClick={() => setEditRow(row)}
                                                onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--app-primary-accent)'; e.currentTarget.style.backgroundColor = 'rgba(0, 123, 255, 0.08)'; }}
                                                onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--app-text-secondary)'; e.currentTarget.style.backgroundColor = 'transparent'; }}
                                            >
                                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: 'middle' }}>
                                                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                                                    <path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                                                </svg>
                                            </button>
                                            <button
                                                type="button"
                                                className="btn btn-sm px-2 py-1 border-0"
                                                style={{ color: '#e74c3c', transition: 'all 0.2s', backgroundColor: 'transparent' }}
                                                title="Move to Trash"
                                                onClick={() => onRowDelete(section.id, row.id)}
                                                onMouseEnter={(e) => { e.currentTarget.style.color = '#c0392b'; e.currentTarget.style.backgroundColor = 'rgba(231, 76, 60, 0.08)'; }}
                                                onMouseLeave={(e) => { e.currentTarget.style.color = '#e74c3c'; e.currentTarget.style.backgroundColor = 'transparent'; }}
                                            >
                                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: 'middle' }}>
                                                    <polyline points="3 6 5 6 21 6"></polyline>
                                                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                                    <line x1="10" y1="11" x2="10" y2="17"></line>
                                                    <line x1="14" y1="11" x2="14" y2="17"></line>
                                                </svg>
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
            <div className="d-flex gap-2 mb-3">
                <button
                    type="button"
                    className="btn flex-grow-1"
                    style={{ backgroundColor: 'var(--app-bg-card)', color: 'var(--app-text-primary)', border: '1px solid var(--app-border-mid)', fontSize: '0.85rem', transition: 'background-color 0.2s' }}
                    onClick={() => setIsAddModalOpen(true)}
                    onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--app-bg-alt)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'var(--app-bg-card)'; }}
                >
                    Add Material to {section.name}
                </button>
                {onSectionDelete && (
                    <button
                        type="button"
                        className="btn px-3"
                        style={{ backgroundColor: 'transparent', color: '#e74c3c', border: '1px solid rgba(231, 76, 60, 0.4)', fontSize: '0.85rem', transition: 'all 0.2s' }}
                        onClick={() => onSectionDelete(section.id)}
                        onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'rgba(231, 76, 60, 0.08)'; e.currentTarget.style.borderColor = '#e74c3c'; }}
                        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.borderColor = 'rgba(231, 76, 60, 0.4)'; }}
                    >
                        {activeRows.length ? 'Clear All' : 'Delete Component'}
                    </button>
                )}
            </div>
            {isAddModalOpen && (
                <MaterialAddModal
                    sectionName={section.name}
                    projectData={projectData}
                    onClose={() => setIsAddModalOpen(false)}
                    onAdd={(newRowData) => {
                        onAddRow(section.id, newRowData);
                        setIsAddModalOpen(false);
                    }}
                />
            )}
            {editRow && (
                <MaterialAddModal
                    sectionName={section.name}
                    projectData={projectData}
                    editData={editRow}
                    onClose={() => setEditRow(null)}
                    onAdd={(updatedRowData) => {
                        if (onRowUpdate) {
                            onRowUpdate(section.id, editRow.id, updatedRowData);
                        } else {
                            Object.keys(updatedRowData).forEach((field) => {
                                onRowChange(section.id, editRow.id, field, updatedRowData[field]);
                            });
                        }
                        setEditRow(null);
                    }}
                />
            )}
        </div>
    );
}

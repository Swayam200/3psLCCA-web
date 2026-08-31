import { useMemo, useState } from 'react';
import { updatePreviewRow } from '../../../utils/constructionExcel';

const EDITABLE_COLUMNS = [
    ['srcId', 'ID'],
    ['workName', 'Name'],
    ['qty', 'Quantity'],
    ['unit', 'Unit'],
    ['rate', 'Rate'],
    ['source', 'Rate Source'],
    ['carbonFactor', 'Carbon Factor'],
    ['carbonUnitDen', 'Carbon Unit (per)'],
    ['carbonUnit', 'Carbon Unit (ratio)'],
    ['conversionFactor', 'Conversion Factor'],
    ['carbonSource', 'Carbon Source'],
    ['scrapRate', 'Scrap Rate'],
    ['recoveryPct', 'Recovery %'],
    ['component', 'Component'],
];

export default function ImportPreviewModal({ initialPreview, onClose, onImport }) {
    const [preview, setPreview] = useState(initialPreview);
    const [activeSheet, setActiveSheet] = useState(initialPreview.sheets[0]?.name || 'Metadata');
    const [validOnly, setValidOnly] = useState(false);

    const rows = useMemo(() => {
        const sheet = preview.sheets.find((item) => item.name === activeSheet);
        if (!sheet) return [];
        return validOnly
            ? sheet.rows.filter((row) => row.errors.length === 0 && row.workName && row.unit && Number(row.qty) !== 0 && Number(row.rate) !== 0)
            : sheet.rows;
    }, [activeSheet, preview, validOnly]);

    const allRows = preview.sheets.flatMap((sheet) => sheet.rows);
    const selectableRows = allRows.filter((row) => row.errors.length === 0);
    const selectedCount = selectableRows.filter((row) => row.selected).length;
    const errorCount = allRows.filter((row) => row.errors.length).length;
    const warningCount = allRows.filter((row) => row.warnings.length).length;

    const setSelected = (sheetName, rowId, selected) => {
        setPreview((current) => ({
            ...current,
            sheets: current.sheets.map((sheet) => (
                sheet.name !== sheetName
                    ? sheet
                    : { ...sheet, rows: sheet.rows.map((row) => row.id === rowId ? { ...row, selected } : row) }
            )),
        }));
    };

    const toggleAll = () => {
        const shouldSelect = selectedCount < selectableRows.length;
        setPreview((current) => ({
            ...current,
            sheets: current.sheets.map((sheet) => ({
                ...sheet,
                rows: sheet.rows.map((row) => row.errors.length ? row : { ...row, selected: shouldSelect }),
            })),
        }));
    };

    return (
        <>
            <div className="modal-backdrop fade show construction-preview-backdrop" />
            <div className="modal fade show d-block construction-preview-modal" role="dialog" aria-modal="true">
                <div className="modal-dialog modal-fullscreen">
                    <div className="modal-content" style={{ backgroundColor: 'var(--app-bg-main)', color: 'var(--app-text-primary)' }}>
                        <div className="modal-header py-2" style={{ backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-mid)' }}>
                            <h5 className="modal-title">Import Preview - Review &amp; Correct</h5>
                            <button type="button" className="btn-close" aria-label="Close" onClick={onClose} />
                        </div>

                        <div className="d-flex align-items-center gap-3 flex-wrap px-3 py-2 border-bottom" style={{ backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-mid)' }}>
                            <span className="me-auto" style={{ fontSize: '0.78rem', color: 'var(--app-text-secondary)' }}>
                                <b>Click a cell</b> to edit. <span className="text-danger">Red = errors</span> (cannot import). <span style={{ color: '#b7791f' }}>Yellow = warnings.</span>
                            </span>
                            <label className="d-flex align-items-center gap-2 m-0" style={{ fontSize: '0.82rem' }}>
                                <input type="checkbox" checked={selectedCount > 0 && selectedCount === selectableRows.length} onChange={toggleAll} />
                                Select all ({selectedCount} / {selectableRows.length})
                            </label>
                            <label className="d-flex align-items-center gap-2 m-0" style={{ fontSize: '0.82rem' }}>
                                <input type="checkbox" checked={validOnly} onChange={(event) => setValidOnly(event.target.checked)} />
                                Valid rows only
                            </label>
                        </div>

                        {allRows.some((row) => row.duplicate) && (
                            <div className="construction-import-warning mx-3 mt-2">
                                <b>{allRows.filter((row) => row.duplicate).length} row(s)</b> already exist in this project, matched by material name and component. They are unchecked by default; select them to overwrite.
                            </div>
                        )}

                        <div className="d-flex flex-column flex-grow-1 overflow-hidden p-3">
                            <div className="d-flex gap-1 border-bottom construction-preview-tabs">
                                {preview.sheets.map((sheet) => {
                                    const errors = sheet.rows.filter((row) => row.errors.length).length;
                                    const warnings = sheet.rows.filter((row) => row.warnings.length).length;
                                    return (
                                        <button
                                            key={sheet.name}
                                            type="button"
                                            className={`btn btn-sm rounded-0 ${activeSheet === sheet.name ? 'active' : ''}`}
                                            onClick={() => setActiveSheet(sheet.name)}
                                        >
                                            {sheet.name}{errors ? ` (${errors} x)` : warnings ? ` (${warnings} !)` : ''}
                                        </button>
                                    );
                                })}
                                {preview.metadata.length > 0 && (
                                    <button type="button" className={`btn btn-sm rounded-0 ${activeSheet === 'Metadata' ? 'active' : ''}`} onClick={() => setActiveSheet('Metadata')}>
                                        Metadata
                                    </button>
                                )}
                            </div>

                            <div className="flex-grow-1 overflow-auto border border-top-0" style={{ borderColor: 'var(--app-border-mid) !important' }}>
                                {activeSheet === 'Metadata' ? (
                                    <table className="table table-sm m-0">
                                        <thead><tr><th>Key</th><th>Value</th></tr></thead>
                                        <tbody>{preview.metadata.map((item) => <tr key={item.key}><td>{item.key}</td><td>{item.value}</td></tr>)}</tbody>
                                    </table>
                                ) : (
                                    <table className="table table-sm table-bordered m-0 construction-preview-table">
                                        <thead>
                                            <tr>
                                                <th aria-label="Import row" />
                                                <th>Excel Row</th>
                                                {EDITABLE_COLUMNS.map(([, label]) => <th key={label}>{label}</th>)}
                                                <th>Issues</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {rows.map((row) => (
                                                <tr key={row.id} className={row.errors.length ? 'construction-row-error' : row.warnings.length ? 'construction-row-warning' : ''}>
                                                    <td>
                                                        <input
                                                            type="checkbox"
                                                            checked={Boolean(row.selected)}
                                                            disabled={row.errors.length > 0}
                                                            onChange={(event) => setSelected(activeSheet, row.id, event.target.checked)}
                                                        />
                                                    </td>
                                                    <td>{row.rowNumber}</td>
                                                    {EDITABLE_COLUMNS.map(([field]) => (
                                                        <td key={field}>
                                                            <input
                                                                className="construction-preview-cell"
                                                                value={row[field] ?? ''}
                                                                onChange={(event) => setPreview((current) => updatePreviewRow(current, activeSheet, row.id, field, event.target.value))}
                                                            />
                                                        </td>
                                                    ))}
                                                    <td className="construction-issues-cell">
                                                        {[...row.errors, ...row.warnings].join('; ')}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                )}
                            </div>
                            <div className="pt-2" style={{ fontSize: '0.82rem' }}>
                                Total rows: <b>{allRows.length}</b> | <span className="text-danger">Errors: {errorCount}</span> | <span style={{ color: '#b7791f' }}>Warnings: {warningCount}</span> | <span className="text-success">Valid: {allRows.length - errorCount}</span> | <b>Selected: {selectedCount}</b>
                            </div>
                        </div>

                        <div className="modal-footer py-2" style={{ backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-mid)' }}>
                            <button type="button" className="btn btn-sm btn-secondary" onClick={onClose}>Cancel</button>
                            <button type="button" className="btn btn-sm btn-primary" disabled={selectedCount === 0} onClick={() => onImport(preview)}>
                                Import {selectedCount} Row{selectedCount === 1 ? '' : 's'}
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </>
    );
}

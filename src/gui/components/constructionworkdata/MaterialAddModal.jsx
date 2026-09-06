/* eslint-disable no-unused-vars */
import React, { useState, useEffect, useMemo, useRef } from 'react';
import darbhangaData from '../utils/material_database/INDIA_Bihar_Darbhanga_2025.json';
import mumbaiData from '../utils/material_database/INDIA_Maharashtra_Mumbai_2023.json';
import { searchMaterials, resolveDbKey, isSearchableQuery } from './materialSearch.js';
import { resolveCarbonDenom, denomToWebUnit, resolveConversionFactor, canonicalUnit } from '../../../utils/carbonUnits.js';

const DB_MAP = {
    "INDIA/Bihar/Darbhanga-2025": darbhangaData,
    "INDIA/Maharashtra/Mumbai-2023": mumbaiData
};

const UNIT_SELECT_STYLE = {
    backgroundColor: 'var(--app-bg-card)',
    color: 'var(--app-text-primary)',
    borderColor: 'var(--app-border-mid)',
};

function UnitDropdown({ value, onChange, disabled = false }) {
    const handleChange = (e) => {
        if (e.target.value === 'custom_unit_trigger') {
            const customUnit = prompt('Enter custom unit:');
            if (customUnit) onChange(customUnit);
        } else {
            onChange(e.target.value);
        }
    };

    return (
        <select
            className="form-select form-select-sm shadow-none"
            style={UNIT_SELECT_STYLE}
            value={value}
            onChange={handleChange}
            disabled={disabled}
        >
            <option value={value} hidden>{value}</option>

            <optgroup label="— Length —">
                <option value="m">m (Metre)</option>
                <option value="mm">mm (Millimetre)</option>
                <option value="cm">cm (Centimetre)</option>
                <option value="km">km (Kilometre)</option>
            </optgroup>

            <optgroup label="— Area —">
                <option value="m²">m² (Square Metre)</option>
                <option value="mm²">mm² (Square Millimetre)</option>
                <option value="cm²">cm² (Square Centimetre)</option>
                <option value="ha">ha (Hectare)</option>
            </optgroup>

            <optgroup label="— Volume —">
                <option value="m³">m³ (Cubic Metre)</option>
                <option value="mL">mL (Millilitre)</option>
                <option value="L">L (Litre)</option>
            </optgroup>

            <optgroup label="— Mass —">
                <option value="kg">kg (Kilogram)</option>
                <option value="t">t (Metric Tonne)</option>
                <option value="q">q (Quintal)</option>
                <option value="g">g (Gram)</option>
            </optgroup>

            <optgroup label="— Count —">
                <option value="Nos.">Nos. (Numbers)</option>
                <option value="Pcs.">Pcs. (Pieces)</option>
                <option value="Set">Set (Set)</option>
                <option value="L.S.">L.S. (Lump Sum)</option>
            </optgroup>

            <optgroup label="— Time —">
                <option value="hr">hr (Hour)</option>
                <option value="day">day (Day)</option>
                <option value="month">month (Month)</option>
                <option value="yr">yr (Year)</option>
            </optgroup>

            <option value="custom_unit_trigger" className="fw-bold" style={{ color: 'var(--app-primary-accent)' }}>
                + Add Custom Unit...
            </option>
        </select>
    );
}

const MaterialAddModal = ({ sectionName, onClose, onAdd, projectData, editData }) => {
    // Robust resolution of the selected database key (tolerates case/space
    // drift in stored values — an exact-lookup miss used to mean "no
    // suggestions ever" with zero feedback).
    const rawDbKey = projectData?.general_info?.sor_database || projectData?.bridge_data?.sor_database || projectData?.sor_database || '';
    const sorDbKey = resolveDbKey(Object.keys(DB_MAP), rawDbKey);
    const dbData = sorDbKey ? DB_MAP[sorDbKey] : undefined;

    // Basic fields
    const [workName, setWorkName] = useState(editData ? editData.workName : '');
    const [allowEditingDB, setAllowEditingDB] = useState(editData ? !!editData.allowEditingDB : false);
    // Rows saved by earlier builds never stored the schedule-of-rates
    // conversion factor. When editing such a row, recover it from the same
    // database entry (matched by exact name) so the row can be counted.
    const legacyDbFactor = useMemo(() => {
        if (!editData || !dbData) return null;
        const stored = editData.conversionFactor;
        if (stored !== undefined && stored !== null && stored !== '' && Number(stored) > 0) return null;
        const match = searchMaterials(dbData, editData.workName || '', sectionName)
            .find((item) => item.name === editData.workName);
        const dbFactor = Number(match?.conversion_factor);
        return match && Number.isFinite(dbFactor) && dbFactor > 0 ? dbFactor : null;
    }, [editData, dbData, sectionName]);
    // True once the fields were filled from the schedule of rates; until the
    // user ticks "Allow editing DB-filled values" those fields stay read-only.
    const [dbFilled, setDbFilled] = useState(editData ? (!!editData.dbFilled || legacyDbFactor !== null) : false);
    // Conversion factor = emission units per quantity unit (kg per MT, kg
    // per m³ …). The SOR ships it per item; otherwise it is derived from the
    // units or entered by the user.
    const [conversionFactor, setConversionFactor] = useState(() => {
        if (legacyDbFactor !== null) return String(legacyDbFactor);
        const stored = editData?.conversionFactor;
        return stored !== undefined && stored !== null && stored !== '' && Number(stored) > 0 ? String(stored) : '';
    });
    const [conversionFactorSource, setConversionFactorSource] = useState(
        legacyDbFactor !== null ? 'db' : (editData?.conversionFactorSource || ''),
    );
    const [qty, setQty] = useState(editData ? editData.qty : '');
    const [unit, setUnit] = useState(editData ? editData.unit : 'm³ — Cubic Metre');
    const [rate, setRate] = useState(editData ? editData.rate : '');
    const [source, setSource] = useState(editData ? editData.source : '');

    // Carbon Emission
    const [includeCarbon, setIncludeCarbon] = useState(editData ? !!editData.carbonEmission : true);
    const [emissionFactor, setEmissionFactor] = useState(editData?.carbonEmission ? editData.carbonEmission.factor : '');
    const [emissionPerUnit, setEmissionPerUnit] = useState(editData?.carbonEmission ? editData.carbonEmission.perUnit : 'm³ — Cubic Metre');
    const [emissionSource, setEmissionSource] = useState(editData?.carbonEmission ? editData.carbonEmission.source : '');

    // Recyclability
    const [includeRecyclability, setIncludeRecyclability] = useState(editData ? !!editData.recyclability : false);
    const [grade, setGrade] = useState(editData?.recyclability ? editData.recyclability.grade : '');
    const [type, setType] = useState(editData?.recyclability ? editData.recyclability.type : '');
    const [recoveryPercent, setRecoveryPercent] = useState(
        editData?.postDemolitionRecoveryPercentage ? String(editData.postDemolitionRecoveryPercentage) : '',
    );
    const [scrapRate, setScrapRate] = useState(editData?.scrapRate ? String(editData.scrapRate) : '');

    // Search Suggestions
    const [showSuggestions, setShowSuggestions] = useState(false);
    const [selectedIndex, setSelectedIndex] = useState(-1);
    const suggestionRef = useRef(null);

    // Window chrome: the dialog drags by its header and the □ button
    // maximizes/restores. (The old — and □ buttons were wired to onClose.)
    const [maximized, setMaximized] = useState(false);
    const [offset, setOffset] = useState({ x: 0, y: 0 });
    const dragRef = useRef(null);

    const startDrag = (e) => {
        if (maximized || e.button !== 0 || e.target.closest('[data-window-button]')) return;
        e.preventDefault();
        const start = { x: e.clientX, y: e.clientY, baseX: offset.x, baseY: offset.y };
        dragRef.current = start;
        const onMove = (ev) => {
            if (!dragRef.current) return;
            setOffset({ x: start.baseX + ev.clientX - start.x, y: start.baseY + ev.clientY - start.y });
        };
        const onUp = () => {
            dragRef.current = null;
            window.removeEventListener('pointermove', onMove);
            window.removeEventListener('pointerup', onUp);
        };
        window.addEventListener('pointermove', onMove);
        window.addEventListener('pointerup', onUp);
    };

    const suggestions = useMemo(
        () => searchMaterials(dbData, workName, sectionName),
        [dbData, workName, sectionName],
    );

    // The dropdown always answers a searchable query (2+ chars, or "?" to
    // list everything, desktop-style) — with matches, with "no matches", or
    // with "no database selected". Silence looked like a bug.
    const searchActive = showSuggestions && isSearchableQuery(workName);

    const handleSelectMaterial = (item) => {
        setWorkName(item.name);
        setRate(item.rate);
        setUnit(item.unit);
        setSource(item.rate_src);
        setDbFilled(true);
        setAllowEditingDB(false);

        if (item.carbon_emission !== 'not_available') {
            setIncludeCarbon(true);
            setEmissionFactor(item.carbon_emission);
            setEmissionSource(item.carbon_emission_src);
            // Desktop-canonical unit resolution: "_den" wins, otherwise the
            // ratio in carbon_emission_units yields its denominator.
            const denom = resolveCarbonDenom(item);
            const webUnit = denomToWebUnit(denom);
            setEmissionPerUnit(webUnit || denom || '');
            // The schedule of rates carries the factor that turns the priced
            // unit into the emission unit (kg per MT, kg per cum, …).
            const dbFactor = Number(item.conversion_factor);
            if (Number.isFinite(dbFactor) && dbFactor > 0) {
                setConversionFactor(String(dbFactor));
                setConversionFactorSource('db');
            } else {
                setConversionFactor('');
                setConversionFactorSource('');
            }
        }

        setShowSuggestions(false);
        setSelectedIndex(-1);
    };

    const lockDb = dbFilled && !allowEditingDB;
    const conversion = useMemo(() => resolveConversionFactor({
        quantityUnit: unit,
        emissionUnit: emissionPerUnit,
        explicit: conversionFactor,
        trusted: conversionFactorSource === 'db' || conversionFactorSource === 'user',
    }), [unit, emissionPerUnit, conversionFactor, conversionFactorSource]);
    const emissionPreview = (() => {
        const q = parseFloat(qty);
        const ef = parseFloat(emissionFactor);
        if (!includeCarbon || !Number.isFinite(q) || !Number.isFinite(ef) || conversion.status === 'mismatch') return null;
        const total = q * conversion.factor * ef;
        return `${q} ${canonicalUnit(unit) || unit} × ${conversion.factor} × ${ef} = ${total.toLocaleString('en-IN', { maximumFractionDigits: 3 })} kgCO₂e`;
    })();

    const handleKeyDown = (e) => {
        if (!showSuggestions || suggestions.length === 0) return;

        if (e.key === 'ArrowDown') {
            setSelectedIndex(prev => (prev + 1) % suggestions.length);
        } else if (e.key === 'ArrowUp') {
            setSelectedIndex(prev => (prev - 1 + suggestions.length) % suggestions.length);
        } else if (e.key === 'Enter' && selectedIndex >= 0) {
            handleSelectMaterial(suggestions[selectedIndex]);
            e.preventDefault();
        } else if (e.key === 'Escape') {
            setShowSuggestions(false);
        }
    };

    const [entryErrors, setEntryErrors] = useState({});

    const validateEntry = () => {
        const errors = {};
        const quantity = Number(qty);
        const unitRate = Number(rate);
        if (!String(workName || '').trim()) errors.workName = 'Enter a material or work item name.';
        if (qty === '' || qty === null || !Number.isFinite(quantity)) errors.qty = 'Enter a quantity.';
        else if (quantity <= 0) errors.qty = 'Quantity must be greater than zero. Use the recycling section for credits.';
        if (rate !== '' && rate !== null && (!Number.isFinite(unitRate) || unitRate < 0)) errors.rate = 'Rate cannot be negative.';
        if (includeCarbon && (parseFloat(emissionFactor) || 0) > 0 && conversion.status === 'mismatch') {
            errors.conversion = conversion.note;
        }
        if (includeRecyclability) {
            const pct = parseFloat(recoveryPercent);
            if (recoveryPercent !== '' && (!Number.isFinite(pct) || pct < 0 || pct > 100)) errors.recovery = 'Recovery must be between 0 and 100 %.';
            const scrap = parseFloat(scrapRate);
            if (scrapRate !== '' && (!Number.isFinite(scrap) || scrap < 0)) errors.scrap = 'Scrap rate cannot be negative.';
        }
        setEntryErrors(errors);
        return Object.keys(errors).length === 0;
    };

    const handleAdd = () => {
        if (!validateEntry()) return;
        const factorSource = conversionFactorSource || (conversion.status === 'derived' || conversion.status === 'same' ? 'derived' : '');
        const newRowData = {
            workName,
            qty: parseFloat(qty) || 0,
            unit,
            rate: parseFloat(rate) || 0,
            source,
            allowEditingDB,
            dbFilled,
            conversionFactor: conversion.status === 'mismatch' ? 0 : conversion.factor,
            conversionFactorSource: factorSource,
            carbonEmission: includeCarbon ? { factor: parseFloat(emissionFactor) || 0, perUnit: emissionPerUnit, source: emissionSource } : null,
            recyclability: includeRecyclability ? { grade, type } : null,
            ...(includeRecyclability && recoveryPercent !== '' ? { postDemolitionRecoveryPercentage: parseFloat(recoveryPercent) || 0 } : {}),
            ...(includeRecyclability && scrapRate !== '' ? { scrapRate: parseFloat(scrapRate) || 0 } : {}),
        };
        onAdd(newRowData);
    };

    return (
        <>
            <div className="modal-backdrop fade show" style={{ zIndex: 1040, backgroundColor: 'rgba(0,0,0,0.6)' }} onClick={onClose}></div>

            <div className="modal fade show d-block" tabIndex="-1" style={{ zIndex: 1050 }} role="dialog">
                <div
                    className={`modal-dialog ${maximized ? '' : 'modal-dialog-centered'}`}
                    style={maximized
                        ? { maxWidth: 'none', width: '100vw', height: '100vh', margin: 0 }
                        : { maxWidth: '800px', transform: `translate(${offset.x}px, ${offset.y}px)` }}
                >
                    <div
                        className="modal-content shadow-lg border-0 overflow-hidden"
                        style={{ backgroundColor: 'var(--app-bg-card)', color: 'var(--app-text-primary)', borderRadius: maximized ? 0 : '8px', height: maximized ? '100vh' : 'auto' }}
                    >

                        <div
                            className="d-flex justify-content-between align-items-center px-3 py-2 border-bottom"
                            style={{ backgroundColor: 'var(--app-bg-alt)', borderColor: 'var(--app-border-mid)', cursor: maximized ? 'default' : 'move', userSelect: 'none', touchAction: 'none' }}
                            onPointerDown={startDrag}
                            onDoubleClick={() => setMaximized((value) => !value)}
                        >
                            <div className="d-flex align-items-center gap-2" style={{ fontSize: '0.9rem' }}>
                                <span style={{ color: 'var(--app-primary-accent)', fontSize: '1.2rem' }}>⛁</span>
                                <span>{editData ? 'Edit Material' : 'Add Material'} — {sectionName}</span>
                            </div>
                            <div className="d-flex gap-3 align-items-center" style={{ cursor: 'pointer', fontSize: '1.1rem' }}>
                                <span
                                    className="opacity-75"
                                    data-window-button
                                    title={maximized ? 'Restore' : 'Maximize'}
                                    onClick={() => setMaximized((value) => !value)}
                                >
                                    {maximized ? '❐' : '□'}
                                </span>
                                <span data-window-button title="Close" onClick={onClose}>✕</span>
                            </div>
                        </div>

                        <div className="modal-body px-4 py-2" style={{ fontSize: '0.9rem', overflowY: maximized ? 'auto' : 'visible' }}>
                            <div className="mb-3 opacity-75" style={{ fontSize: '0.85rem' }}>
                                Suggestions from: <span className="fst-italic">{sorDbKey || '— not set (choose an SOR database on the General Information page)'}</span>
                            </div>

                            <div className="mb-2 position-relative">
                                <label className="form-label fw-medium mb-1">Material Name <span className="text-danger">*</span></label>
                                <input
                                    type="text"
                                    className="form-control form-control-sm"
                                    placeholder="e.g. Ready-mix Concrete M25  (2+ chars to search, ? lists everything)"
                                    value={workName}
                                    aria-invalid={entryErrors.workName ? 'true' : 'false'}
                                    onChange={e => { setWorkName(e.target.value); setShowSuggestions(true); setSelectedIndex(-1); if (entryErrors.workName) setEntryErrors((prev) => ({ ...prev, workName: undefined })); }}
                                    onKeyDown={handleKeyDown}
                                    onFocus={() => setShowSuggestions(true)}
                                />
                                {entryErrors.workName && <div className="invalid-feedback d-block" data-testid="material-name-error">{entryErrors.workName}</div>}
                                {searchActive && suggestions.length === 0 && (
                                    <div
                                        className="w-100 border rounded px-3 py-2 mt-1"
                                        style={{ backgroundColor: 'var(--app-bg-alt)', borderColor: 'var(--app-border-mid)', fontSize: '0.83rem', color: 'var(--app-text-secondary)' }}
                                        data-testid="material-search-empty"
                                    >
                                        {!dbData
                                            ? 'No SOR database selected — choose one on the General Information page to get suggestions.'
                                            : `No matches for “${workName.trim()}” in ${sorDbKey}. Refine the search or fill the fields manually.`}
                                    </div>
                                )}
                                {showSuggestions && suggestions.length > 0 && (
                                    <ul
                                        ref={suggestionRef}
                                        className="list-group position-absolute w-100 shadow-sm"
                                        style={{ zIndex: 1100, maxHeight: '250px', overflowY: 'auto', backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-mid)' }}
                                    >
                                        {suggestions.map((item, index) => (
                                            <li
                                                key={index}
                                                className={`list-group-item list-group-item-action py-2 border-0 ${selectedIndex === index ? 'active' : ''}`}
                                                style={{
                                                    cursor: 'pointer',
                                                    fontSize: '0.85rem',
                                                    backgroundColor: selectedIndex === index ? 'var(--app-primary-accent)' : 'transparent',
                                                    color: selectedIndex === index ? 'white' : 'var(--app-text-primary)'
                                                }}
                                                onClick={() => handleSelectMaterial(item)}
                                                onMouseEnter={() => setSelectedIndex(index)}
                                            >
                                                <div className="d-flex justify-content-between align-items-center">
                                                    <span>{item.name}</span>
                                                    <span className="badge bg-secondary opacity-50" style={{ fontSize: '0.7rem' }}>{item.type}</span>
                                                </div>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>

                            {dbFilled && (
                                <div className="mb-2 form-check d-flex align-items-center gap-2">
                                    <input
                                        className="form-check-input mt-0"
                                        type="checkbox"
                                        id="allowDb"
                                        style={{ width: '18px', height: '18px', backgroundColor: allowEditingDB ? 'var(--app-primary-accent)' : 'var(--app-input-bg)', borderColor: 'var(--app-border-mid)' }}
                                        checked={allowEditingDB}
                                        onChange={e => setAllowEditingDB(e.target.checked)}
                                    />
                                    <label className="form-check-label opacity-75" htmlFor="allowDb" style={{ paddingTop: '1px', cursor: 'pointer' }}>
                                        Allow editing DB-filled values
                                        {lockDb && <span className="ms-2 fst-italic" style={{ fontSize: '0.8rem' }}>(rate, units and emission factor are locked to the schedule of rates)</span>}
                                    </label>
                                </div>
                            )}

                            <div className="row mb-2">
                                <div className="col-md-6">
                                    <label className="form-label fw-medium mb-1" htmlFor="material-qty">Quantity <span className="text-danger">*</span></label>
                                    <input
                                        id="material-qty"
                                        type="number"
                                        min="0"
                                        step="any"
                                        className={`form-control form-control-sm${entryErrors.qty ? ' is-invalid' : ''}`}
                                        placeholder="e.g. 100"
                                        value={qty}
                                        aria-invalid={entryErrors.qty ? 'true' : 'false'}
                                        onChange={e => { setQty(e.target.value); if (entryErrors.qty) setEntryErrors((prev) => ({ ...prev, qty: undefined })); }}
                                    />
                                    {entryErrors.qty && <div className="invalid-feedback d-block" data-testid="material-qty-error">{entryErrors.qty}</div>}
                                </div>
                                <div className="col-md-6">
                                    <label className="form-label fw-medium mb-1">Unit <span className="text-danger">*</span></label>
                                    <UnitDropdown value={unit} onChange={setUnit} disabled={lockDb} />
                                </div>
                            </div>

                            <div className="row mb-2 pb-2 border-bottom border-secondary" style={{ borderColor: 'var(--app-border-mid) !important' }}>
                                <div className="col-md-6">
                                    <label className="form-label fw-medium mb-1" htmlFor="material-rate">Rate (Cost)</label>
                                    <input
                                        id="material-rate"
                                        type="number"
                                        min="0"
                                        step="any"
                                        className={`form-control form-control-sm${entryErrors.rate ? ' is-invalid' : ''}`}
                                        placeholder="0.00"
                                        value={rate}
                                        readOnly={lockDb}
                                        aria-invalid={entryErrors.rate ? 'true' : 'false'}
                                        onChange={e => { setRate(e.target.value); if (entryErrors.rate) setEntryErrors((prev) => ({ ...prev, rate: undefined })); }}
                                    />
                                    {entryErrors.rate && <div className="invalid-feedback d-block" data-testid="material-rate-error">{entryErrors.rate}</div>}
                                </div>
                                <div className="col-md-6">
                                    <label className="form-label fw-medium mb-1">Rate Source</label>
                                    <input
                                        type="text"
                                        className="form-control form-control-sm"
                                        placeholder="e.g. SOR, Market"
                                        value={source}
                                        readOnly={lockDb}
                                        onChange={e => setSource(e.target.value)}
                                    />
                                </div>
                            </div>

                            <div className="mb-2 pb-2 border-bottom border-secondary" style={{ borderColor: 'var(--app-border-mid) !important' }}>
                                <div className="d-flex justify-content-between align-items-center mb-3">
                                    <h6 className="m-0 fw-bold">Carbon Emission</h6>
                                    <div className="form-check d-flex align-items-center gap-2 m-0">
                                        <input
                                            className="form-check-input mt-0"
                                            type="checkbox"
                                            id="incCarbon"
                                            style={{ width: '18px', height: '18px', backgroundColor: includeCarbon ? 'var(--app-primary-accent)' : 'var(--app-input-bg)', borderColor: 'var(--app-border-mid)' }}
                                            checked={includeCarbon}
                                            onChange={e => setIncludeCarbon(e.target.checked)}
                                        />
                                        <label className="form-check-label" htmlFor="incCarbon" style={{ cursor: 'pointer' }}>Include</label>
                                    </div>
                                </div>
                                <div className="row" style={{ opacity: includeCarbon ? 1 : 0.5, pointerEvents: includeCarbon ? 'auto' : 'none' }}>
                                    <div className="col-md-4">
                                        <label className="form-label mb-1">Emission Factor (kgCO₂e per unit below)</label>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            placeholder="0.000"
                                            value={emissionFactor}
                                            readOnly={lockDb}
                                            onChange={e => setEmissionFactor(e.target.value)}
                                        />
                                    </div>
                                    <div className="col-md-4">
                                        <label className="form-label mb-1">Per unit of material</label>
                                        <UnitDropdown value={emissionPerUnit} onChange={setEmissionPerUnit} disabled={lockDb} />
                                    </div>
                                    <div className="col-md-4">
                                        <label className="form-label mb-1">Source</label>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            placeholder="e.g. ICE, IPCC"
                                            value={emissionSource}
                                            readOnly={lockDb}
                                            onChange={e => setEmissionSource(e.target.value)}
                                        />
                                    </div>
                                </div>
                                <div className="row mt-2" style={{ opacity: includeCarbon ? 1 : 0.5, pointerEvents: includeCarbon ? 'auto' : 'none' }}>
                                    <div className="col-md-5">
                                        <label className="form-label mb-1" htmlFor="material-conversion">
                                            Conversion factor ({canonicalUnit(emissionPerUnit) || 'emission unit'} per {canonicalUnit(unit) || 'quantity unit'})
                                        </label>
                                        <input
                                            id="material-conversion"
                                            type="number"
                                            min="0"
                                            step="any"
                                            className={`form-control form-control-sm${entryErrors.conversion ? ' is-invalid' : ''}`}
                                            placeholder={conversion.status === 'derived' ? String(conversion.factor) : 'e.g. 2400 for kg per m³'}
                                            value={conversionFactor}
                                            readOnly={lockDb && conversionFactorSource === 'db'}
                                            aria-invalid={entryErrors.conversion ? 'true' : 'false'}
                                            onChange={e => {
                                                setConversionFactor(e.target.value);
                                                setConversionFactorSource(e.target.value === '' ? '' : 'user');
                                                if (entryErrors.conversion) setEntryErrors((prev) => ({ ...prev, conversion: undefined }));
                                            }}
                                        />
                                        {entryErrors.conversion && <div className="invalid-feedback d-block" data-testid="material-conversion-error">{entryErrors.conversion}</div>}
                                    </div>
                                    <div className="col-md-7 d-flex flex-column justify-content-end" style={{ fontSize: '0.8rem' }}>
                                        {conversion.status === 'mismatch' && !entryErrors.conversion && (
                                            <div className="text-warning" data-testid="material-conversion-warning">⚠ {conversion.note}</div>
                                        )}
                                        {conversion.status === 'derived' && (
                                            <div className="text-secondary">Auto-converted: {conversion.note}.</div>
                                        )}
                                        {conversion.status === 'explicit' && conversionFactorSource === 'db' && (
                                            <div className="text-secondary">From the schedule of rates: {conversion.note}.</div>
                                        )}
                                        {emissionPreview && <div className="fw-medium" data-testid="material-emission-preview">{emissionPreview}</div>}
                                    </div>
                                </div>
                            </div>

                            <div className="mb-2">
                                <div className="d-flex justify-content-between align-items-center mb-3">
                                    <h6 className="m-0 fw-bold">Recyclability</h6>
                                    <div className="form-check d-flex align-items-center gap-2 m-0">
                                        <input
                                            className="form-check-input mt-0"
                                            type="checkbox"
                                            id="incRecyclability"
                                            style={{ width: '18px', height: '18px', backgroundColor: includeRecyclability ? 'var(--app-primary-accent)' : 'var(--app-input-bg)', borderColor: 'var(--app-border-mid)' }}
                                            checked={includeRecyclability}
                                            onChange={e => setIncludeRecyclability(e.target.checked)}
                                        />
                                        <label className="form-check-label" htmlFor="incRecyclability" style={{ cursor: 'pointer' }}>Include</label>
                                    </div>
                                </div>
                                <div className="row" style={{ opacity: includeRecyclability ? 1 : 0.5, pointerEvents: includeRecyclability ? 'auto' : 'none' }}>
                                    <div className="col-md-6">
                                        <label className="form-label mb-1">Grade</label>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            placeholder="e.g. M25"
                                            value={grade}
                                            onChange={e => setGrade(e.target.value)}
                                        />
                                    </div>
                                    <div className="col-md-6">
                                        <label className="form-label mb-1">Type</label>
                                        <input
                                            className="form-control form-control-sm"
                                            value={type}
                                            onChange={e => setType(e.target.value)}
                                            placeholder="e.g. Concrete"
                                        />
                                    </div>
                                </div>
                                <div className="row mt-2" style={{ opacity: includeRecyclability ? 1 : 0.5, pointerEvents: includeRecyclability ? 'auto' : 'none' }}>
                                    <div className="col-md-6">
                                        <label className="form-label mb-1" htmlFor="material-recovery">Recovery after demolition (%)</label>
                                        <input
                                            id="material-recovery"
                                            type="number"
                                            min="0"
                                            max="100"
                                            step="any"
                                            className={`form-control form-control-sm${entryErrors.recovery ? ' is-invalid' : ''}`}
                                            placeholder="e.g. 90"
                                            value={recoveryPercent}
                                            onChange={e => { setRecoveryPercent(e.target.value); if (entryErrors.recovery) setEntryErrors((prev) => ({ ...prev, recovery: undefined })); }}
                                        />
                                        {entryErrors.recovery && <div className="invalid-feedback d-block">{entryErrors.recovery}</div>}
                                    </div>
                                    <div className="col-md-6">
                                        <label className="form-label mb-1" htmlFor="material-scrap">Scrap rate (per {canonicalUnit(unit) || 'unit'})</label>
                                        <input
                                            id="material-scrap"
                                            type="number"
                                            min="0"
                                            step="any"
                                            className={`form-control form-control-sm${entryErrors.scrap ? ' is-invalid' : ''}`}
                                            placeholder="e.g. 30000"
                                            value={scrapRate}
                                            onChange={e => { setScrapRate(e.target.value); if (entryErrors.scrap) setEntryErrors((prev) => ({ ...prev, scrap: undefined })); }}
                                        />
                                        {entryErrors.scrap && <div className="invalid-feedback d-block">{entryErrors.scrap}</div>}
                                    </div>
                                    <div className="col-12 text-secondary mt-1" style={{ fontSize: '0.78rem' }}>
                                        Both values are needed for the material to count on the Recycling page; they can also be set there later.
                                    </div>
                                </div>
                            </div>

                        </div>

                        <div className="modal-footer d-flex justify-content-between border-top border-secondary pt-3 pb-3 px-4" style={{ backgroundColor: 'var(--app-bg-alt)', borderColor: 'var(--app-border-mid) !important' }}>
                            <button className="btn px-4" style={{ backgroundColor: 'transparent', color: 'var(--app-text-primary)', border: '1px solid var(--app-primary-accent)' }}>Save to Custom DB...</button>
                            <div className="d-flex gap-2">
                                <button className="btn px-4" style={{ backgroundColor: 'var(--app-bg-card)', color: 'var(--app-text-primary)', border: '1px solid var(--app-border-mid)' }} onClick={onClose}>Cancel</button>
                                <button className="btn px-4" style={{ backgroundColor: 'var(--app-primary-accent)', color: 'white', border: 'none' }} onClick={handleAdd}>{editData ? 'Save Changes' : 'Add to Table'}</button>
                            </div>
                        </div>

                    </div>
                </div>
            </div>
        </>
    );
};

export default MaterialAddModal;
/**
 * Recyclability editor for one construction material.
 *
 * Only the two recycling inputs are editable here — scrap rate and recovery
 * after demolition — because everything else (quantity, unit, rate, carbon
 * factor) belongs to Construction Work Data and is edited there. Those
 * values are shown read-only for context, straight from the row, and the
 * preview is computed from what is on screen.
 */
import { useEffect, useMemo, useState } from 'react';
import { Modal, Button, Form, Row, Col } from 'react-bootstrap';

const parse = (value) => {
    const n = parseFloat(String(value ?? '').replace(/,/g, ''));
    return Number.isFinite(n) ? n : 0;
};

const fmt = (value, digits = 3) => new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: Math.min(digits, 3),
    maximumFractionDigits: digits,
}).format(value);

const unitSymbol = (unit) => String(unit || '').split(/\s[—-]\s/)[0].trim() || '—';

const EditRecyclabilityModal = ({ show, onClose, item, onSave }) => {
    const [scrapRate, setScrapRate] = useState('');
    const [recoveryPercent, setRecoveryPercent] = useState('');
    const [errors, setErrors] = useState({});

    useEffect(() => {
        if (!show) return;
        // Reset the two inputs each time the dialog opens for a (new) row.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setScrapRate(item?.scrapRate ?? '');
        setRecoveryPercent(item?.recoveryPercent ?? item?.recyclability ?? '');
        setErrors({});
    }, [show, item]);

    const quantity = parse(item?.qtyValue);
    const unit = unitSymbol(item?.qtyUnit);
    const currency = item?.currency || '';
    const preview = useMemo(() => {
        const pct = parse(recoveryPercent);
        const rate = parse(scrapRate);
        const recyclable = quantity * (pct / 100);
        return { pct, rate, recyclable, recovered: recyclable * rate };
    }, [quantity, recoveryPercent, scrapRate]);

    if (!show) return null;

    const validate = () => {
        const next = {};
        const pct = parse(recoveryPercent);
        const rate = parse(scrapRate);
        if (recoveryPercent === '' || pct < 0 || pct > 100) next.recoveryPercent = 'Enter a recovery between 0 and 100 %.';
        if (scrapRate === '' || rate < 0) next.scrapRate = 'Enter a scrap rate of 0 or more.';
        setErrors(next);
        return Object.keys(next).length === 0;
    };

    const handleSave = () => {
        if (!validate()) return;
        onSave({ ...item, scrapRate, recoveryPercent });
        onClose();
    };

    const readOnly = (label, value, testId) => (
        <Col md={4} className="mb-2">
            <div style={{ fontSize: '0.75rem', color: 'var(--app-text-muted)' }}>{label}</div>
            <div data-testid={testId} style={{ fontSize: '0.9rem', color: 'var(--app-text-primary)' }}>{value}</div>
        </Col>
    );

    const emissionFactor = item?.emissionFactor === '' || item?.emissionFactor === undefined || item?.emissionFactor === null
        ? null : parse(item.emissionFactor);

    return (
        <Modal show={show} onHide={onClose} centered size="lg" contentClassName="border-0" data-testid="recyclability-modal">
            <Modal.Header closeButton style={{ backgroundColor: 'var(--app-bg-card)', color: 'var(--app-text-primary)', borderBottom: '1px solid var(--app-border-mid)' }}>
                <Modal.Title style={{ fontSize: '1rem' }}>Recyclability — {item?.material || 'Material'}</Modal.Title>
            </Modal.Header>
            <Modal.Body style={{ backgroundColor: 'var(--app-bg-main)', color: 'var(--app-text-primary)' }}>
                <div className="p-3 rounded mb-3" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-mid)' }}>
                    <div className="d-flex justify-content-between align-items-baseline mb-2">
                        <h6 className="m-0" style={{ fontSize: '0.85rem', color: 'var(--app-logo-accent)', fontWeight: 'bold' }}>From Construction Work Data</h6>
                        <span style={{ fontSize: '0.75rem', color: 'var(--app-text-muted)' }}>Edit these on the construction page</span>
                    </div>
                    <Row>
                        {readOnly('Quantity', `${fmt(quantity)} ${unit}`, 'recyclability-quantity')}
                        {readOnly('Rate', item?.rateCost === '' || item?.rateCost === undefined ? '—' : `${fmt(parse(item.rateCost), 2)} ${currency}/${unit}`, 'recyclability-rate')}
                        {readOnly('Emission factor', emissionFactor === null ? '—' : `${fmt(emissionFactor, 3)} kgCO₂e per ${item?.perUnit || 'unit'}`, 'recyclability-ef')}
                    </Row>
                </div>

                <Row className="mb-2">
                    <Col md={6}>
                        <Form.Label htmlFor="recyclability-scrap-rate">Scrap rate ({currency ? `${currency} per ${unit}` : `per ${unit}`})</Form.Label>
                        <Form.Control
                            id="recyclability-scrap-rate"
                            type="number"
                            min="0"
                            step="any"
                            value={scrapRate}
                            isInvalid={Boolean(errors.scrapRate)}
                            onChange={(e) => setScrapRate(e.target.value)}
                            data-testid="recyclability-scrap-rate"
                        />
                        <Form.Control.Feedback type="invalid">{errors.scrapRate}</Form.Control.Feedback>
                    </Col>
                    <Col md={6}>
                        <Form.Label htmlFor="recyclability-recovery">Recovery after demolition (%)</Form.Label>
                        <Form.Control
                            id="recyclability-recovery"
                            type="number"
                            min="0"
                            max="100"
                            step="any"
                            value={recoveryPercent}
                            isInvalid={Boolean(errors.recoveryPercent)}
                            onChange={(e) => setRecoveryPercent(e.target.value)}
                            data-testid="recyclability-recovery"
                        />
                        <Form.Control.Feedback type="invalid">{errors.recoveryPercent}</Form.Control.Feedback>
                    </Col>
                </Row>

                <div className="mt-3" style={{ fontSize: '0.85rem', color: 'var(--app-primary-accent)' }} data-testid="recyclability-preview">
                    {fmt(quantity)} {unit} × {fmt(preview.pct, 2)} % = {fmt(preview.recyclable)} {unit} recyclable
                    {' → '}
                    {fmt(preview.recyclable)} {unit} × {fmt(preview.rate, 2)} = <span className="fw-bold" style={{ color: 'var(--app-text-primary)' }}>{fmt(preview.recovered, 2)} {currency}</span> recovered
                </div>
            </Modal.Body>
            <Modal.Footer style={{ backgroundColor: 'var(--app-bg-card)', borderTop: '1px solid var(--app-border-mid)' }}>
                <Button variant="outline-secondary" onClick={onClose}>Cancel</Button>
                <Button onClick={handleSave} style={{ backgroundColor: 'var(--app-primary-accent)', border: 'none' }} data-testid="recyclability-save">Save</Button>
            </Modal.Footer>
        </Modal>
    );
};

export default EditRecyclabilityModal;

/* eslint-disable no-unused-vars */
import React, { useState, useEffect } from 'react';
import { Modal, Button, Form } from 'react-bootstrap';
import { COUNTRIES, CURRENCIES } from './utils/countriesdata';
import { materialCatalog } from './utils/materialCatalog';

const UNIT_SYSTEM_OPTIONS = ['Metric (SI)', 'Imperial (US)'];

const NewProjectModal = ({ show, onHide, onCreate }) => {
    const [projectName, setProjectName] = useState('');
    const [country, setCountry] = useState('');
    const [currency, setCurrency] = useState('');
    const [unitSystem, setUnitSystem] = useState('Metric (SI)');
    const [sorDatabase, setSorDatabase] = useState('');
    const [validated, setValidated] = useState(false);

    useEffect(() => {
        if (show) {
            setProjectName('');
            setCountry('');
            setCurrency('');
            setUnitSystem('Metric (SI)');
            setSorDatabase('');
            setValidated(false);
        }
    }, [show]);

    const handleCreate = () => {
        setValidated(true);
        if (!projectName.trim() || !country || !currency || !unitSystem) {
            return;
        }
        onCreate({
            name: projectName.trim(),
            country,
            currency,
            unitSystem,
            sorDatabase,
            createdAt: new Date().toLocaleString()
        });
        onHide();
    };

    return (
        <Modal
            show={show}
            onHide={onHide}
            centered
            contentClassName="new-project-modal"
            style={{ fontFamily: '"Segoe UI", sans-serif' }}
        >
            <style>{`
                .new-project-modal {
                    background-color: var(--app-bg-card);
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-primary);
                    border-radius: 12px;
                    max-width: 480px;
                    margin: auto;
                }
                .new-project-modal .modal-header {
                    border-bottom: 1px solid var(--app-border-light);
                    padding: 0.75rem 1.25rem;
                }
                .new-project-modal .modal-body {
                    padding: 1.25rem;
                }
                .new-project-modal .modal-footer {
                    border-top: none;
                    padding: 0 1.25rem 1.25rem 1.25rem;
                }
                .new-project-modal .form-label {
                    font-size: 0.9rem;
                    font-weight: 600;
                    margin-bottom: 0.5rem;
                }
                .new-project-modal .form-control, .new-project-modal .form-select {
                    background-color: var(--app-bg-alt);
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-primary);
                    font-size: 0.9rem;
                    padding: 0.6rem;
                }
                .new-project-modal .form-control:focus, .new-project-modal .form-select:focus {
                    background-color: var(--app-bg-alt);
                    border-color: var(--app-primary-accent);
                    box-shadow: 0 0 0 0.2rem rgba(154, 205, 50, 0.1);
                    color: var(--app-text-primary);
                }
                .new-project-modal .help-text {
                    font-size: 0.75rem;
                    color: var(--app-text-secondary);
                    margin-top: 0.4rem;
                }
                .new-project-modal .invalid-feedback-inline {
                    font-size: 0.75rem;
                    color: var(--app-danger, #dc3545);
                    margin-top: 0.25rem;
                }
                .btn-create {
                    background-color: var(--app-primary-accent);
                    border: none;
                    color: #000;
                    font-weight: 600;
                    padding: 0.5rem 1.5rem;
                    border-radius: 8px;
                }
                .btn-create:hover {
                    background-color: var(--app-primary-accent);
                    opacity: 0.9;
                    color: #000;
                }
                .btn-cancel {
                    background-color: transparent;
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-secondary);
                    font-weight: 600;
                    padding: 0.5rem 1.5rem;
                    border-radius: 8px;
                }
                .btn-cancel:hover {
                    background-color: var(--app-bg-alt);
                    color: var(--app-text-primary);
                }
            `}</style>
            <Modal.Header closeButton closeVariant="white">
                <Modal.Title className="fw-semibold" style={{ fontSize: '1.1rem' }}>
                    <span className="me-2">📁</span> New Project
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    <Form.Group className="mb-3">
                        <Form.Label>Project Name</Form.Label>
                        <Form.Control
                            type="text"
                            placeholder="e.g. Highway 5 Bridge Replacement"
                            value={projectName}
                            onChange={(e) => setProjectName(e.target.value)}
                            isInvalid={validated && !projectName.trim()}
                        />
                        {validated && !projectName.trim() ? (
                            <div className="invalid-feedback-inline">Please enter a Project Name.</div>
                        ) : (
                            <div className="help-text">You can rename this later.</div>
                        )}
                    </Form.Group>

                    <Form.Group className="mb-3">
                        <Form.Label>Country</Form.Label>
                        <Form.Select
                            value={country}
                            onChange={(e) => setCountry(e.target.value)}
                            isInvalid={validated && !country}
                        >
                            <option value="">— Select country —</option>
                            {COUNTRIES.map((c) => (
                                <option key={c} value={c}>{c}</option>
                            ))}
                        </Form.Select>
                        {validated && !country ? (
                            <div className="invalid-feedback-inline">Please select a Country.</div>
                        ) : (
                            <div className="help-text">Cannot be changed after project creation.</div>
                        )}
                    </Form.Group>

                    <Form.Group className="mb-3">
                        <Form.Label>Currency</Form.Label>
                        <Form.Select
                            value={currency}
                            onChange={(e) => setCurrency(e.target.value)}
                            isInvalid={validated && !currency}
                        >
                            <option value="">— Select currency —</option>
                            {CURRENCIES.map((c) => (
                                <option key={c} value={c}>{c}</option>
                            ))}
                        </Form.Select>
                        {validated && !currency ? (
                            <div className="invalid-feedback-inline">Please select a Currency.</div>
                        ) : (
                            <div className="help-text">Cannot be changed after project creation.</div>
                        )}
                    </Form.Group>

                    <Form.Group className="mb-3">
                        <Form.Label>Unit System</Form.Label>
                        <Form.Select
                            value={unitSystem}
                            onChange={(e) => setUnitSystem(e.target.value)}
                            isInvalid={validated && !unitSystem}
                        >
                            {UNIT_SYSTEM_OPTIONS.map((u) => (
                                <option key={u} value={u}>{u}</option>
                            ))}
                        </Form.Select>
                        {validated && !unitSystem ? (
                            <div className="invalid-feedback-inline">Please select a Unit System.</div>
                        ) : (
                            <div className="help-text">Cannot be changed after project creation.</div>
                        )}
                    </Form.Group>

                    <Form.Group className="mb-0">
                        <Form.Label>Material Suggestions (SOR) — optional</Form.Label>
                        <Form.Select
                            value={sorDatabase}
                            onChange={(e) => setSorDatabase(e.target.value)}
                        >
                            <option value="">— None (choose later) —</option>
                            {Object.keys(materialCatalog).map((key) => (
                                <option key={key} value={key}>{key}</option>
                            ))}
                        </Form.Select>
                        <div className="help-text">
                            Schedule of Rates database that auto-suggests material names,
                            rates, and emission factors. Can be set or changed anytime in
                            General Information.
                        </div>
                    </Form.Group>
                </Form>
            </Modal.Body>
            <Modal.Footer className="gap-2">
                <Button className="btn-create" onClick={handleCreate}>
                    Create Project
                </Button>
                <Button className="btn-cancel" onClick={onHide}>
                    Cancel
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default NewProjectModal;

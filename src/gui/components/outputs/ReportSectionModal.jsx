/* eslint-disable no-unused-vars */
import React, { useState } from 'react';
import { Modal, Button, Form, Accordion, Row, Col } from 'react-bootstrap';
import { FaFilePdf, FaCheckSquare, FaSquare } from 'react-icons/fa';
import { SECTION_KEYS } from './reportSections.js';

export { REPORT_SECTIONS, SECTION_KEYS } from './reportSections.js';

const SUBSECTION_MAP = {
    "Bridge geometry and description": [
        { label: "Bridge Data Summary", key: SECTION_KEYS.KEY_SHOW_BRIDGE_DESC },
    ],
    "User note": [
        { label: "Financial Data", key: SECTION_KEYS.KEY_SHOW_FINANCIAL },
    ],
    "Construction data": [
        { label: "Construction materials", key: SECTION_KEYS.KEY_SHOW_CONSTRUCTION },
        { label: "Maintenance and end-of-life inputs", key: SECTION_KEYS.KEY_SHOW_USE_STAGE },
        { label: "Recycling data", key: SECTION_KEYS.KEY_SHOW_RECYCLING },
    ],
    "Traffic data": [
        { label: "Average daily traffic", key: SECTION_KEYS.KEY_SHOW_AVG_TRAFFIC },
        { label: "Road and traffic data", key: SECTION_KEYS.KEY_SHOW_ROAD_TRAFFIC },
        { label: "Peak hour distribution", key: SECTION_KEYS.KEY_SHOW_PEAK_HOUR },
    ],
    "Environmental input data": [
        { label: "Social cost of carbon", key: SECTION_KEYS.KEY_SHOW_SOCIAL_CARBON },
        { label: "Material emission factors", key: SECTION_KEYS.KEY_SHOW_MATERIAL_EMISSION },
        { label: "Traffic diversion emissions", key: SECTION_KEYS.KEY_SHOW_VEHICLE_EMISSION },
        { label: "On-site emissions", key: SECTION_KEYS.KEY_SHOW_ONSITE_EMISSION },
        { label: "Transport emissions", key: SECTION_KEYS.KEY_SHOW_TRANSPORT_EMISSION },
    ],
};

const INITIAL_STATE = Object.values(SECTION_KEYS).reduce((acc, key) => {
    acc[key] = true; // Default all to true
    return acc;
}, {});

const ReportSectionModal = ({ show, onHide, onConfirm, confirmLabel = 'Generate PDF Report' }) => {
    const [selections, setSelections] = useState(INITIAL_STATE);

    const handleToggle = (key) => {
        setSelections(prev => ({ ...prev, [key]: !prev[key] }));
    };

    const handleToggleGroup = (groupKey, value) => {
        const groupItems = SUBSECTION_MAP[groupKey] || [];
        const newSelections = { ...selections };
        groupItems.forEach(item => {
            newSelections[item.key] = value;
        });
        setSelections(newSelections);
    };

    const handleSelectAll = (value) => {
        const newSelections = {};
        Object.keys(selections).forEach(key => {
            newSelections[key] = value;
        });
        setSelections(newSelections);
    };

    return (
        <Modal 
            show={show} 
            onHide={onHide} 
            size="lg" 
            centered
            contentClassName="report-modal-content"
        >
            <Modal.Header closeButton style={{ borderBottom: '1px solid var(--app-border-light)', backgroundColor: 'var(--app-bg-card)' }}>
                <Modal.Title className="d-flex align-items-center" style={{ color: 'var(--app-primary-accent)', gap: '10px' }}>
                    <FaFilePdf /> Report Customization
                </Modal.Title>
            </Modal.Header>
            <Modal.Body className="overflow-y-auto" style={{ backgroundColor: 'var(--app-bg-main)', color: 'var(--app-text-primary)', maxHeight: '70vh' }}>
                <div className="mb-4 d-flex justify-content-between align-items-center">
                    <p className="text-muted mb-0" style={{ fontSize: '0.9rem' }}>
                        Select the sections and tables to include in your professional LCCA report.
                    </p>
                    <div className="d-flex gap-2">
                        <Button variant="outline-secondary" size="sm" onClick={() => handleSelectAll(true)}>Select All</Button>
                        <Button variant="outline-secondary" size="sm" onClick={() => handleSelectAll(false)}>Deselect All</Button>
                    </div>
                </div>

                <div className="report-sections-tree">
                    {/* Top Level Sections */}
                    <div className="mb-3 p-3 rounded" style={{ backgroundColor: 'var(--app-bg-card)', border: '1px solid var(--app-border-light)' }}>
                        <h6 className="mb-3 fw-bold" style={{ color: 'var(--app-primary-accent)' }}>Main Sections</h6>
                        <Row>
                            <Col md={4}>
                                <Form.Check 
                                    type="checkbox"
                                    id="check-title-page"
                                    label="Title Page"
                                    checked={selections[SECTION_KEYS.KEY_SHOW_TITLE_PAGE]}
                                    onChange={() => handleToggle(SECTION_KEYS.KEY_SHOW_TITLE_PAGE)}
                                />
                            </Col>
                            <Col md={4}>
                                <Form.Check 
                                    type="checkbox"
                                    id="check-intro"
                                    label="Introduction"
                                    checked={selections[SECTION_KEYS.KEY_SHOW_INTRODUCTION]}
                                    onChange={() => handleToggle(SECTION_KEYS.KEY_SHOW_INTRODUCTION)}
                                />
                            </Col>
                            <Col md={4}>
                                <Form.Check 
                                    type="checkbox"
                                    id="check-results"
                                    label="LCCA Results"
                                    checked={selections[SECTION_KEYS.KEY_SHOW_LCCA_RESULTS]}
                                    onChange={() => handleToggle(SECTION_KEYS.KEY_SHOW_LCCA_RESULTS)}
                                />
                            </Col>
                        </Row>
                    </div>

                    {/* Input Data Detail */}
                    <h6 className="mb-3 fw-bold" style={{ color: 'var(--app-primary-accent)', paddingLeft: '5px' }}>Input Data Tables</h6>
                    <Accordion defaultActiveKey="0">
                        {Object.keys(SUBSECTION_MAP).map((group, idx) => (
                            <Accordion.Item eventKey={idx.toString()} key={group} style={{ backgroundColor: 'transparent', border: '1px solid var(--app-border-light)', marginBottom: '10px', borderRadius: '8px', overflow: 'hidden' }}>
                                <Accordion.Header style={{ backgroundColor: 'var(--app-bg-card)' }}>
                                    <div className="d-flex align-items-center gap-3 w-100 pe-3">
                                        <span className="fw-bold">{group}</span>
                                        <div className="ms-auto">
                                            <Button 
                                                variant="link" 
                                                size="sm" 
                                                className="text-decoration-none p-0 me-2"
                                                onClick={(e) => { e.stopPropagation(); handleToggleGroup(group, true); }}
                                                style={{ fontSize: '0.75rem', color: 'var(--app-primary-accent)' }}
                                            >
                                                All
                                            </Button>
                                            <Button 
                                                variant="link" 
                                                size="sm" 
                                                className="text-decoration-none p-0"
                                                onClick={(e) => { e.stopPropagation(); handleToggleGroup(group, false); }}
                                                style={{ fontSize: '0.75rem', color: 'var(--app-text-muted)' }}
                                            >
                                                None
                                            </Button>
                                        </div>
                                    </div>
                                </Accordion.Header>
                                <Accordion.Body style={{ backgroundColor: 'var(--app-bg-card)' }}>
                                    <Row>
                                        {SUBSECTION_MAP[group].map((item) => (
                                            <Col md={6} key={item.key} className="mb-2">
                                                <Form.Check 
                                                    type="checkbox"
                                                    id={`check-${item.key}`}
                                                    label={item.label}
                                                    checked={selections[item.key]}
                                                    onChange={() => handleToggle(item.key)}
                                                    style={{ fontSize: '0.85rem' }}
                                                />
                                            </Col>
                                        ))}
                                    </Row>
                                </Accordion.Body>
                            </Accordion.Item>
                        ))}
                    </Accordion>
                </div>
            </Modal.Body>
            <Modal.Footer style={{ borderTop: '1px solid var(--app-border-light)', backgroundColor: 'var(--app-bg-card)' }}>
                <Button variant="outline-secondary" onClick={onHide}>
                    Cancel
                </Button>
                <Button 
                    variant="primary" 
                    className="fw-bold"
                    onClick={() => onConfirm(selections)}
                    style={{ backgroundColor: 'var(--app-primary-accent)', borderColor: 'var(--app-primary-accent)', color: '#000' }}
                >
                    {confirmLabel}
                </Button>
            </Modal.Footer>
            <style>{`
                .report-modal-content {
                    border: 1px solid var(--app-border-mid);
                    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                }
                .accordion-button:not(.collapsed) {
                    background-color: var(--app-bg-main);
                    color: var(--app-primary-accent);
                    box-shadow: none;
                }
                .accordion-button::after {
                    filter: invert(var(--app-icon-invert));
                }
                .form-check-input:checked {
                    background-color: var(--app-primary-accent);
                    border-color: var(--app-primary-accent);
                }
            `}</style>
        </Modal>
    );
};

export default ReportSectionModal;

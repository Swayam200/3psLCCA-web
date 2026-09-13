import { useState } from 'react';
import { Modal, Row, Col, ListGroup } from 'react-bootstrap';

const VersionHistoryModal = ({ show, onHide }) => {
    const [selectedChunk, setSelectedChunk] = useState('analysis_period');

    const chunks = [
        'analysis_period',
        'bridge_data',
        'demolition_data',
        'diversion_emissions',
        'financial_data',
        'general_info',
        'machinery_emissions_data',
        'maintenance_data',
        'material_emissions_data',
        'miscellaneous_construction_work',
        'outputs_data',
        'social_cost_of_carbon',
        'substructure',
        'superstructure',
        'traffic_data',
        'transportation_emissions_data'
    ];

    return (
        <Modal 
            show={show} 
            onHide={onHide} 
            centered 
            dialogClassName="vh-modal-dialog"
            contentClassName="version-history-modal"
            style={{ fontFamily: '"Segoe UI", sans-serif' }}
        >
            <style>{`
                .vh-modal-dialog {
                    max-width: 500px;
                }
                .version-history-modal {
                    background-color: var(--app-bg-card);
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-primary);
                    border-radius: 12px;
                }
                .version-history-modal .modal-header {
                    border-bottom: none;
                    padding: 1.25rem 1.25rem 0.25rem 1.25rem;
                    align-items: flex-start;
                }
                .version-history-modal .modal-title {
                    font-size: 1rem;
                    font-weight: 700;
                    margin-bottom: 0.25rem;
                    display: flex;
                    align-items: center;
                }
                .version-history-modal .modal-subtitle {
                    font-size: 0.75rem;
                    color: var(--app-text-primary);
                    opacity: 0.7;
                    line-height: 1.3;
                    margin-top: 0.25rem;
                }
                .version-history-modal .modal-body {
                    padding: 0 1.25rem 1.25rem 1.25rem;
                }
                .version-history-modal .modal-footer {
                    border-top: none;
                    padding: 0 1.25rem 1.25rem 1.25rem;
                    display: flex;
                    justify-content: flex-end;
                    align-items: center;
                    gap: 0.75rem;
                }
                .vh-column-title {
                    font-size: 0.65rem;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 0.05em;
                    margin-bottom: 0.5rem;
                    margin-top: 0.5rem;
                    color: var(--app-text-primary);
                }
                .vh-list-group {
                    background-color: transparent;
                    border-radius: 0;
                }
                .vh-list-item {
                    background-color: transparent;
                    border: none;
                    color: var(--app-text-secondary);
                    padding: 0.4rem 0.6rem;
                    cursor: pointer;
                    transition: all 0.2s ease;
                    border-left: 3px solid transparent;
                    font-size: 0.75rem;
                }
                .vh-list-item:hover {
                    background-color: var(--app-bg-alt);
                    color: var(--app-text-primary);
                }
                .vh-list-item.active {
                    background-color: var(--app-bg-alt);
                    color: var(--app-text-primary);
                    border-left: 3px solid var(--app-primary-accent);
                    font-weight: 600;
                }
                .vh-version-item {
                    color: var(--app-text-primary);
                    font-size: 0.75rem;
                    padding: 0.4rem 0;
                }
                .vh-btn-close {
                    background-color: transparent;
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-primary);
                    font-weight: 600;
                    padding: 0.35rem 1rem;
                    border-radius: 6px;
                    transition: all 0.2s;
                    font-size: 0.75rem;
                }
                .vh-btn-close:hover {
                    background-color: var(--app-bg-alt);
                    color: var(--app-text-primary);
                }
                .vh-btn-rollback {
                    background-color: transparent;
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-secondary);
                    font-weight: 600;
                    padding: 0.35rem 0.8rem;
                    border-radius: 6px;
                    transition: all 0.2s;
                    display: flex;
                    align-items: center;
                    gap: 0.4rem;
                    font-size: 0.75rem;
                }
                .vh-btn-rollback:hover:not(:disabled) {
                    background-color: var(--app-bg-alt);
                    color: var(--app-text-primary);
                }
                .vh-btn-rollback:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }
                .vh-divider {
                    border-top: 1px solid var(--app-border-light);
                    margin: 0.75rem -1.25rem 0 -1.25rem;
                }
                .vh-scrollable::-webkit-scrollbar {
                    width: 4px;
                }
                .vh-scrollable::-webkit-scrollbar-track {
                    background: transparent;
                }
                .vh-scrollable::-webkit-scrollbar-thumb {
                    background-color: var(--app-border-mid);
                    border-radius: 4px;
                }
                .vh-scrollable::-webkit-scrollbar-thumb:hover {
                    background-color: var(--app-primary-accent);
                }
            `}</style>
            
            <Modal.Header closeButton closeVariant="white">
                <div className="d-flex flex-column">
                    <Modal.Title>
                        <div className="d-inline-flex position-relative" style={{ width: '16px', height: '16px', marginRight: '10px' }}>
                            <div className="position-absolute" style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#ff6b35', top: 0, left: 0 }}></div>
                            <div className="position-absolute" style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#8bc34a', top: 0, right: 0 }}></div>
                            <div className="position-absolute" style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: '#a9b0fc', bottom: 0, left: '3px' }}></div>
                        </div>
                        Version Rollback
                    </Modal.Title>
                    <div className="modal-subtitle">
                        Select a chunk on the left, then choose which saved version to restore on the right.
                        Only the selected chunk is affected.
                    </div>
                </div>
            </Modal.Header>
            
            <Modal.Body>
                <div className="vh-divider"></div>
                <Row>
                    <Col xs={5} style={{ borderRight: '1px solid var(--app-border-light)', paddingRight: '0', paddingBottom: '0.25rem' }}>
                        <div className="vh-column-title px-2">Chunks</div>
                        <div className="vh-scrollable overflow-y-auto overflow-x-hidden" style={{ maxHeight: '300px', paddingRight: '4px' }}>
                            <ListGroup className="vh-list-group">
                                {chunks.map((chunk) => (
                                    <ListGroup.Item 
                                        key={chunk}
                                        className={`vh-list-item ${selectedChunk === chunk ? 'active' : ''}`}
                                        onClick={() => setSelectedChunk(chunk)}
                                    >
                                        {chunk}
                                    </ListGroup.Item>
                                ))}
                            </ListGroup>
                        </div>
                    </Col>
                    <Col xs={7} style={{ paddingLeft: '1.25rem' }}>
                        <div className="vh-column-title">Available Versions</div>
                        <div className="vh-scrollable overflow-y-auto overflow-x-hidden" style={{ maxHeight: '300px' }}>
                            <div className="vh-version-item">
                                Current - 2026-04-18 19:00:44
                            </div>
                        </div>
                    </Col>
                </Row>
            </Modal.Body>
            
            <Modal.Footer>
                <button type="button" className="vh-btn-close" onClick={onHide}>
                    Close
                </button>
                <button type="button" className="vh-btn-rollback" disabled>
                    <span>&#8617;</span> Roll Back to Selected Version
                </button>
            </Modal.Footer>
        </Modal>
    );
};

export default VersionHistoryModal;

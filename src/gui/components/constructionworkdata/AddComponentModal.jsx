import { useState } from 'react';
import { Modal, Button, Form } from 'react-bootstrap';

const AddComponentModal = ({ show, onHide, onAdd, defaultName }) => {
    const [name, setName] = useState(defaultName || '');
    const [prevShow, setPrevShow] = useState(show);
    if (show !== prevShow) {
        setPrevShow(show);
        if (show) setName(defaultName || '');
    }

    const handleAdd = () => {
        if (!name.trim()) return;
        if (onAdd) onAdd(name.trim());
        onHide();
    };

    return (
        <Modal
            show={show}
            onHide={onHide}
            centered
            contentClassName="add-component-modal"
            style={{ fontFamily: '"Segoe UI", sans-serif' }}
        >
            <style>{`
                .add-component-modal {
                    background-color: var(--app-bg-card);
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-primary);
                    border-radius: 12px;
                }
                .add-component-modal .modal-header {
                    border-bottom: 1px solid var(--app-border-light);
                    padding: 1rem 1.5rem;
                }
                .add-component-modal .modal-body {
                    padding: 1.5rem;
                }
                .add-component-modal .form-label {
                    font-size: 0.9rem;
                    font-weight: 600;
                    margin-bottom: 0.5rem;
                }
                .add-component-modal .form-control {
                    background-color: var(--app-bg-alt);
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-primary);
                    font-size: 0.9rem;
                    padding: 0.6rem;
                }
                .add-component-modal .form-control:focus {
                    background-color: var(--app-bg-alt);
                    border-color: var(--app-primary-accent);
                    box-shadow: 0 0 0 0.2rem color-mix(in srgb, var(--app-primary-accent) 15%, transparent);
                    color: var(--app-text-primary);
                }
                .add-component-modal .modal-actions {
                    display: flex;
                    justify-content: flex-end;
                    gap: 12px;
                    margin-top: 1.5rem;
                }
                .add-component-modal .btn-modal-cancel {
                    background-color: transparent;
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-primary);
                    font-weight: 600;
                    padding: 0.5rem 1.5rem;
                    border-radius: 8px;
                }
                .add-component-modal .btn-modal-cancel:hover {
                    background-color: var(--app-bg-alt);
                    color: var(--app-text-primary);
                }
                .add-component-modal .btn-modal-add {
                    background-color: var(--app-primary-accent);
                    border: none;
                    color: #000;
                    font-weight: 600;
                    padding: 0.5rem 1.5rem;
                    border-radius: 8px;
                }
                .add-component-modal .btn-modal-add:hover {
                    background-color: var(--app-primary-accent);
                    opacity: 0.9;
                    color: #000;
                }
            `}</style>
            <Modal.Header closeButton>
                <Modal.Title className="fw-bold" style={{ fontSize: '1.1rem' }}>
                    New Component
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    <Form.Group className="mb-0">
                        <Form.Label>Enter Component Name:</Form.Label>
                        <Form.Control
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                    e.preventDefault();
                                    handleAdd();
                                }
                            }}
                            autoFocus
                        />
                    </Form.Group>
                </Form>
                <div className="modal-actions">
                    <Button className="btn-modal-cancel" onClick={onHide}>
                        Cancel
                    </Button>
                    <Button className="btn-modal-add" onClick={handleAdd}>
                        Add
                    </Button>
                </div>
            </Modal.Body>
        </Modal>
    );
};

export default AddComponentModal;

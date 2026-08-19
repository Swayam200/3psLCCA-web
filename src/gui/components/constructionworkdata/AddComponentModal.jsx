import React, { useState, useEffect } from 'react';
import { Modal, Button, Form } from 'react-bootstrap';

const AddComponentModal = ({ show, onHide, onAdd, defaultName }) => {
    const [name, setName] = useState(defaultName || '');

    useEffect(() => {
        if (show) {
            setName(defaultName || '');
        }
    }, [show, defaultName]);

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
            backdropClassName="add-component-backdrop"
        >
            <style>{`
                .add-component-modal {
                    background-color: #2b2d3d;
                    border: 1px solid #1a1b26;
                    color: #ffffff;
                    border-radius: 12px;
                    overflow: hidden;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.5);
                }
                .add-component-modal .modal-header {
                    background-color: #3b3e51;
                    border-bottom: 1px solid #1a1b26;
                    padding: 0.5rem 1rem;
                    display: flex;
                    align-items: center;
                }
                .add-component-modal .modal-body {
                    padding: 1.5rem;
                }
                .add-component-modal .form-label {
                    font-size: 0.95rem;
                    font-weight: 600;
                    margin-bottom: 0.75rem;
                    color: #ffffff;
                }
                .add-component-modal .form-control {
                    background-color: #2b2d3d;
                    border: 2px solid #b794f6;
                    color: #ffffff;
                    font-size: 1rem;
                    padding: 0.75rem 1rem;
                    border-radius: 12px;
                }
                .add-component-modal .form-control:focus {
                    background-color: #2b2d3d;
                    border-color: #b794f6;
                    box-shadow: 0 0 0 0.25rem rgba(183, 148, 246, 0.25);
                    color: #ffffff;
                }
                .modal-actions {
                    display: flex;
                    justify-content: flex-end;
                    gap: 12px;
                    margin-top: 1.5rem;
                }
                .btn-modal-cancel {
                    background-color: transparent;
                    border: 1px solid #6b7280;
                    color: #ffffff;
                    font-weight: 600;
                    padding: 0.6rem 1.5rem;
                    border-radius: 12px;
                    transition: all 0.2s;
                }
                .btn-modal-cancel:hover {
                    background-color: #3b3e51;
                }
                .btn-modal-add {
                    background-color: #b794f6;
                    border: none;
                    color: #000000;
                    font-weight: 700;
                    padding: 0.6rem 2rem;
                    border-radius: 12px;
                    transition: all 0.2s;
                }
                .btn-modal-add:hover {
                    filter: brightness(0.9);
                }
                .mac-dots {
                    display: flex;
                    gap: 6px;
                    margin-right: 15px;
                }
                .mac-dot {
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                }
                .add-component-backdrop {
                    background-color: rgba(0,0,0,0.6);
                }
            `}</style>
            <Modal.Header>
                <div className="d-flex align-items-center w-100">
                    <div className="mac-dots">
                        <div className="mac-dot" style={{ backgroundColor: '#ff5f56' }}></div>
                        <div className="mac-dot" style={{ backgroundColor: '#5c5c5c' }}></div>
                        <div className="mac-dot" style={{ backgroundColor: '#27c93f' }}></div>
                    </div>
                    <Modal.Title className="fw-bold mx-auto pe-5" style={{ fontSize: '1.1rem', color: '#e5e7eb' }}>
                        New Component
                    </Modal.Title>
                </div>
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

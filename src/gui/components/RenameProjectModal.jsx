import { useState, useEffect } from 'react';
import { Modal, Button, Form } from 'react-bootstrap';

const RenameProjectModal = ({ show, onHide, onRename, currentName }) => {
    const [newName, setNewName] = useState(currentName || '');

    useEffect(() => {
        if (show) {
            // eslint-disable-next-line react-hooks/set-state-in-effect -- Opening the modal intentionally restores the current project name.
            setNewName(currentName || '');
        }
    }, [show, currentName]);

    const handleRename = () => {
        if (!newName.trim()) {
            alert('Project name cannot be empty.');
            return;
        }
        if (onRename) {
            onRename(newName);
        }
        onHide();
    };

    return (
        <Modal 
            show={show} 
            onHide={onHide} 
            centered 
            contentClassName="rename-project-modal"
            style={{ fontFamily: '"Segoe UI", sans-serif' }}
        >
            <style>{`
                .rename-project-modal {
                    background-color: var(--app-bg-card);
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-primary);
                    border-radius: 12px;
                }
                .rename-project-modal .modal-header {
                    border-bottom: 1px solid var(--app-border-light);
                    padding: 1rem 1.5rem;
                }
                .rename-project-modal .modal-body {
                    padding: 1.5rem;
                }
                .rename-project-modal .modal-footer {
                    border-top: none;
                    padding: 0 1.5rem 1.5rem 1.5rem;
                }
                .rename-project-modal .form-label {
                    font-size: 0.9rem;
                    font-weight: 600;
                    margin-bottom: 0.5rem;
                }
                .rename-project-modal .form-control {
                    background-color: var(--app-bg-alt);
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-primary);
                    font-size: 0.9rem;
                    padding: 0.6rem;
                }
                .rename-project-modal .form-control:focus {
                    background-color: var(--app-bg-alt);
                    border-color: var(--app-primary-accent);
                    box-shadow: 0 0 0 0.2rem rgba(154, 205, 50, 0.1);
                    color: var(--app-text-primary);
                }
                .btn-save {
                    background-color: var(--app-primary-accent);
                    border: none;
                    color: #000;
                    font-weight: 600;
                    padding: 0.5rem 1.5rem;
                    border-radius: 8px;
                }
                .btn-save:hover {
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
                <Modal.Title className="d-flex align-items-center fw-semibold" style={{ fontSize: '1.1rem' }}>
                    <div className="d-inline-flex position-relative" style={{ width: '20px', height: '20px', marginRight: '12px' }}>
                        <div className="position-absolute" style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#ff6b35', top: 0, left: 0 }}></div>
                        <div className="position-absolute" style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#8bc34a', top: 0, right: 0 }}></div>
                        <div className="position-absolute" style={{ width: '12px', height: '12px', borderRadius: '50%', backgroundColor: '#a9b0fc', bottom: 0, left: '4px' }}></div>
                    </div>
                    Rename Project
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <Form>
                    <Form.Group className="mb-0">
                        <Form.Label>New name:</Form.Label>
                        <Form.Control 
                            type="text" 
                            placeholder="Enter new project name" 
                            value={newName}
                            onChange={(e) => setNewName(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                    e.preventDefault();
                                    handleRename();
                                }
                            }}
                            autoFocus
                        />
                    </Form.Group>
                </Form>
            </Modal.Body>
            <Modal.Footer className="gap-2">
                <Button className="btn-save" onClick={handleRename}>
                    OK
                </Button>
                <Button className="btn-cancel" onClick={onHide}>
                    Cancel
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default RenameProjectModal;

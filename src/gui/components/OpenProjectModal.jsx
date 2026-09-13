import { useState } from 'react';
import { Modal, Button, ListGroup } from 'react-bootstrap';
import { FaFolderOpen, FaFileUpload, FaClock } from 'react-icons/fa';

const OpenProjectModal = ({ show, onHide, onOpen }) => {
    const [recentProjects] = useState([
        { id: 1, name: 'Mumbai-Steel-2L-35m-F', date: '2026-05-01', country: 'India' },
        { id: 2, name: 'Highway_Bridge_Assessment_01', date: '2026-04-28', country: 'USA' },
        { id: 3, name: 'Delhi_Flyover_Phase_2', date: '2026-04-15', country: 'India' }
    ]);

    const handleImport = (e) => {
        const file = e.target.files[0];
        if (file) {
            const reader = new FileReader();
            reader.onload = (event) => {
                try {
                    const data = JSON.parse(event.target.result);
                    onOpen(data);
                    onHide();
                } catch {
                    alert('Invalid project file format.');
                }
            };
            reader.readAsText(file);
        }
    };

    return (
        <Modal 
            show={show} 
            onHide={onHide} 
            centered 
            contentClassName="open-project-modal"
            style={{ fontFamily: '"Segoe UI", sans-serif' }}
        >
            <style>{`
                .open-project-modal {
                    background-color: var(--app-bg-card);
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-primary);
                    border-radius: 12px;
                }
                .open-project-modal .modal-header {
                    border-bottom: 1px solid var(--app-border-light);
                    padding: 1rem 1.5rem;
                }
                .open-project-modal .modal-body {
                    padding: 1.5rem;
                }
                .project-item {
                    background-color: var(--app-bg-alt);
                    border: 1px solid var(--app-border-mid);
                    color: var(--app-text-primary);
                    margin-bottom: 10px;
                    border-radius: 8px !important;
                    transition: all 0.2s ease;
                    cursor: pointer;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    padding: 12px 16px;
                }
                .project-item:hover {
                    border-color: var(--app-primary-accent);
                    background-color: rgba(154, 205, 50, 0.05);
                }
                .import-zone {
                    border: 2px dashed var(--app-border-mid);
                    border-radius: 8px;
                    padding: 20px;
                    text-align: center;
                    margin-top: 20px;
                    cursor: pointer;
                    transition: all 0.2s ease;
                }
                .import-zone:hover {
                    border-color: var(--app-primary-accent);
                    background-color: rgba(154, 205, 50, 0.05);
                }
            `}</style>
            <Modal.Header closeButton closeVariant="white">
                <Modal.Title className="fw-semibold" style={{ fontSize: '1.1rem' }}>
                    <FaFolderOpen className="me-2" /> Open Project
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                <div className="mb-3" style={{ fontSize: '0.9rem', fontWeight: '600', color: 'var(--app-text-secondary)' }}>
                    <FaClock className="me-2" /> Recent Projects
                </div>
                <ListGroup variant="flush">
                    {recentProjects.map(project => (
                        <div key={project.id} className="project-item" onClick={() => onOpen(project)}>
                            <div>
                            <div className="fw-semibold">{project.name}</div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--app-text-muted)' }}>{project.country} • Last modified: {project.date}</div>
                            </div>
                            <Button variant="link" className="p-0" style={{ color: 'var(--app-primary-accent)' }}>Open</Button>
                        </div>
                    ))}
                </ListGroup>

                <div className="import-zone" onClick={() => document.getElementById('project-import').click()}>
                    <FaFileUpload size={24} className="mb-2" style={{ color: 'var(--app-primary-accent)' }} />
                    <div className="fw-semibold" style={{ fontSize: '0.9rem' }}>Import Project File</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--app-text-muted)' }}>Drag and drop or click to upload .json</div>
                    <input 
                        id="project-import" 
                        type="file" 
                        accept=".json" 
                        className="d-none"
                        onChange={handleImport}
                    />
                </div>
            </Modal.Body>
            <Modal.Footer>
                <Button 
                    variant="outline-secondary" 
                    onClick={onHide}
                    style={{ border: '1px solid var(--app-border-mid)', color: 'var(--app-text-secondary)' }}
                >
                    Close
                </Button>
            </Modal.Footer>
        </Modal>
    );
};

export default OpenProjectModal;

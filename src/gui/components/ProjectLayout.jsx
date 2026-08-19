import React, { useState } from 'react';
import { Offcanvas } from 'react-bootstrap';
import ProjectNavbar from './ProjectNavbar';
import Sidebar from './Sidebar';

const ProjectLayout = ({ children, activeNode, setActiveNode, onBackToHome, checkpoints, onSaveCheckpoint, onDeleteCheckpoint, onNewProject, onOpenProject, addLog, isLocked, setIsLocked, projectName, projectData, onRenameProject, onExportProject, projectId }) => {
    const [showMobileSidebar, setShowMobileSidebar] = useState(false);

    return (
        <div className="d-flex flex-column overflow-hidden" style={{ height: '100vh', width: '100vw' }}>
            <ProjectNavbar 
                projectId={projectId}
                onBackToHome={onBackToHome} 
                setActiveNode={setActiveNode} 
                onSaveCheckpoint={onSaveCheckpoint}
                onDeleteCheckpoint={onDeleteCheckpoint}
                onNewProject={onNewProject}
                onOpenProject={onOpenProject}
                checkpoints={checkpoints}
                addLog={addLog}
                isLocked={isLocked}
                setIsLocked={setIsLocked}
                projectName={projectName}
                projectData={projectData}
                onRenameProject={onRenameProject}
                onExportProject={onExportProject}
                onToggleSidebar={() => setShowMobileSidebar(true)}
            />
            <div className="d-flex flex-grow-1 overflow-hidden">
                <div className="d-none d-md-flex flex-shrink-0 h-100">
                    <Sidebar activeNode={activeNode} setActiveNode={setActiveNode} />
                </div>
                <div className="flex-grow-1 overflow-y-auto" style={{ backgroundColor: 'var(--app-bg-main)', transition: 'background-color 0.3s ease' }}>
                    {children}
                </div>
            </div>

            <Offcanvas show={showMobileSidebar} onHide={() => setShowMobileSidebar(false)} placement="start" style={{ width: '280px', backgroundColor: 'var(--app-bg-card)', borderRight: '1px solid var(--app-border-light)' }}>
                <Offcanvas.Header closeButton closeVariant={document.documentElement.getAttribute('data-bs-theme') === 'dark' ? 'white' : undefined} style={{ borderBottom: '1px solid var(--app-border-light)' }}>
                    <Offcanvas.Title style={{ color: 'var(--app-text-primary)' }}>Sections</Offcanvas.Title>
                </Offcanvas.Header>
                <Offcanvas.Body className="p-0 overflow-hidden d-flex flex-column">
                    <Sidebar 
                        activeNode={activeNode} 
                        setActiveNode={(node) => { setActiveNode(node); setShowMobileSidebar(false); }} 
                        isMobile={true} 
                    />
                </Offcanvas.Body>
            </Offcanvas>
        </div>
    );
};

export default ProjectLayout;

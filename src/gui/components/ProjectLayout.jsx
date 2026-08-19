import React, { useState } from 'react';
import { Offcanvas } from 'react-bootstrap';
import ProjectNavbar from './ProjectNavbar';
import Sidebar from './Sidebar';
import { FaLock } from 'react-icons/fa';


// The AI assistant only exists in builds made with VITE_AI_ENABLED=true. The
// comparison must stay inline (not a shared constant) so Vite folds it to a
// literal and drops the dynamic import — and with it the whole src/lib/ai
// package — from flag-off bundles (enforced by tests/ai/bundleExclusion.test.js).
const AI_ENABLED = import.meta.env.VITE_AI_ENABLED === 'true';
const AiFabLazy = AI_ENABLED ? React.lazy(() => import('./ai/AiFab.jsx')) : null;

const LockedOverlay = () => {
    const [showBanner, setShowBanner] = React.useState(false);
    const [timer, setTimer] = React.useState(null);

    const handleClick = () => {
        setShowBanner(true);
        if (timer) clearTimeout(timer);
        const t = setTimeout(() => {
            setShowBanner(false);
        }, 2000);
        setTimer(t);
    };

    React.useEffect(() => {
        return () => {
            if (timer) clearTimeout(timer);
        };
    }, [timer]);

    return (
        <>
            <div 
                style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    zIndex: 999,
                    cursor: 'not-allowed',
                    backgroundColor: 'rgba(0, 0, 0, 0.01)',
                }}
                onClick={handleClick}
            />
            <div 
                style={{
                    position: 'fixed',
                    top: '50%',
                    left: '50%',
                    transform: `translate(-50%, -50%) scale(${showBanner ? 1 : 0.95})`,
                    backgroundColor: 'var(--app-bg-card, #ffffff)',
                    color: 'var(--app-text-primary, #212529)',
                    border: '1.5px solid var(--app-primary-accent, #6366f1)',
                    padding: '12px 24px',
                    borderRadius: '8px',
                    boxShadow: '0 8px 30px rgba(0, 0, 0, 0.2)',
                    fontSize: '0.95rem',
                    fontWeight: '500',
                    pointerEvents: 'none',
                    zIndex: 1000,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    opacity: showBanner ? 1 : 0,
                    transition: 'opacity 0.25s ease-in-out, transform 0.25s ease-in-out',
                }}
            >
                <FaLock style={{ color: 'var(--app-primary-accent, #6366f1)', fontSize: '1.1em' }} />
                Project is locked - click Unlock in the toolbar to edit.
            </div>
        </>
    );
};

const ProjectLayout = ({ children, activeNode, setActiveNode, onBackToHome, checkpoints, onSaveCheckpoint, onDeleteCheckpoint, onNewProject, onOpenProject, addLog, isLocked, setIsLocked, projectName, projectData, onRenameProject, onExportProject, projectId, saveState }) => {
    const [showMobileSidebar, setShowMobileSidebar] = useState(false);

    return (
        <div className="d-flex flex-column overflow-hidden" style={{ height: '100vh', width: '100vw' }}>
            <ProjectNavbar 
                projectId={projectId}
                onBackToHome={onBackToHome} 
                setActiveNode={setActiveNode} 
                onNewProject={onNewProject}
                onOpenProject={onOpenProject}
                addLog={addLog}
                isLocked={isLocked}
                setIsLocked={setIsLocked}
                projectName={projectName}
                projectData={projectData}
                onRenameProject={onRenameProject}
                onExportProject={onExportProject}
                saveState={saveState}
                onToggleSidebar={() => setShowMobileSidebar(true)}
            />
            <div className="d-flex flex-grow-1 overflow-hidden">
                <div className="d-none d-md-flex flex-shrink-0 h-100">
                    <Sidebar activeNode={activeNode} setActiveNode={setActiveNode} />
                </div>
                <div className="flex-grow-1 overflow-y-auto" style={{ backgroundColor: 'var(--app-bg-main)', transition: 'background-color 0.3s ease' }}>
                    <div style={{ position: 'relative', minHeight: '100%' }}>
                        {children}
                        {isLocked && activeNode !== 'Results' && activeNode !== 'Outputs' && activeNode !== 'Logs' && <LockedOverlay />}
                    </div>
                </div>
            </div>
            {AiFabLazy && (
                <React.Suspense fallback={null}>
                    <AiFabLazy activeNode={activeNode} />
                </React.Suspense>
            )}

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

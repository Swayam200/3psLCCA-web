/* eslint-disable no-unused-vars */
import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Navbar, Nav, NavDropdown, Button, Tooltip, OverlayTrigger, Spinner } from 'react-bootstrap';
import { FaHome, FaLock, FaLockOpen, FaInfoCircle, FaCheckCircle, FaUndo, FaSave, FaCalculator, FaHistory, FaFolderOpen, FaPlus, FaSignOutAlt, FaCog, FaExclamationTriangle, FaBars } from 'react-icons/fa';
import NewProjectModal from './NewProjectModal';
import OpenProjectModal from './OpenProjectModal';
import RenameProjectModal from './RenameProjectModal';
import VersionHistoryModal from './VersionHistoryModal';
import HelpModal from './HelpModal';
import ProjectInfoModal from './ProjectInfoModal';
import Logo3psLCCA from '../../assets/logo-3psLCCA.svg';

const NavItemLink = ({ href, children, onClick, icon: Icon }) => {
    const [hover, setHover] = useState(false);
    return (
        <Nav.Link 
            href={href} 
            className="px-2 py-1 mx-1 rounded d-flex align-items-center justify-content-center"
            style={{ 
                color: hover ? 'var(--app-primary-accent)' : 'var(--app-text-primary)', 
                backgroundColor: hover ? 'var(--app-bg-alt)' : 'transparent',
                fontSize: '14px',
                transition: 'all 0.2s ease',
                minWidth: Icon ? '36px' : 'auto',
                height: '32px'
            }}
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
            onClick={(e) => {
                if (onClick) {
                    e.preventDefault();
                    onClick();
                }
            }}
        >
            {Icon ? <Icon size={18} /> : children}
        </Nav.Link>
    );
};

const CustomDropdown = ({ title, id, items, icon: Icon }) => {
    const [hover, setHover] = useState(false);
    return (
        <NavDropdown 
            title={Icon ? <Icon size={16} className="me-1" /> : title} 
            id={id} 
            className="px-1 custom-nav-dropdown d-flex align-items-center"
            style={{
                color: hover ? 'var(--app-primary-accent)' : 'var(--app-text-primary)', 
                backgroundColor: hover ? 'var(--app-bg-alt)' : 'transparent',
                borderRadius: '4px',
                transition: 'all 0.2s ease'
            }}
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
        >
            {items.map((item, idx) => (
                item === "divider" 
                ? <NavDropdown.Divider key={idx} style={{ borderColor: 'var(--app-border-light)' }} />
                : <NavDropdown.Item 
                    key={idx} 
                    href={item.href} 
                    onClick={(e) => {
                        if (item.onClick) {
                            e.preventDefault();
                            item.onClick();
                        }
                    }}
                    className="custom-dropdown-item d-flex align-items-center"
                    style={{ fontSize: '13px', color: 'var(--app-text-primary)', padding: '6px 16px' }}
                  >
                      {item.icon && <item.icon size={14} className="me-2" style={{ opacity: 0.8 }} />}
                      {item.label}
                  </NavDropdown.Item>
            ))}
        </NavDropdown>
    );
};

const CustomNavBtn = ({ variant, outlineColor, outlineHoverBg, children, icon: Icon, ...props }) => {
    const [hover, setHover] = useState(false);
    const borderCol = hover ? 'var(--app-primary-accent)' : outlineColor;
    const bgCol = hover ? outlineHoverBg : 'transparent';
    const textCol = hover ? 'var(--app-bg-card)' : 'var(--app-text-secondary)';
    const finalOutlineHoverBg = hover ? 'var(--app-primary-accent)' : bgCol;

    return (
        <Button 
            variant={variant} 
            size="sm" 
            className="d-flex align-items-center justify-content-center"
            style={{ 
                borderColor: variant === 'outline-secondary' ? borderCol : 'transparent',
                backgroundColor: variant === 'outline-secondary' ? (hover ? 'var(--app-primary-accent)' : 'transparent') : 'transparent',
                color: variant === 'outline-secondary' ? (hover ? 'var(--app-bg-card)' : 'var(--app-text-secondary)') : 'var(--app-text-secondary)',
                fontSize: '13px',
                padding: Icon && !children ? '4px 8px' : '4px 12px',
                transition: 'all 0.2s ease',
                height: '32px',
                borderRadius: '4px'
            }}
            onMouseEnter={() => setHover(true)}
            onMouseLeave={() => setHover(false)}
            {...props}
        >
            {Icon && <Icon size={14} className={children ? "me-2" : ""} />}
            {children}
        </Button>
    );
};

const ProjectNavbar = ({ onBackToHome, setActiveNode, onNewProject, onOpenProject, addLog, isLocked, setIsLocked, projectName, projectData, onRenameProject, onExportProject, projectId, saveState = 'saved', onToggleSidebar }) => {
    const [showNewProjectModal, setShowNewProjectModal] = useState(false);
    const [showOpenProjectModal, setShowOpenProjectModal] = useState(false);
    const [showRenameModal, setShowRenameModal] = useState(false);
    const [showVersionModal, setShowVersionModal] = useState(false);
    const [showContactModal, setShowContactModal] = useState(false);
    const [showFeedbackModal, setShowFeedbackModal] = useState(false);
    const [showInfoModal, setShowInfoModal] = useState(false);

    return (
        <Navbar expand="lg" className="px-3 border-bottom custom-project-nav flex-shrink-0" style={{ 
            backgroundColor: 'var(--app-bg-card)', 
            borderBottomColor: 'var(--app-border-light)',
            minHeight: '48px',
            fontFamily: '"Segoe UI", system-ui, sans-serif'
        }}>
            <style>{`
                .custom-project-nav .nav-link { color: var(--app-text-primary) !important; font-size: 14px; }
                .custom-dropdown-item:hover, .custom-dropdown-item:focus { background-color: var(--app-bg-main) !important; color: var(--app-primary-accent) !important; }
                .custom-project-nav .dropdown-menu { background-color: var(--app-bg-card); border: 1px solid var(--app-border-mid); }
                .custom-project-nav .dropdown-toggle { color: var(--app-text-primary) !important; font-size: 14px; }
            `}</style>
            
            {/* Logo and Brand Name */}
            <div className="d-flex align-items-center">
                <Button variant="link" className="d-md-none p-0 me-3 text-secondary d-flex align-items-center justify-content-center" onClick={onToggleSidebar} style={{ color: 'var(--app-text-primary)' }}>
                    <FaBars size={20} />
                </Button>
                <Link to="/" className="d-flex align-items-center me-3 navbar-brand m-0" style={{ cursor: 'pointer', color: 'var(--app-text-primary)', fontWeight: 'bold', textDecoration: 'none' }} onClick={() => addLog("Project closed. Returning to home.")}>
                    <img src={Logo3psLCCA} alt="3psLCCA Logo" width="28" height="28" className="me-2" style={{ objectFit: 'contain' }} />
                    <span style={{ fontSize: '1rem' }}>3psLCCA</span>
                </Link>
            </div>
            
            <Navbar.Toggle aria-controls="project-navbar-nav" className="border-0 shadow-none" style={{ filter: 'invert(0.5)' }} />
            <Navbar.Collapse id="project-navbar-nav">
                <Nav className="me-auto align-items-center flex-row flex-wrap gap-2 gap-lg-0">
                <Link to="/" className="nav-link px-2 py-1 mx-1 rounded d-flex align-items-center justify-content-center" style={{ color: 'var(--app-text-primary)', transition: 'color 0.2s' }} onClick={() => addLog("Project closed. Returning to home.")}>
                    <FaHome size={18} />
                </Link>
                
                <CustomDropdown 
                    title="File" 
                    id="file-nav-dropdown" 
                    items={[
                        { label: 'New Project', icon: FaPlus, onClick: () => setShowNewProjectModal(true) },
                        { label: 'Open Project', icon: FaFolderOpen, onClick: onBackToHome },
                        'divider',
                        { label: 'Save Now', icon: FaSave, href: '#save' },
                        'divider',
                        { label: 'Rename', icon: FaCog, onClick: () => setShowRenameModal(true) },
                        { label: 'Export...', icon: FaSave, onClick: onExportProject },
                        'divider',
                        { label: 'Version History', icon: FaHistory, onClick: () => setShowVersionModal(true) },
                        'divider',
                        { label: 'Info', onClick: () => setShowInfoModal(true) },
                        'divider',
                        { label: 'Close Project', icon: FaSignOutAlt, onClick: onBackToHome }
                    ]}
                />

                <CustomDropdown 
                    title="Help" 
                    id="help-nav-dropdown" 
                    items={[
                        { label: 'Contact us', onClick: () => setShowContactModal(true) },
                        { label: 'Feedback', onClick: () => setShowFeedbackModal(true) }
                    ]}
                />

                <Link to={`/project/${projectId}/Logs`} className="nav-link px-2 py-1 mx-1 rounded" style={{ color: 'var(--app-text-primary)' }} onClick={() => setActiveNode('Logs')}>Logs</Link>
            </Nav>

            <Nav className="ms-auto align-items-center column-gap-2 flex-row flex-wrap mt-2 mt-lg-0">
                <div className="d-flex align-items-center me-2" style={{ 
                    color: saveState === 'error' ? 'var(--bs-danger)' : (saveState === 'saving' ? 'var(--bs-warning)' : (saveState === 'offline' ? 'var(--app-text-muted)' : 'var(--app-primary-accent)')), 
                    fontSize: '12px', 
                    opacity: 0.9 
                }}>
                    {saveState === 'saving' && <Spinner size="sm" animation="border" className="me-1" style={{ width: '12px', height: '12px', borderWidth: '0.15em' }} />}
                    {saveState === 'saved' && <FaCheckCircle size={12} className="me-1" />}
                    {saveState === 'offline' && <FaCheckCircle size={12} className="me-1" />}
                    {saveState === 'error' && <FaExclamationTriangle size={12} className="me-1" />}
                    <span>
                        {saveState === 'saving' ? 'Saving...' : (saveState === 'error' ? 'Save failed - retry' : (saveState === 'offline' ? 'Saved Locally (Offline)' : 'All changes saved'))}
                    </span>
                </div>
                

                <Button 
                    variant="outline-secondary" 
                    size="sm" 
                    className="calc-btn d-flex align-items-center"
                    style={{ 
                        fontSize: '13px', 
                        padding: '4px 12px', 
                        transition: 'all 0.2s', 
                        borderColor: 'var(--app-border-mid)', 
                        color: 'var(--app-text-secondary)', 
                        backgroundColor: 'transparent',
                        height: '32px',
                        borderRadius: '4px'
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--app-primary-accent)'; e.currentTarget.style.borderColor = 'var(--app-primary-accent)'; e.currentTarget.style.color = 'var(--app-bg-card)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.borderColor = 'var(--app-border-mid)'; e.currentTarget.style.color = 'var(--app-text-secondary)'; }}
                    onClick={() => {
                        // The calculation itself runs on the Results page; the
                        // project is locked there once it succeeds.
                        addLog("Opening Results — run the calculation from there.");
                        setActiveNode('Results');
                    }}
                >
                    <FaCalculator size={13} className="me-2" />
                    Calculate
                </Button>
 
                <OverlayTrigger
                    placement="bottom"
                    overlay={<Tooltip>{isLocked ? 'Unlock Project' : 'Lock Project'}</Tooltip>}
                >
                    <Button 
                        variant="link"
                        className="p-1 mx-1 text-secondary"
                        aria-label={isLocked ? 'Unlock project' : 'Lock project'}
                        aria-pressed={isLocked}
                        onClick={() => {
                            if (isLocked) {
                                if (window.confirm("Unlock the project to edit its inputs?\n\nNothing is deleted: your inputs stay as they are and the current results remain on the Results page, but they will be out of date until you calculate again.")) {
                                    setIsLocked(false);
                                    addLog("Project unlocked. Inputs can be edited; recalculate to refresh the results.");
                                }
                            } else {
                                setIsLocked(true);
                                addLog("Project locked. All operations suspended.");
                            }
                        }}
                        style={{ transition: 'all 0.2s' }}
                    >
                        {isLocked ? <FaLock size={18} color="var(--app-primary-accent)" /> : <FaLockOpen size={18} style={{ opacity: 0.7 }} />}
                    </Button>
                </OverlayTrigger>
            </Nav>
            </Navbar.Collapse>


            <NewProjectModal 
                show={showNewProjectModal}
                onHide={() => setShowNewProjectModal(false)}
                onCreate={onNewProject}
            />

            <OpenProjectModal 
                show={showOpenProjectModal}
                onHide={() => setShowOpenProjectModal(false)}
                onOpen={(data) => {
                    onOpenProject(data);
                    setShowOpenProjectModal(false);
                }}
            />

            <RenameProjectModal 
                show={showRenameModal}
                onHide={() => setShowRenameModal(false)}
                onRename={onRenameProject}
                currentName={projectName}
            />

            <VersionHistoryModal 
                show={showVersionModal}
                onHide={() => setShowVersionModal(false)}
            />

            <HelpModal 
                show={showContactModal}
                onHide={() => setShowContactModal(false)}
                title="Contact Us"
                message="For support or enquiries, please email: support@3pslcca.com"
            />

            <HelpModal 
                show={showFeedbackModal}
                onHide={() => setShowFeedbackModal(false)}
                title="Feedback"
                message="We'd love to hear from you! Send feedback to: feedback@3pslcca.com"
            />

            <ProjectInfoModal 
                show={showInfoModal}
                onHide={() => setShowInfoModal(false)}
                projectData={projectData}
            />
        </Navbar>
    );
};

export default ProjectNavbar;

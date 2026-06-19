/* eslint-disable no-unused-vars */
import React, { useState, useEffect, useRef } from 'react';
import { BsHouseDoorFill, BsFileEarmarkPlus, BsFolder2Open, BsGearFill, BsThreeDotsVertical, BsStarFill, BsStar } from 'react-icons/bs';
import { AiOutlineRedo } from 'react-icons/ai';
import NewProject from './NewProject';
import SettingsModal from './SettingsModal';
import { projectStorageService } from '../../lib/projectStorageService';
import { import3psFile } from '../../utils/projectImport';

// Base Imports
import Logo3psLCCA from '../../assets/logo-3psLCCA.svg';

// Custom Logos (Light Theme)
import ConstructSteelLight from '../../assets/special/ConstructSteel_light.svg';
import IITBLogoLight from '../../assets/special/IITB_logo_light.svg';
import InsdagLight from '../../assets/special/INSDAG_light.svg';
import MOSLight from '../../assets/special/MOS_light.svg';

// Custom Logos (Dark Theme)
import ConstructSteelDark from '../../assets/special/ConstructSteel_dark.svg';
import IITBLogoDark from '../../assets/special/IITB_logo_dark.svg';
import InsdagDark from '../../assets/special/INSDAG_dark.svg';
import MOSDark from '../../assets/special/MOS_dark.svg';


const AppLogo = () => (
    <img src={Logo3psLCCA} alt="3psLCCA Logo" width="45" height="45" style={{ objectFit: 'contain' }} />
);

// Project Card with hover star like desktop
const ProjectCard = ({ proj, theme, onOpen, onContextMenu, onPinToggle }) => {
    const [isHovered, setIsHovered] = useState(false);

    const handleStarClick = (e) => {
        e.stopPropagation();
        onPinToggle();
    };

    const showStar = proj.pinned || isHovered;
    const starFilled = proj.pinned;

    return (
        <div 
            className="p-3 d-flex justify-content-between align-items-start shadow-sm position-relative" 
            style={{ 
                backgroundColor: theme.bgCard, 
                border: `1px solid ${theme.border}`, 
                borderRadius: '8px', 
                cursor: 'pointer', 
                transition: 'all 0.2s', 
                minHeight: '90px',
                borderLeft: proj.pinned ? `4px solid ${theme.activeIconColor}` : undefined
            }} 
            onClick={onOpen}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
        >
            <div className="d-flex flex-column justify-content-between h-100" style={{ flex: 1 }}>
                <div className="d-flex align-items-center gap-2">
                    <h6 className="mb-0" style={{ color: theme.textPrimary, fontSize: '0.95rem', fontWeight: '500' }}>{proj.name}</h6>
                </div>
                <small style={{ color: theme.textSecondary, fontSize: '0.75rem' }}>{proj.date}</small>
            </div>
            
            {/* Star icon - shows on hover or when pinned */}
            {showStar && (
                <button
                    onClick={handleStarClick}
                    className="btn btn-link p-0 border-0"
                    style={{ 
                        marginTop: 'auto', 
                        marginBottom: 'auto',
                        marginRight: '8px',
                        opacity: starFilled ? 1 : 0.6
                    }}
                    title={starFilled ? 'Unpin' : 'Pin to top'}
                >
                    {starFilled ? (
                        <BsStarFill size={16} color={theme.activeIconColor} />
                    ) : (
                        <BsStar size={16} color={theme.textSecondary} />
                    )}
                </button>
            )}
            
            {/* Three dots menu */}
            <button 
                className="btn btn-link text-muted p-0 border-0" 
                style={{ marginTop: 'auto', marginBottom: 'auto' }}
                onClick={onContextMenu}
            >
                <BsThreeDotsVertical size={16} color={theme.textSecondary} />
            </button>
        </div>
    );
};


const Homepage = ({ onProjectOpen, onProjectCreate, userName = 'ritik!', isDarkMode, userSettings, setUserSettings, onLogout }) => {
    const [showModal, setShowModal] = useState(false);
    const [showSettingsModal, setShowSettingsModal] = useState(false);
    const [activeTab, setActiveTab] = useState('home');
    const [searchTerm, setSearchTerm] = useState('');
    const [filter, setFilter] = useState('recent'); // 'recent', 'name', 'pinned'
    const [projects, setProjects] = useState([]);
    const isGuest = sessionStorage.getItem('isGuest') === 'true';
    const pinStorageKey = isGuest ? 'pinned_projects_guest' : `pinned_projects_${userName}`;

    const [pinnedIds, setPinnedIds] = useState(() => {
        return JSON.parse(localStorage.getItem(pinStorageKey) || '[]');
    });
    const fileInputRef = useRef(null);
    // Context menu state
    const [contextMenu, setContextMenu] = useState({ show: false, x: 0, y: 0, project: null });
    const [importStatus, setImportStatus] = useState('idle'); // 'idle' | 'loading' | 'success' | 'error'
    const [importMessage, setImportMessage] = useState('');

    const fetchProjects = async () => {
        const list = await projectStorageService.listProjects();
        setProjects(list);
    };

    useEffect(() => {
        fetchProjects();
    }, []);

    const handleOpenModal = () => setShowModal(true);
    const handleCloseModal = () => setShowModal(false);

    const handleNewProject = () => {
        setActiveTab('new');
        handleOpenModal();
    };

    const handleProjectCreate = (newProjectData) => {
        const result = onProjectCreate ? onProjectCreate(newProjectData) : null;
        const newProject = {
            id: result?.id ?? Date.now(),
            name: newProjectData.name,
            date: 'just now'
        };
        setProjects(prev => [...prev, newProject]);
        setActiveTab('home');
    };

    // Filter and sort projects based on search term and active filter
    const filteredProjects = projects
        .filter(proj => {
            const matchesSearch = proj.name.toLowerCase().includes(searchTerm.toLowerCase());
            const isPinned = pinnedIds.includes(proj.id);
            if (filter === 'pinned' && !isPinned) return false;
            return matchesSearch;
        })
        .sort((a, b) => {
            if (filter === 'name') {
                return a.name.localeCompare(b.name);
            }
            // 'recent' - keep original order (most recent first)
            // 'pinned' - show pinned first then by recent
            if (filter === 'pinned') {
                const isPinnedA = pinnedIds.includes(a.id);
                const isPinnedB = pinnedIds.includes(b.id);
                if (isPinnedA && !isPinnedB) return -1;
                if (!isPinnedA && isPinnedB) return 1;
            }
            return 0;
        });

    // Handle file upload for .3ps project files
    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        // Reset file input value to allow uploading the same file again
        event.target.value = '';

        // 1. Validate file extension
        if (!file.name.endsWith('.3ps')) {
            setImportMessage('Invalid file type. Please select a valid .3ps file.');
            setImportStatus('error');
            return;
        }

        setImportStatus('loading');
        setImportMessage('');

        try {
            // Extract and parse ZIP content 100% client-side
            const arrayBuffer = await file.arrayBuffer();
            const importedProjectData = await import3psFile(arrayBuffer);

            const projectId = importedProjectData.id || `proj_${Date.now()}`;
            const projectName = importedProjectData.name || importedProjectData.general_info?.project_name || file.name.replace(/\.3ps$/, '');

            importedProjectData.id = projectId;
            importedProjectData.name = projectName;

            // 2. Persist using projectStorageService (offline-first, localStorage + Appwrite sync)
            try {
                await projectStorageService.saveProject(projectId, importedProjectData);
            } catch (err) {
                if (err.message !== 'offline') throw err;
            }

            // 3. Update local projects list
            const newProjectItem = {
                id: projectId,
                name: projectName,
                date: new Date().toLocaleDateString()
            };

            setProjects(prev => {
                const filtered = prev.filter(p => p.id !== projectId);
                return [newProjectItem, ...filtered];
            });

            setImportMessage(`Project "${projectName}" imported and loaded successfully.`);
            setImportStatus('success');

            // 4. Automatically open project after a short delay
            setTimeout(() => {
                onProjectOpen(projectId, projectName);
            }, 1000);

        } catch (err) {
            console.error("Import processing failed:", err);
            setImportMessage(err.message || 'An error occurred while importing the .3ps file.');
            setImportStatus('error');
        }
    };

    const triggerFileUpload = () => {
        fileInputRef.current?.click();
    };

    // Context menu handlers
    const handleContextMenu = (e, proj) => {
        e.stopPropagation();
        e.preventDefault();
        
        // Menu dimensions (must match CSS below)
        const menuWidth = 160;
        const menuHeight = 280; // Approximate max height
        
        let x = e.clientX;
        let y = e.clientY;
        
        // Keep within viewport bounds
        if (x + menuWidth > window.innerWidth) {
            x = window.innerWidth - menuWidth - 8;
        }
        if (y + menuHeight > window.innerHeight) {
            y = window.innerHeight - menuHeight - 8;
        }
        
        setContextMenu({
            show: true,
            x,
            y,
            project: proj
        });
    };

    const closeContextMenu = () => {
        setContextMenu({ show: false, x: 0, y: 0, project: null });
    };

    const handlePinToggle = (proj) => {
        setPinnedIds(prev => {
            const newPins = prev.includes(proj.id) 
                ? prev.filter(id => id !== proj.id)
                : [...prev, proj.id];
            localStorage.setItem(pinStorageKey, JSON.stringify(newPins));
            return newPins;
        });
        closeContextMenu();
    };

    const handleCopyName = (name) => {
        navigator.clipboard.writeText(name);
        closeContextMenu();
    };

    const handleDeleteProject = async (proj) => {
        if (window.confirm(`Delete '${proj.name}'?\nThis cannot be undone.`)) {
            await projectStorageService.deleteProject(proj.id);
            setProjects(prev => prev.filter(p => p.id !== proj.id));
        }
        closeContextMenu();
    };

    const handleRenameProject = async (proj) => {
        const newName = window.prompt('New name:', proj.name);
        if (newName && newName.trim()) {
            setProjects(prev => prev.map(p => 
                p.id === proj.id ? { ...p, name: newName.trim() } : p
            ));
            const fullProj = await projectStorageService.loadProject(proj.id);
            if (fullProj) {
                fullProj.name = newName.trim();
                await projectStorageService.saveProject(proj.id, fullProj);
            }
        }
        closeContextMenu();
    };

    const handleDuplicateProject = async (proj) => {
        const fullProj = await projectStorageService.loadProject(proj.id);
        if (fullProj) {
            const newId = 'proj_' + Date.now();
            fullProj.name = `${proj.name} (Copy)`;
            await projectStorageService.saveProject(newId, fullProj);
            await fetchProjects();
        }
        closeContextMenu();
    };

    const getGreetingTime = () => {
        const hour = new Date().getHours();
        if (hour < 12) return 'Morning';
        if (hour < 17) return 'Afternoon';
        return 'Evening';
    };

    let theme = isDarkMode ? {
        logoIITB: IITBLogoDark,
        logoConstructSteel: ConstructSteelDark,
        logoMOS: MOSDark,
        logoINSDAG: InsdagDark,
        inputBg: 'var(--app-bg-main)',
        filterBtnUnselectedBg: 'var(--app-bg-main)'
    } : {
        logoIITB: IITBLogoLight,
        logoConstructSteel: ConstructSteelLight,
        logoMOS: MOSLight,
        logoINSDAG: InsdagLight,
        inputBg: 'var(--app-bg-card)',
        filterBtnUnselectedBg: 'var(--app-bg-card)'
    };

    theme.bgMain = 'var(--app-bg-main)';
    theme.bgSidebar = 'var(--app-bg-card)';
    theme.bgCard = 'var(--app-bg-card)';
    theme.border = 'var(--app-border-mid)';
    theme.textPrimary = 'var(--app-text-primary)';
    theme.textSecondary = 'var(--app-text-secondary)';
    theme.activeIconColor = 'var(--app-primary-accent)';
    theme.activeIconBg = 'var(--app-surface-pressed)';

    return (
        <div className="d-flex vh-100" style={{ backgroundColor: theme.bgMain, color: theme.textPrimary, fontFamily: 'Inter, sans-serif', transition: 'background-color 0.3s ease' }}>

            {/* Left Sidebar */}
            <div className="d-flex flex-column align-items-center" style={{ width: '85px', backgroundColor: theme.bgSidebar, borderRight: `1px solid ${theme.border}`, zIndex: 10, transition: 'background-color 0.3s ease' }}>
                {/* Home Icon */}
                <div
                    className="d-flex flex-column align-items-center justify-content-center w-100 py-3"
                    style={{ cursor: 'pointer', backgroundColor: activeTab === 'home' ? theme.activeIconBg : 'transparent', color: activeTab === 'home' ? theme.activeIconColor : theme.textSecondary, transition: 'all 0.2s' }}
                    onClick={() => setActiveTab('home')}
                >
                    <BsHouseDoorFill size={22} className="mb-1" />
                    <span style={{ fontSize: '11px', fontWeight: activeTab === 'home' ? '600' : 'normal' }}>Home</span>
                </div>

                {/* New Project Icon */}
                <div
                    className="d-flex flex-column align-items-center justify-content-center w-100 py-3"
                    style={{ cursor: 'pointer', backgroundColor: activeTab === 'new' ? theme.activeIconBg : 'transparent', color: activeTab === 'new' ? theme.activeIconColor : theme.textSecondary, transition: 'all 0.2s' }}
                    onClick={handleNewProject}
                >
                    <BsFileEarmarkPlus size={22} className="mb-1" />
                    <span style={{ fontSize: '11px', fontWeight: activeTab === 'new' ? '600' : 'normal' }}>New</span>
                </div>

                {/* Open Project Icon */}
                <div
                    className="d-flex flex-column align-items-center justify-content-center w-100 py-3"
                    style={{ cursor: 'pointer', backgroundColor: activeTab === 'open' ? theme.activeIconBg : 'transparent', color: activeTab === 'open' ? theme.activeIconColor : theme.textSecondary, transition: 'all 0.2s' }}
                    onClick={() => {
                        setActiveTab('open');
                        triggerFileUpload();
                    }}
                >
                    <BsFolder2Open size={22} className="mb-1" />
                    <span style={{ fontSize: '11px', fontWeight: activeTab === 'open' ? '600' : 'normal' }}>Open</span>
                </div>

                <div className="mt-auto w-100 d-flex flex-column align-items-center pb-2">
                    {/* Settings Icon (Bottom) */}
                    <div
                        className="d-flex flex-column align-items-center justify-content-center w-100 py-4"
                        style={{ cursor: 'pointer', backgroundColor: activeTab === 'settings' ? theme.activeIconBg : 'transparent', color: activeTab === 'settings' ? theme.activeIconColor : theme.textSecondary, transition: 'all 0.2s', borderTop: `1px solid ${theme.border}` }}
                        onClick={() => { setActiveTab('settings'); setShowSettingsModal(true); }}
                    >
                        <BsGearFill size={20} className="mb-1" />
                        <span style={{ fontSize: '11px' }}>Settings</span>
                    </div>
                </div>
            </div>

            {/* Main Area */}
            <div className="flex-grow-1 d-flex flex-column overflow-hidden">

                {/* Header */}
                <header className="d-flex justify-content-between align-items-center px-5 py-3" style={{ borderBottom: `1px solid ${theme.border}`, backgroundColor: theme.bgMain, transition: 'background-color 0.3s ease' }}>
                    <h4 className="m-0" style={{ color: theme.textSecondary, fontWeight: '400', fontSize: '1.4rem' }}>
                        Good {getGreetingTime()}, <span style={{ color: theme.activeIconColor, fontWeight: '700' }}>{userName}</span>
                    </h4>
                    <AppLogo />
                </header>

                {/* Content */}
                <main className="flex-grow-1 px-5 py-4 d-flex flex-column overflow-y-auto">

                    {/* Projects Header & Filters */}
                    <div className="d-flex justify-content-between align-items-center mb-4 pb-2" style={{ borderBottom: `1px solid ${theme.border}` }}>
                        <div className="d-flex align-items-center gap-3">
                            <h6 className="m-0 fw-bold text-uppercase" style={{ fontSize: '0.85rem', color: theme.textSecondary, letterSpacing: '1px' }}>
                                RECENT PROJECTS
                            </h6>
                            <button className="btn btn-sm rounded-circle d-flex align-items-center justify-content-center" style={{ width: '28px', height: '28px', border: `1px solid ${theme.border}`, backgroundColor: theme.inputBg, color: theme.textSecondary }}>
                                <AiOutlineRedo size={14} />
                            </button>
                        </div>

                        <div className="d-flex align-items-center gap-2" style={{ marginTop: '-4px' }}>
                            <input
                                type="text"
                                placeholder="Search projects..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="form-control form-control-sm me-2 shadow-sm"
                                style={{
                                    backgroundColor: theme.inputBg,
                                    border: `1px solid ${theme.border}`,
                                    color: theme.textPrimary,
                                    width: '280px',
                                    borderRadius: '6px',
                                    padding: '0.4rem 0.8rem'
                                }}
                            />
                            <button 
                                className="btn btn-sm px-4 shadow-sm" 
                                onClick={() => setFilter('recent')}
                                style={{ 
                                    backgroundColor: filter === 'recent' ? theme.inputBg : theme.filterBtnUnselectedBg, 
                                    color: filter === 'recent' ? theme.activeIconColor : theme.textSecondary, 
                                    border: `1px solid ${filter === 'recent' ? theme.activeIconColor : theme.border}`, 
                                    borderRadius: '6px', 
                                    fontWeight: filter === 'recent' ? '600' : 'normal',
                                    padding: '0.4rem' 
                                }}
                            >
                                Recent
                            </button>
                            <button 
                                className="btn btn-sm px-4 shadow-sm" 
                                onClick={() => setFilter('name')}
                                style={{ 
                                    backgroundColor: filter === 'name' ? theme.inputBg : theme.filterBtnUnselectedBg, 
                                    color: filter === 'name' ? theme.activeIconColor : theme.textSecondary, 
                                    border: `1px solid ${filter === 'name' ? theme.activeIconColor : theme.border}`, 
                                    borderRadius: '6px', 
                                    fontWeight: filter === 'name' ? '600' : 'normal',
                                    padding: '0.4rem' 
                                }}
                            >
                                All
                            </button>
                            <button 
                                className="btn btn-sm px-4 shadow-sm" 
                                onClick={() => setFilter('pinned')}
                                style={{ 
                                    backgroundColor: filter === 'pinned' ? theme.inputBg : theme.filterBtnUnselectedBg, 
                                    color: filter === 'pinned' ? theme.activeIconColor : theme.textSecondary, 
                                    border: `1px solid ${filter === 'pinned' ? theme.activeIconColor : theme.border}`, 
                                    borderRadius: '6px', 
                                    fontWeight: filter === 'pinned' ? '600' : 'normal',
                                    padding: '0.4rem' 
                                }}
                            >
                                Starred
                            </button>
                        </div>
                    </div>

                    {/* Projects List */}
                    <div className="row g-3">
                        {filteredProjects.map((proj) => (
                            <div key={proj.id} className="col-12 col-md-6 col-lg-6">
                                <ProjectCard 
                                    proj={{...proj, pinned: pinnedIds.includes(proj.id)}} 
                                    theme={theme} 
                                    onOpen={() => onProjectOpen(proj.id, proj.name)}
                                    onContextMenu={(e) => handleContextMenu(e, proj)}
                                    onPinToggle={() => handlePinToggle(proj)}
                                />
                            </div>
                        ))}
                    </div>

                    {/* Context Menu */}
                    {contextMenu.show && contextMenu.project && (
                        <>
                            <div 
                                className="position-fixed" 
                                style={{ 
                                    top: 0, 
                                    left: 0, 
                                    right: 0, 
                                    bottom: 0, 
                                    zIndex: 1049 
                                }}
                                onClick={closeContextMenu}
                            />
                            <div 
                                className="position-fixed shadow-lg"
                                style={{
                                    top: contextMenu.y,
                                    left: contextMenu.x,
                                    backgroundColor: theme.bgCard,
                                    border: `1px solid ${theme.border}`,
                                    borderRadius: '6px',
                                    zIndex: 1050,
                                    width: '160px',
                                    fontSize: '13px'
                                }}
                            >
                                <div>
                                    <button 
                                        className="dropdown-item d-flex align-items-center px-3 py-1"
                                        style={{ background: 'transparent', border: 'none', color: theme.textPrimary, cursor: 'pointer', width: '100%', textAlign: 'left', fontSize: '13px' }}
                                        onClick={() => { onProjectOpen(contextMenu.project.id, contextMenu.project.name); closeContextMenu(); }}
                                    >
                                        Open
                                    </button>
                                    <div style={{ borderTop: `1px solid ${theme.border}`, margin: '2px 0' }} />
                                    <button 
                                        className="dropdown-item d-flex align-items-center px-3 py-1"
                                        style={{ background: 'transparent', border: 'none', color: theme.textPrimary, cursor: 'pointer', width: '100%', textAlign: 'left', fontSize: '13px' }}
                                        onClick={() => handlePinToggle(contextMenu.project)}
                                    >
                                        {contextMenu.project.pinned ? 'Unpin' : '📌 Pin to top'}
                                    </button>
                                    <div style={{ borderTop: `1px solid ${theme.border}`, margin: '2px 0' }} />
                                    <button 
                                        className="dropdown-item d-flex align-items-center px-3 py-1"
                                        style={{ background: 'transparent', border: 'none', color: theme.textPrimary, cursor: 'pointer', width: '100%', textAlign: 'left', fontSize: '13px' }}
                                        onClick={() => handleCopyName(contextMenu.project.name)}
                                    >
                                        Copy Name
                                    </button>
                                    <button 
                                        className="dropdown-item d-flex align-items-center px-3 py-1"
                                        style={{ background: 'transparent', border: 'none', color: theme.textSecondary, cursor: 'not-allowed', width: '100%', textAlign: 'left', fontSize: '13px' }}
                                        disabled
                                    >
                                        Share / Export...
                                    </button>
                                    <button 
                                        className="dropdown-item d-flex align-items-center px-3 py-1"
                                        style={{ background: 'transparent', border: 'none', color: theme.textPrimary, cursor: 'pointer', width: '100%', textAlign: 'left', fontSize: '13px' }}
                                        onClick={() => handleRenameProject(contextMenu.project)}
                                    >
                                        Rename
                                    </button>
                                    <button 
                                        className="dropdown-item d-flex align-items-center px-3 py-1"
                                        style={{ background: 'transparent', border: 'none', color: theme.textPrimary, cursor: 'pointer', width: '100%', textAlign: 'left', fontSize: '13px' }}
                                        onClick={() => handleDuplicateProject(contextMenu.project)}
                                    >
                                        Duplicate
                                    </button>
                                    <button 
                                        className="dropdown-item d-flex align-items-center px-3 py-1"
                                        style={{ background: 'transparent', border: 'none', color: theme.textSecondary, cursor: 'not-allowed', width: '100%', textAlign: 'left', fontSize: '13px' }}
                                        disabled
                                    >
                                        Info
                                    </button>
                                    <div style={{ borderTop: `1px solid ${theme.border}`, margin: '2px 0' }} />
                                    <button 
                                        className="dropdown-item d-flex align-items-center px-3 py-1"
                                        style={{ background: 'transparent', border: 'none', color: '#dc3545', cursor: 'pointer', width: '100%', textAlign: 'left', fontSize: '13px' }}
                                        onClick={() => handleDeleteProject(contextMenu.project)}
                                    >
                                        Delete
                                    </button>
                                </div>
                            </div>
                        </>
                    )}

                    {/* Hidden file input for .3ps project upload */}
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileUpload}
                        accept=".3ps"
                        style={{ display: 'none' }}
                    />

                </main>

                {/* Footer */}
                <footer className="px-5 py-2" style={{ borderTop: `1px solid ${theme.border}`, backgroundColor: theme.bgMain, transition: 'background-color 0.3s ease' }}>
                    <div className="d-flex justify-content-between align-items-start mt-1">
                        <div className="d-flex flex-column align-items-start ps-2">
                            <span className="mb-2" style={{ fontSize: '0.65rem', color: theme.textSecondary, fontWeight: 'bold', letterSpacing: '1px' }}>DEVELOPED AT</span>
                            <img src={theme.logoIITB} alt="IIT Bombay Logo" height="50" style={{ opacity: isDarkMode ? 0.9 : 1 }} />
                        </div>
                        <div className="d-flex flex-column align-items-end pe-2">
                            <span className="mb-2" style={{ fontSize: '0.65rem', color: theme.textSecondary, fontWeight: 'bold', letterSpacing: '1px' }}>SUPPORTED BY</span>
                            <div className="d-flex align-items-center gap-4 mt-1">
                                <img src={theme.logoConstructSteel} alt="constructsteel Logo" height="22" />
                                <img src={theme.logoMOS} alt="Ministry of Steel Logo" height="30" />
                                <img src={theme.logoINSDAG} alt="INSDAG Logo" height="30" />
                            </div>
                            <div className="mt-2">
                                <span style={{ fontSize: '0.7rem', color: theme.textSecondary }}>3psLCCA v2026.04.1</span>
                            </div>
                        </div>
                    </div>
                </footer>
            </div>

            {/* New Project Modal */}
            <NewProject show={showModal} handleClose={handleCloseModal} onProjectOpen={onProjectOpen} onProjectCreate={handleProjectCreate} isDarkMode={isDarkMode} theme={theme} />

            {/* Settings Modal */}
            <SettingsModal
                show={showSettingsModal}
                handleClose={() => setShowSettingsModal(false)}
                isDarkMode={isDarkMode}
                theme={theme}
                onLogout={onLogout}
                initialUserName={userName}
                userSettings={userSettings}
                onSaveSettings={(settings) => {
                    setUserSettings({
                        appearanceMode: settings.appearanceMode,
                        lightTheme: settings.lightTheme,
                        darkTheme: settings.darkTheme
                    });
                }}
            />
            {/* Import Status Overlays / Toasts */}
            {importStatus === 'loading' && (
                <div className="position-fixed top-0 start-0 w-100 h-100 d-flex flex-column align-items-center justify-content-center" style={{ backgroundColor: 'rgba(0, 0, 0, 0.75)', zIndex: 9999, transition: 'all 0.3s ease' }}>
                    <div className="spinner-border text-primary mb-3" role="status" style={{ width: '3rem', height: '3rem' }}>
                        <span className="visually-hidden">Loading...</span>
                    </div>
                    <h5 className="text-white fw-bold">Importing project...</h5>
                    <p className="text-light">Extracting chunks, validating headers, and building project structure.</p>
                </div>
            )}

            {importStatus === 'error' && (
                <div className="position-fixed bottom-0 end-0 m-4 p-3 shadow-lg border-0 alert alert-danger alert-dismissible fade show" role="alert" style={{ zIndex: 9999, maxWidth: '400px', borderRadius: '10px' }}>
                    <h6 className="alert-heading fw-bold d-flex align-items-center gap-2 mb-1">
                        ❌ Import Failed
                    </h6>
                    <p className="mb-0 small">{importMessage}</p>
                    <button type="button" className="btn-close" onClick={() => setImportStatus('idle')}></button>
                </div>
            )}

            {importStatus === 'success' && (
                <div className="position-fixed bottom-0 end-0 m-4 p-3 shadow-lg border-0 alert alert-success alert-dismissible fade show" role="alert" style={{ zIndex: 9999, maxWidth: '400px', borderRadius: '10px' }}>
                    <h6 className="alert-heading fw-bold d-flex align-items-center gap-2 mb-1">
                        ✅ Success
                    </h6>
                    <p className="mb-0 small">{importMessage}</p>
                    <button type="button" className="btn-close" onClick={() => setImportStatus('idle')}></button>
                </div>
            )}
        </div>
    );
};

export default Homepage;
import { useRef, useState, useEffect } from 'react';
import { FaFileExport, FaFileImport, FaTrash } from 'react-icons/fa';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import {
    applyConstructionImport,
    downloadConstructionWorkbook,
    getActiveConstructionCount,
    getConstructionTrash,
    parseConstructionWorkbook,
} from '../../../utils/constructionExcel';
import './ConstructionWorkData.css';
import Foundation from './foundation/Foundation';
import SubStructure from './substructure/SubStructure';
import SuperStructure from './superstructure/SuperStructure';
import Miscellaneous from './miscellaneous/Miscellaneous';
import ImportPreviewModal from './ImportPreviewModal';
import ConstructionTrash from './ConstructionTrash';

const TABS = [
    { key: 'Foundation', label: 'Foundation', component: Foundation },
    { key: 'SuperStructure', label: 'Super Structure', component: SuperStructure },
    { key: 'SubStructure', label: 'Sub Structure', component: SubStructure },
    { key: 'Miscellaneous', label: 'Miscellaneous', component: Miscellaneous },
];

const ConstructionWorkData = ({ controller, projectData, data, onUpdate, projectName = 'Active Analysis', initialTab = 'Foundation', setActiveNode }) => {
    const projectContext = useProjectData();
    const currentProject = projectContext.projectData || projectData;
    const { updateProjectData } = projectContext;
    const [activeTab, setActiveTab] = useState(initialTab);
    const [preview, setPreview] = useState(null);
    const [busy, setBusy] = useState('');
    const fileInputRef = useRef(null);

    useEffect(() => {
        // Sidebar navigation can switch the visible construction tab while mounted.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setActiveTab(initialTab);
    }, [initialTab]);

    const ActiveComponent = TABS.find((t) => t.key === activeTab)?.component || Foundation;
    const trashCount = getConstructionTrash(currentProject).length;

    const saveConstructionSections = (sections) => {
        Object.entries(sections).forEach(([key, value]) => updateProjectData(key, value));
    };

    const handleImportFile = async (event) => {
        const file = event.target.files?.[0];
        event.target.value = '';
        if (!file) return;
        setBusy('import');
        try {
            const parsed = await parseConstructionWorkbook(await file.arrayBuffer(), currentProject);
            setPreview(parsed);
        } catch (error) {
            window.alert(`Could not import this workbook.\n\n${error.message}`);
        } finally {
            setBusy('');
        }
    };

    const handleImport = (reviewedPreview) => {
        saveConstructionSections(applyConstructionImport(currentProject, reviewedPreview));
        const count = reviewedPreview.sheets.flatMap((sheet) => sheet.rows).filter((row) => row.selected && row.errors.length === 0).length;
        setPreview(null);
        window.alert(`${count} row(s) imported.`);
        controller?.engine?._log(`Construction: imported ${count} Excel row(s).`);
    };

    const handleExport = async () => {
        if (getActiveConstructionCount(currentProject) === 0) {
            window.alert('No active materials found.\nAdd materials first, or restore items from Trash.');
            return;
        }
        setBusy('export');
        try {
            const fileName = await downloadConstructionWorkbook(currentProject);
            controller?.engine?._log(`Construction: exported ${fileName}.`);
        } catch (error) {
            window.alert(`Could not export the workbook.\n\n${error.message}`);
        } finally {
            setBusy('');
        }
    };

    const updateTrashRow = (target, updater) => {
        const sections = (currentProject[target.sectionKey] || []).map((section) => {
            if (section.id !== target.sectionId) return section;
            return updater(section);
        });
        updateProjectData(target.sectionKey, sections);
    };

    const handleRestore = (target) => {
        const section = (currentProject[target.sectionKey] || []).find((item) => item.id === target.sectionId);
        const conflict = section?.rows?.some((row) => (
            row.id !== target.id
            && !row?.state?.in_trash
            && String(row.workName || '').trim().toLowerCase() === String(target.workName || '').trim().toLowerCase()
        ));
        if (conflict) {
            window.alert(`A material named "${target.workName}" already exists in "${target.component}".\n\nRemove or rename the existing material before restoring this one.`);
            return;
        }
        updateTrashRow(target, (item) => ({
            ...item,
            is_deleted: false,
            rows: item.rows.map((row) => row.id === target.id ? { ...row, state: { ...(row.state || {}), in_trash: false } } : row),
        }));
    };

    const handlePermanentDelete = (target) => {
        if (!window.confirm('Remove this item? This cannot be undone.')) return;
        updateTrashRow(target, (item) => ({ ...item, rows: item.rows.filter((row) => row.id !== target.id) }));
    };

    const handleDeleteAll = () => {
        if (!window.confirm('Permanently delete all items in trash? This cannot be undone.')) return;
        ['foundation_data', 'substructure_data', 'superstructure_data', 'miscellaneous_data'].forEach((key) => {
            updateProjectData(key, (currentProject[key] || []).map((section) => ({
                ...section,
                rows: (section.rows || []).filter((row) => !row?.state?.in_trash),
            })));
        });
    };

    if (!currentProject) {
        return <div className="p-4 text-danger">Error: Project data missing. Please reload the application.</div>;
    }

    return (
        <div className="d-flex flex-column h-100 overflow-hidden" style={{ backgroundColor: 'var(--app-bg-main)', color: 'var(--app-text-primary)' }}>
            {/* Header */}
            <div className="d-flex flex-wrap align-items-start justify-content-between border-bottom gap-2" style={{ padding: '14px 20px 10px', backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-light) !important', flexShrink: 0 }}>
                <div>
                    <h5 className="m-0 fw-bold" style={{ fontSize: '0.95rem', color: 'var(--app-text-primary)' }}>Structure Management</h5>
                    <div className="text-muted mt-1" style={{ fontSize: '0.78rem' }}>
                        Project: <span className="fw-bold" style={{ color: 'var(--app-primary-accent)' }}>{projectName}</span>
                    </div>
                </div>
                <div className="d-flex align-items-center gap-2">
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept=".xlsx"
                        className="d-none"
                        onChange={handleImportFile}
                    />
                    <button
                        className="btn btn-sm"
                        style={{ backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-secondary)', border: '1px solid var(--app-border-mid)' }}
                        onClick={() => fileInputRef.current?.click()}
                        disabled={Boolean(busy)}
                        onMouseEnter={(e) => { e.target.style.backgroundColor = 'var(--app-border-light)'; e.target.style.color = 'var(--app-text-primary)'; }}
                        onMouseLeave={(e) => { e.target.style.backgroundColor = 'var(--app-bg-alt)'; e.target.style.color = 'var(--app-text-secondary)'; }}
                    >
                        <FaFileImport className="me-1" /> {busy === 'import' ? 'Parsing...' : 'Import Excel'}
                    </button>
                    <button
                        className="btn btn-sm"
                        style={{ backgroundColor: 'var(--app-bg-alt)', color: 'var(--app-text-secondary)', border: '1px solid var(--app-border-mid)' }}
                        onClick={handleExport}
                        disabled={Boolean(busy)}
                    >
                        <FaFileExport className="me-1" /> {busy === 'export' ? 'Exporting...' : 'Export Excel'}
                    </button>
                    <button
                        className="btn btn-sm"
                        style={{
                            backgroundColor: activeTab === 'Trash' ? 'var(--app-primary-accent)' : 'var(--app-bg-alt)',
                            color: activeTab === 'Trash' ? 'white' : 'var(--app-text-secondary)',
                            border: '1px solid var(--app-border-mid)',
                        }}
                        onClick={() => setActiveTab((tab) => tab === 'Trash' ? 'Foundation' : 'Trash')}
                        onMouseEnter={(e) => { e.target.style.backgroundColor = 'var(--app-border-light)'; e.target.style.color = 'var(--app-text-primary)'; }}
                        onMouseLeave={(e) => { e.target.style.backgroundColor = 'var(--app-bg-alt)'; e.target.style.color = 'var(--app-text-secondary)'; }}
                    >
                        <FaTrash className="me-1" /> Trash{trashCount ? ` (${trashCount})` : ''}
                    </button>
                </div>
            </div>

            {/* Tab bar */}
            <div className={`d-flex border-bottom px-3 ${activeTab === 'Trash' ? 'd-none' : ''}`} style={{ backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-light) !important', flexShrink: 0 }}>
                {TABS.map((tab) => {
                    const isActive = activeTab === tab.key;
                    return (
                        <button
                            key={tab.key}
                            className={`btn rounded-0 px-3 py-2 border-0 fw-medium ${isActive ? 'fw-bold' : ''}`}
                            style={{
                                color: isActive ? 'var(--app-primary-accent)' : 'var(--app-text-secondary)',
                                borderBottom: isActive ? '2px solid var(--app-primary-accent)' : '2px solid transparent',
                                fontSize: '0.82rem',
                                transition: 'all 0.2s',
                                marginBottom: '-1px'
                            }}
                            onClick={() => {
                                setActiveTab(tab.key);
                                if (setActiveNode) setActiveNode(tab.label); // Link sidebar to tab selection
                            }}
                        >
                            {tab.label}
                        </button>
                    );
                })}
            </div>

            {/* Active tab content */}
            <div className="flex-grow-1 p-4" style={{ backgroundColor: 'var(--app-bg-main)', overflowY: 'auto' }}>
                {activeTab === 'Trash' ? (
                    <ConstructionTrash
                        projectData={currentProject}
                        onRestore={handleRestore}
                        onDelete={handlePermanentDelete}
                        onDeleteAll={handleDeleteAll}
                    />
                ) : (
                    <ActiveComponent
                        controller={controller}
                        projectData={currentProject}
                        data={data}
                        onUpdate={onUpdate}
                    />
                )}
            </div>
            {preview && (
                <ImportPreviewModal
                    initialPreview={preview}
                    onClose={() => setPreview(null)}
                    onImport={handleImport}
                />
            )}
        </div>
    );
};

export default ConstructionWorkData;

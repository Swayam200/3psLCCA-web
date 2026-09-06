import { useState, useCallback, useEffect } from 'react';
import { useProjectData } from '../../../../contexts/ProjectDataContext';
import { normalizeConstructionSections } from '../../../../utils/projectPageSchema';
import '../ConstructionWorkData.css';
import MaterialTable from '../MaterialTable';
import AddComponentModal from '../AddComponentModal';

// Row ids must be unique across every component, page and session: they are
// referenced by the transport deliveries and the report. A per-page counter
// restarted at "row-1" on every mount and collided across components.
const uid = () => `row-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
// calcTotal removed as it's in MaterialTable.jsx

const DEFAULT_SECTIONS = [
    { id: 'abutment',  name: 'Abutment',  rows: [] },
    { id: 'pier',      name: 'Pier',      rows: [] },
    { id: 'pier-cap',  name: 'Pier Cap',  rows: [] },
    { id: 'pedestal',  name: 'Pedestal',  rows: [] },
    { id: 'bearing',   name: 'Bearing',   rows: [] },
];

const defaultSections = () => normalizeConstructionSections(DEFAULT_SECTIONS, 'substructure');

// MaterialTable imported from shared component

const SubStructure = () => {
    const { projectData, updateProjectData } = useProjectData();
    const [sections, setSections] = useState(() => {
        const saved = projectData.substructure_data;
        return (saved && saved.length > 0) ? normalizeConstructionSections(saved, 'substructure') : defaultSections();
    });
    const [showAddModal, setShowAddModal] = useState(false);

    useEffect(() => {
        const next = projectData.substructure_data?.length
            ? normalizeConstructionSections(projectData.substructure_data, 'substructure')
            : defaultSections();
        // Project imports replace context data while this tab remains mounted.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSections(prev => JSON.stringify(next) !== JSON.stringify(prev) ? next : prev);
    }, [projectData.substructure_data]);

    useEffect(() => {
        updateProjectData('substructure_data', sections);
    }, [sections, updateProjectData]);
    const handleRowChange = useCallback((sId, rId, field, val) => setSections((prev) => prev.map((s) => s.id !== sId ? s : { ...s, rows: s.rows.map((r) => r.id !== rId ? r : { ...r, [field]: val }) })), []);
    const handleRowDelete = useCallback((sId, rId) => {
        if (!window.confirm('Move this item to trash?')) return;
        setSections((prev) => prev.map((s) => s.id !== sId ? s : { ...s, rows: s.rows.map((r) => r.id !== rId ? r : { ...r, state: { ...(r.state || {}), in_trash: true } }) }));
    }, []);
    const handleRowUpdate = useCallback((sId, rId, updatedRowData) => setSections((prev) => prev.map((s) => s.id !== sId ? s : { ...s, rows: s.rows.map((r) => r.id !== rId ? r : { ...r, ...updatedRowData }) })), []);
    const handleDeleteSection = useCallback((sId) => {
        setSections((prev) => prev.map((s) => {
            if (s.id !== sId) return s;
            const activeCount = s.rows.filter((row) => !row?.state?.in_trash).length;
            const message = activeCount ? `Move all ${activeCount} item(s) in "${s.name}" to trash?` : `Delete component "${s.name}"?\n\nIt will be hidden but can be recovered by restoring its materials from the trash.`;
            if (!window.confirm(message)) return s;
            return activeCount ? { ...s, rows: s.rows.map((row) => ({ ...row, state: { ...(row.state || {}), in_trash: true } })) } : { ...s, is_deleted: true };
        }));
    }, []);
    const handleAddRow = useCallback((sId, newRowData) => setSections((prev) => prev.map((s) => s.id !== sId ? s : { ...s, rows: [...s.rows, { id: uid(), ...newRowData }] })), []);
    const handleAddSection = (name) => {
        setSections((prev) => {
            const next = [
                ...prev,
                { id: uid(), name: name.trim(), rows: [] },
            ];
            return next;
        });
    };

    return (
        <div>
            {sections.filter((sec) => !sec.is_deleted).map((sec) => (
                <MaterialTable
                    key={sec.id}
                    section={sec}
                    onRowChange={handleRowChange}
                    onRowDelete={handleRowDelete}
                    onRowUpdate={handleRowUpdate}
                    onAddRow={handleAddRow}
                    onSectionDelete={handleDeleteSection}
                    projectData={projectData}
                />
            ))}
            <button
                className="btn btn-sm mt-3"
                style={{ backgroundColor: 'transparent', color: 'var(--app-text-primary)', border: '1px solid var(--app-border-mid)', transition: 'background-color 0.2s', fontWeight: 500 }}
                onClick={() => setShowAddModal(true)}
                onMouseEnter={(e) => { e.target.style.backgroundColor = 'var(--app-bg-alt)'; }}
                onMouseLeave={(e) => { e.target.style.backgroundColor = 'transparent'; }}
            >
                + Add Component Section
            </button>
            <AddComponentModal 
                show={showAddModal} 
                onHide={() => setShowAddModal(false)} 
                onAdd={handleAddSection} 
                defaultName={`Section ${sections.length + 1}`} 
            />
        </div>
    );
};

export default SubStructure;

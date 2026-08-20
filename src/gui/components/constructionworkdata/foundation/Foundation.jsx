import { useState, useCallback, useEffect } from 'react';
import { useProjectData } from '../../../../contexts/ProjectDataContext';
import { normalizeConstructionSections } from '../../../../utils/projectPageSchema';
import '../ConstructionWorkData.css';
import MaterialTable from '../MaterialTable';
import AddComponentModal from '../AddComponentModal';

// ── Helpers ───────────────────────────────────────────────────────────────────

let _uid = 0;
const uid = () => `row-${++_uid}`;

// ── Default sections for Foundation ──────────────────────────────────────────

const DEFAULT_SECTIONS = [
    { id: 'excavation', name: 'Excavation', rows: [] },
    { id: 'pile',       name: 'Pile',       rows: [] },
    { id: 'pile-cap',   name: 'Pile Cap',   rows: [] },
];

const defaultSections = () => normalizeConstructionSections(DEFAULT_SECTIONS, 'foundation');

// (MaterialTable imported from shared component)

// ── Foundation main component ─────────────────────────────────────────────────

const Foundation = () => {
    const { projectData, updateProjectData } = useProjectData();
    const [sections, setSections] = useState(() => {
        const saved = projectData.foundation_data;
        return (saved && saved.length > 0) ? normalizeConstructionSections(saved, 'foundation') : defaultSections();
    });
    const [showAddModal, setShowAddModal] = useState(false);

    useEffect(() => {
        const next = projectData.foundation_data?.length
            ? normalizeConstructionSections(projectData.foundation_data, 'foundation')
            : defaultSections();
        // Project imports replace context data while this tab remains mounted.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setSections(prev => JSON.stringify(next) !== JSON.stringify(prev) ? next : prev);
    }, [projectData.foundation_data]);

    useEffect(() => {
        updateProjectData('foundation_data', sections);
    }, [sections, updateProjectData]);

    const handleRowChange = useCallback((sectionId, rowId, field, value) => {
        setSections((prev) => {
            const next = prev.map((sec) =>
                sec.id !== sectionId ? sec : {
                    ...sec,
                    rows: sec.rows.map((r) =>
                        r.id !== rowId ? r : { ...r, [field]: value }
                    ),
                }
            );
            return next;
        });
    }, []);

    const handleRowDelete = useCallback((sectionId, rowId) => {
        if (!window.confirm('Move this item to trash?')) return;
        setSections((prev) => {
            const next = prev.map((sec) =>
                sec.id !== sectionId ? sec : {
                    ...sec,
                    rows: sec.rows.map((r) => r.id !== rowId ? r : { ...r, state: { ...(r.state || {}), in_trash: true } }),
                }
            );
            return next;
        });
    }, []);

    const handleRowUpdate = useCallback((sectionId, rowId, updatedRowData) => {
        setSections((prev) => {
            const next = prev.map((sec) =>
                sec.id !== sectionId ? sec : {
                    ...sec,
                    rows: sec.rows.map((r) =>
                        r.id !== rowId ? r : { ...r, ...updatedRowData }
                    ),
                }
            );
            return next;
        });
    }, []);

    const handleDeleteSection = useCallback((sectionId) => {
        setSections((prev) => prev.map((sec) => {
            if (sec.id !== sectionId) return sec;
            const activeCount = sec.rows.filter((row) => !row?.state?.in_trash).length;
            const message = activeCount
                ? `Move all ${activeCount} item(s) in "${sec.name}" to trash?`
                : `Delete component "${sec.name}"?\n\nIt will be hidden but can be recovered by restoring its materials from the trash.`;
            if (!window.confirm(message)) return sec;
            return activeCount
                ? { ...sec, rows: sec.rows.map((row) => ({ ...row, state: { ...(row.state || {}), in_trash: true } })) }
                : { ...sec, is_deleted: true };
        }));
    }, []);

    const handleAddRow = useCallback((sectionId, newRowData) => {
        setSections((prev) => {
            const next = prev.map((sec) =>
                sec.id !== sectionId ? sec : {
                    ...sec,
                    rows: [...sec.rows, { id: uid(), ...newRowData }],
                }
            );
            return next;
        });
    }, []);

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

export default Foundation;

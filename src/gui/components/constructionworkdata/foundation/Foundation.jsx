import React, { useState, useCallback, useEffect } from 'react';
import { useProjectData } from '../../../../contexts/ProjectDataContext';
import '../ConstructionWorkData.css';
import MaterialTable from '../MaterialTable';
import AddComponentModal from '../AddComponentModal';

// ── Helpers ───────────────────────────────────────────────────────────────────

let _uid = 0;
const uid = () => `row-${++_uid}`;

const emptyRow = () => ({
    id: uid(),
    workName: '',
    rate: '',
    qty: '',
    source: '',
});

// ── Default sections for Foundation ──────────────────────────────────────────

const DEFAULT_SECTIONS = [
    { id: 'excavation', name: 'Excavation', rows: [] },
    { id: 'pile',       name: 'Pile',       rows: [] },
    { id: 'pile-cap',   name: 'Pile Cap',   rows: [] },
];

// (MaterialTable imported from shared component)

// ── Foundation main component ─────────────────────────────────────────────────

const Foundation = ({ controller }) => {
    const { projectData, updateProjectData } = useProjectData();
    const [sections, setSections] = useState(() => {
        const saved = projectData.foundation_data;
        return (saved && saved.length > 0) ? saved : DEFAULT_SECTIONS;
    });
    const [showAddModal, setShowAddModal] = useState(false);

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
        setSections((prev) => {
            const next = prev.map((sec) =>
                sec.id !== sectionId ? sec : {
                    ...sec,
                    rows: sec.rows.filter((r) => r.id !== rowId),
                }
            );
            return next;
        });
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
            {sections.map((sec) => (
                <MaterialTable
                    key={sec.id}
                    section={sec}
                    onRowChange={handleRowChange}
                    onRowDelete={handleRowDelete}
                    onAddRow={handleAddRow}
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
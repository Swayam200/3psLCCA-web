import React, { useState, useCallback, useEffect } from 'react';
import { useProjectData } from '../../../../contexts/ProjectDataContext';
import '../ConstructionWorkData.css';
import MaterialTable from '../MaterialTable';
import AddComponentModal from '../AddComponentModal';

let _uid = 0;
const uid = () => `row-${++_uid}`;
// calcTotal removed as it's in MaterialTable.jsx

const DEFAULT_SECTIONS = [
    { id: 'abutment',  name: 'Abutment',  rows: [] },
    { id: 'pier',      name: 'Pier',      rows: [] },
    { id: 'pier-cap',  name: 'Pier Cap',  rows: [] },
    { id: 'pedestal',  name: 'Pedestal',  rows: [] },
    { id: 'bearing',   name: 'Bearing',   rows: [] },
];

// MaterialTable imported from shared component

const SubStructure = ({ controller }) => {
    const { projectData, updateProjectData } = useProjectData();
    const [sections, setSections] = useState(() => {
        const saved = projectData.substructure_data;
        return (saved && saved.length > 0) ? saved : DEFAULT_SECTIONS;
    });
    const [showAddModal, setShowAddModal] = useState(false);

    useEffect(() => {
        updateProjectData('substructure_data', sections);
    }, [sections, updateProjectData]);
    const handleRowChange = useCallback((sId, rId, field, val) => setSections((prev) => prev.map((s) => s.id !== sId ? s : { ...s, rows: s.rows.map((r) => r.id !== rId ? r : { ...r, [field]: val }) })), []);
    const handleRowDelete = useCallback((sId, rId) => setSections((prev) => prev.map((s) => s.id !== sId ? s : { ...s, rows: s.rows.filter((r) => r.id !== rId) })), []);
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
            {sections.map((sec) => <MaterialTable key={sec.id} section={sec} onRowChange={handleRowChange} onRowDelete={handleRowDelete} onAddRow={handleAddRow} projectData={projectData} />)}
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

/* eslint-disable no-unused-vars */
/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { createDefaultProject, normalizeProjectData } from '../utils/projectSchema';
import { normalizeProjectSection } from '../utils/projectPageSchema';

const ProjectDataContext = createContext();

export const useProjectData = () => useContext(ProjectDataContext);

export const ProjectDataProvider = ({ children, projectId = 'default', initialData, onStateChange }) => {
    const [projectData, setProjectData] = useState(() => {
        return normalizeProjectData(initialData);
    });

    useEffect(() => {
        // We notify parent, parent saves to cloud or local via projectStorageService
        if (onStateChange) {
            onStateChange(projectData);
        }
    }, [projectData, onStateChange]);

    // `data` may be an updater `(currentChunk, wholeProject) => nextChunk` so
    // pages can build on the latest stored chunk instead of a render-time
    // closure (two quick saves from one page must not clobber each other).
    const updateProjectData = useCallback((chunkName, data) => {
        setProjectData(prev => {
            const resolved = typeof data === 'function' ? data(prev[chunkName], prev) : data;
            const normalizedData = normalizeProjectSection(chunkName, resolved, prev);
            const next = { ...prev, [chunkName]: normalizedData };
            if (chunkName === 'maintenance_repair_data') {
                next.maintenance_data = normalizedData;
            }
            if (chunkName === 'general_info' && normalizedData?.project_name && normalizedData.project_name !== prev.name) {
                next.name = normalizedData.project_name;
            }
            return next;
        });
    }, []);

    const clearProjectData = useCallback(() => {
        setProjectData(createDefaultProject());
    }, []);

    return (
        <ProjectDataContext.Provider value={{ projectData, updateProjectData, clearProjectData }}>
            {children}
        </ProjectDataContext.Provider>
    );
};

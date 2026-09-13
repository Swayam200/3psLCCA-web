import { act, render, renderHook, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ProjectDataProvider, useProjectData } from '../../src/contexts/ProjectDataContext.jsx';

const initialData = { name: 'Bridge A', general_info: { project_name: 'Bridge A' }, bridge_data: { span: 20 } };
function setup() {
    const onStateChange = vi.fn();
    const wrapper = ({ children }) => <ProjectDataProvider initialData={initialData} onStateChange={onStateChange}>{children}</ProjectDataProvider>;
    return { ...renderHook(useProjectData, { wrapper }), onStateChange };
}

describe('project state updates', () => {
    it('keeps both rapid functional updates and leaves unrelated sections intact', () => {
        const { result, onStateChange } = setup();
        act(() => {
            result.current.updateProjectData('general_info', (current) => ({ ...current, project_name: 'Renamed' }));
            result.current.updateProjectData('general_info', (current, project) => ({ ...current, project_code: `${project.bridge_data.span}-CODE` }));
        });
        expect(result.current.projectData.name).toBe('Renamed');
        expect(result.current.projectData.general_info.project_code).toBe('20-CODE');
        expect(result.current.projectData.bridge_data.span).toBe(20);
        expect(onStateChange).toHaveBeenLastCalledWith(result.current.projectData);
        expect(initialData.general_info.project_name).toBe('Bridge A');
    });

    it('maintains the legacy maintenance alias after an edit', () => {
        const { result } = setup();
        act(() => result.current.updateProjectData('maintenance_repair_data', { routine_inspection_cost: '0', routine_inspection_freq: '2' }));
        expect(result.current.projectData.maintenance_data).toEqual(result.current.projectData.maintenance_repair_data);
        expect(Number(result.current.projectData.maintenance_data.routine_inspection_freq)).toBe(2);
    });

    it('keeps the updater stable across renders and clears project data', () => {
        const { result } = setup();
        const update = result.current.updateProjectData;
        act(() => update('general_info', { project_name: 'Temporary' }));
        expect(result.current.updateProjectData).toBe(update);
        act(() => result.current.clearProjectData());
        expect(result.current.projectData.general_info.project_name).not.toBe('Temporary');
    });

    it('loads the next project when its keyed provider is replaced', () => {
        function Consumer() { return <span>{useProjectData().projectData.name}</span>; }
        const { rerender } = render(<ProjectDataProvider key="a" initialData={initialData}><Consumer /></ProjectDataProvider>);
        expect(screen.getByText('Bridge A')).toBeTruthy();
        rerender(<ProjectDataProvider key="b" initialData={{ name: 'Bridge B' }}><Consumer /></ProjectDataProvider>);
        expect(screen.queryByText('Bridge A')).toBeNull();
        expect(screen.getByText('Bridge B')).toBeTruthy();
    });
});

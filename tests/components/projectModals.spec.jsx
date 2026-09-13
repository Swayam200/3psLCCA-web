import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import RenameProjectModal from '../../src/gui/components/RenameProjectModal.jsx';
import NewProjectModal from '../../src/gui/components/NewProjectModal.jsx';

describe('rename project', () => {
    it('submits the entered name using Enter and closes the modal', () => {
        const onRename = vi.fn();
        const onHide = vi.fn();
        render(<RenameProjectModal show currentName="Original" onRename={onRename} onHide={onHide} />);
        const input = screen.getByPlaceholderText('Enter new project name');
        expect(input.value).toBe('Original');
        fireEvent.change(input, { target: { value: 'Renamed Bridge' } });
        fireEvent.keyDown(input, { key: 'Enter' });
        expect(onRename).toHaveBeenCalledExactlyOnceWith('Renamed Bridge');
        expect(onHide).toHaveBeenCalledTimes(1);
    });
    it('rejects blank names without saving or closing', () => {
        const onRename = vi.fn();
        const onHide = vi.fn();
        vi.spyOn(window, 'alert').mockImplementation(() => {});
        render(<RenameProjectModal show currentName="Original" onRename={onRename} onHide={onHide} />);
        fireEvent.change(screen.getByPlaceholderText('Enter new project name'), { target: { value: '   ' } });
        fireEvent.click(screen.getByRole('button', { name: 'OK' }));
        expect(window.alert).toHaveBeenCalledWith('Project name cannot be empty.');
        expect(onRename).not.toHaveBeenCalled();
        expect(onHide).not.toHaveBeenCalled();
    });
    it('restores the persisted name when reopened after cancelling a draft', () => {
        const props = { currentName: 'Saved', onRename: vi.fn(), onHide: vi.fn() };
        const { rerender } = render(<RenameProjectModal {...props} show />);
        fireEvent.change(screen.getByPlaceholderText('Enter new project name'), { target: { value: 'Unsaved' } });
        fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
        expect(props.onRename).not.toHaveBeenCalled();
        rerender(<RenameProjectModal {...props} show={false} />);
        rerender(<RenameProjectModal {...props} show />);
        expect(screen.getByPlaceholderText('Enter new project name').value).toBe('Saved');
    });
});

describe('new project', () => {
    it('shows required-field errors and does not create an incomplete project', () => {
        const onCreate = vi.fn();
        const onHide = vi.fn();
        render(<NewProjectModal show onCreate={onCreate} onHide={onHide} />);
        fireEvent.click(screen.getByRole('button', { name: /create/i }));
        expect(screen.getByText('Please enter a Project Name.')).toBeTruthy();
        expect(screen.getByText('Please select a Country.')).toBeTruthy();
        expect(onCreate).not.toHaveBeenCalled();
        expect(onHide).not.toHaveBeenCalled();
    });
    it('creates with a trimmed name and permits an empty optional material database', () => {
        const onCreate = vi.fn();
        const onHide = vi.fn();
        render(<NewProjectModal show onCreate={onCreate} onHide={onHide} />);
        fireEvent.change(screen.getByPlaceholderText('e.g. Highway 5 Bridge Replacement'), { target: { value: '  Test Bridge  ' } });
        // Existing selects do not associate labels; locate them by their option sets.
        const selects = screen.getAllByRole('combobox');
        const country = selects.find(el => [...el.options].some(o => o.textContent.includes('Select country')));
        const currency = selects.find(el => [...el.options].some(o => o.value === 'INR'));
        fireEvent.change(country, { target: { value: country.options[1].value } });
        fireEvent.change(currency, { target: { value: 'INR' } });
        fireEvent.click(screen.getByRole('button', { name: /create/i }));
        expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({ name: 'Test Bridge', currency: 'INR', unitSystem: 'Metric (SI)', sorDatabase: '' }));
        expect(onHide).toHaveBeenCalledTimes(1);
    });
    it('discards an old draft when reopened', () => {
        const props = { onCreate: vi.fn(), onHide: vi.fn() };
        const { rerender } = render(<NewProjectModal {...props} show />);
        fireEvent.change(screen.getByPlaceholderText('e.g. Highway 5 Bridge Replacement'), { target: { value: 'Discard me' } });
        rerender(<NewProjectModal {...props} show={false} />);
        rerender(<NewProjectModal {...props} show />);
        expect(screen.getByPlaceholderText('e.g. Highway 5 Bridge Replacement').value).toBe('');
        expect(props.onCreate).not.toHaveBeenCalled();
    });
});

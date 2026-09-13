import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import SettingsModal from '../../src/gui/components/SettingsModal.jsx';
import FinancialData from '../../src/gui/components/financialdata/FinancialData.jsx';
import { ProjectDataProvider } from '../../src/contexts/ProjectDataContext.jsx';
import { saveProfile } from '../../src/gui/utils/profileStorage.js';

it('settings restore the selected profile on open and save general settings', () => {
    saveProfile('Test Agency', { agency_name: 'Agency Ltd', contact_person: 'Assessor' });
    const onSaveSettings = vi.fn();
    const handleClose = vi.fn();
    render(<SettingsModal show theme={{}} initialUserName="Original User" userSettings={{ appearanceMode: 'Light' }} onSaveSettings={onSaveSettings} handleClose={handleClose} />);
    fireEvent.change(screen.getByDisplayValue('Original User'), { target: { value: 'Renamed User' } });
    fireEvent.click(screen.getByRole('tab', { name: 'Profiles' }));
    expect(screen.getByDisplayValue('Agency Ltd')).toBeTruthy();
    expect(screen.getByDisplayValue('Assessor')).toBeTruthy();
    fireEvent.click(screen.getByRole('tab', { name: 'General' }));
    fireEvent.click(screen.getByRole('button', { name: /save/i }));
    expect(onSaveSettings).toHaveBeenCalledWith(expect.objectContaining({ displayName: 'Renamed User' }));
    expect(handleClose).toHaveBeenCalledTimes(1);
});

it('settings without an active profile initialize an empty profile form', () => {
    render(<SettingsModal show theme={{}} initialUserName="User" userSettings={{}} onSaveSettings={vi.fn()} handleClose={vi.fn()} />);
    fireEvent.click(screen.getByRole('tab', { name: 'Profiles' }));
    expect(screen.getByRole('option', { name: '+ New Profile' }).selected).toBe(true);
    expect(screen.queryByDisplayValue('Agency Ltd')).toBeNull();
});

it('financial inputs restore saved values and persist a valid zero', async () => {
    const onStateChange = vi.fn();
    const { container } = render(<ProjectDataProvider initialData={{ financial_data: { discount_rate: 6.7 } }} onStateChange={onStateChange}><FinancialData /></ProjectDataProvider>);
    const input = container.querySelector('#discount_rate');
    expect(input.value).toBe('6.7');
    fireEvent.change(input, { target: { value: '0' } });
    fireEvent.blur(input);
    await waitFor(() => expect(Number(onStateChange.mock.lastCall[0].financial_data.discount_rate)).toBe(0));
    expect(input.getAttribute('aria-invalid')).not.toBe('true');
});

it('financial inputs still show out-of-range validation on blur', () => {
    const { container } = render(<ProjectDataProvider initialData={{ financial_data: { discount_rate: 6.7 } }}><FinancialData /></ProjectDataProvider>);
    const input = container.querySelector('#discount_rate');
    fireEvent.change(input, { target: { value: '-1' } });
    fireEvent.blur(input);
    expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(container.querySelector('#discount_rate-error').textContent).toMatch(/must|least|between/i);
});

/* eslint-disable no-unused-vars */
import React, { useState } from 'react';
import { Modal, Button, Form } from 'react-bootstrap';
import Select from 'react-select';
import { COUNTRIES, CURRENCIES, COUNTRY_TO_CURRENCY } from './utils/countriesdata';
import { materialCatalog } from './utils/materialCatalog';

const countryOptions = COUNTRIES.map(c => ({ value: c, label: c }));
const currencyOptions = CURRENCIES.map(c => ({ value: c, label: c }));
const sorOptions = Object.keys(materialCatalog).map(key => ({ value: key, label: key }));
const unitOptions = [
    { value: 'Metric (SI)', label: 'Metric (SI)' },
    { value: 'Imperial (US)', label: 'Imperial (US)' }
];

const getCustomSelectStyles = (isDark, brandColor) => ({
    control: (provided, state) => ({
        ...provided,
        fontSize: '0.9rem',
        backgroundColor: isDark ? '#36393f' : '#ffffff',
        borderColor: state.isFocused ? brandColor : (isDark ? '#202225' : '#ced4da'),
        color: isDark ? '#fff' : '#333',
        minHeight: '36px',
        height: '36px',
        boxShadow: state.isFocused ? `0 0 0 1px ${brandColor}` : 'none',
        '&:hover': {
            borderColor: state.isFocused ? brandColor : (isDark ? '#4f545c' : '#adb5bd')
        }
    }),
    valueContainer: (provided) => ({
        ...provided,
        padding: '0 10px',
        height: '36px'
    }),
    input: (provided) => ({
        ...provided,
        color: isDark ? '#fff' : '#333',
        margin: '0px',
        padding: '0px'
    }),
    singleValue: (provided) => ({
        ...provided,
        color: isDark ? '#b9bbbe' : '#495057'
    }),
    placeholder: (provided) => ({
        ...provided,
        color: isDark ? '#72767d' : '#868e96'
    }),
    menu: (provided) => ({
        ...provided,
        backgroundColor: isDark ? '#2f3136' : '#ffffff',
        border: isDark ? '1px solid #202225' : '1px solid #e9ecef',
        boxShadow: isDark ? '0 4px 6px rgba(0,0,0,0.3)' : '0 4px 6px rgba(0,0,0,0.1)',
        zIndex: 9999
    }),
    option: (provided, state) => ({
        ...provided,
        fontSize: '0.9rem',
        backgroundColor: state.isFocused ? (isDark ? '#4f545c' : '#f1f3f5') : 'transparent',
        color: isDark ? '#fff' : '#333',
        cursor: 'pointer',
        padding: '6px 12px'
    }),
    indicatorSeparator: () => ({
        display: 'none'
    }),
    dropdownIndicator: (provided) => ({
        ...provided,
        color: isDark ? '#b9bbbe' : '#adb5bd',
        padding: '6px',
        '&:hover': {
            color: isDark ? '#fff' : '#495057'
        }
    }),
    indicatorsContainer: (provided) => ({
        ...provided,
        height: '36px'
    }),
    menuPortal: (provided) => ({
        ...provided,
        zIndex: 9999
    })
});

const NewProject = ({ show, handleClose, onProjectOpen, onProjectCreate, isDarkMode = false, theme = {} }) => {
    const [projectName, setProjectName] = useState('');
    const [country, setCountry] = useState(null);
    const [currency, setCurrency] = useState(null);
    const [unitSystem, setUnitSystem] = useState({ value: 'Metric (SI)', label: 'Metric (SI)' });
    const [sorDatabase, setSorDatabase] = useState(null); // optional
    const [validated, setValidated] = useState(false);

    const brandColor = theme?.activeIconColor || '#8bc34a';

    const colors = {
        modalBg: 'var(--app-bg-card)',
        text: 'var(--app-text-primary)',
        textMuted: 'var(--app-text-secondary)',
        inputBg: 'var(--app-bg-main)',
        inputBorder: 'var(--app-border-mid)',
        headerIconBg: brandColor,
        cancelBtnBg: 'var(--app-bg-alt)',
        cancelBtnColor: 'var(--app-text-primary)',
        cancelBtnBorder: 'var(--app-border-mid)',
    };

    const closeModal = () => {
        setValidated(false);
        handleClose();
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        setValidated(true);

        if (!projectName || !country || !currency || !unitSystem) {
            return;
        }

        const projectData = {
            name: projectName,
            country: country.value,
            currency: currency.value,
            unitSystem: unitSystem.value,
            sorDatabase: sorDatabase?.value || '',
            createdAt: new Date().toLocaleString()
        };

        setProjectName('');
        setCountry(null);
        setCurrency(null);
        setUnitSystem({ value: 'Metric (SI)', label: 'Metric (SI)' });
        setSorDatabase(null);
        setValidated(false);

        handleClose();
        if (onProjectCreate) {
            onProjectCreate(projectData);
        } else if (onProjectOpen) {
            onProjectOpen();
        }
    };

    const customSelectStyles = getCustomSelectStyles(isDarkMode, brandColor);

    return (
        <Modal show={show} onHide={closeModal} centered backdrop="static" keyboard={false}>
            {/* Wrapping Modal content to force styling */}
            <div className="overflow-hidden" style={{ backgroundColor: colors.modalBg, color: colors.text, borderRadius: '6px', transition: 'all 0.3s' }}>
                <Modal.Header closeButton style={{ borderBottom: 'none', paddingBottom: '0' }} className="custom-theme-modal-header pt-3 px-4">
                    <Modal.Title className="d-flex align-items-center fw-bold" style={{ fontSize: '1rem', gap: '8px' }}>
                        <span className="d-inline-block" style={{ width: '12px', height: '12px', backgroundColor: colors.headerIconBg, borderRadius: '2px' }}></span>
                        New Project
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body className="pt-2 px-4 pb-4">
                    <Form onSubmit={handleSubmit} noValidate>
                        <Form.Group className="mb-2">
                            <Form.Label className="fw-bold mb-1" style={{ fontSize: '0.85rem', color: colors.text }}>Project Name</Form.Label>
                            <Form.Control
                                type="text"
                                placeholder="e.g. Highway 5 Bridge Replacement"
                                value={projectName}
                                onChange={(e) => setProjectName(e.target.value)}
                                style={{
                                    fontSize: '0.9rem',
                                    backgroundColor: colors.inputBg,
                                    color: colors.textMuted,
                                    borderColor: (validated && !projectName) ? '#dc3545' : colors.inputBorder,
                                    minHeight: '36px',
                                    height: '36px',
                                    boxShadow: 'none'
                                }}
                                autoComplete="off"
                                isInvalid={validated && !projectName}
                                className="custom-theme-input"
                            />
                            <style>{`
                                .custom-theme-input:focus {
                                    border-color: ${brandColor} !important;
                                    box-shadow: 0 0 0 1px ${brandColor} !important;
                                    color: ${colors.text} !important;
                                }
                                .custom-theme-modal-header .btn-close {
                                    filter: ${isDarkMode ? 'invert(1) grayscale(100%) brightness(200%)' : 'none'};
                                }
                            `}</style>
                            <Form.Control.Feedback type="invalid" style={{ fontSize: '0.75rem' }}>
                                Please enter a Project Name.
                            </Form.Control.Feedback>
                            {(!validated || projectName) && (
                                <Form.Text style={{ fontSize: '0.75rem', color: colors.textMuted, display: 'block', marginTop: '2px' }}>
                                    You can rename this later.
                                </Form.Text>
                            )}
                        </Form.Group>

                        <Form.Group className="mb-2">
                            <Form.Label className="fw-bold mb-1" style={{ fontSize: '0.85rem', color: colors.text }}>Country</Form.Label>
                            <Select
                                options={countryOptions}
                                value={country}
                                onChange={(selectedCountry) => {
                                    setCountry(selectedCountry);
                                    if (selectedCountry && COUNTRY_TO_CURRENCY[selectedCountry.value]) {
                                        const currCode = COUNTRY_TO_CURRENCY[selectedCountry.value];
                                        setCurrency({ value: currCode, label: currCode });
                                    } else {
                                        setCurrency(null);
                                    }
                                }}
                                placeholder="— Select country —"
                                styles={customSelectStyles}
                                menuPlacement="auto"
                                menuPortalTarget={document.body}
                                menuPosition="fixed"
                                maxMenuHeight={180}
                                isSearchable
                            />
                            {validated && !country ? (
                                <div className="text-danger mt-1" style={{ fontSize: '0.75rem' }}>
                                    Please select a Country.
                                </div>
                            ) : (
                                <Form.Text style={{ fontSize: '0.75rem', color: colors.textMuted, display: 'block', marginTop: '2px' }}>
                                    Cannot be changed after project creation.
                                </Form.Text>
                            )}
                        </Form.Group>

                        <Form.Group className="mb-2">
                            <Form.Label className="fw-bold mb-1" style={{ fontSize: '0.85rem', color: colors.text }}>Currency</Form.Label>
                            <Select
                                options={currencyOptions}
                                value={currency}
                                onChange={setCurrency}
                                placeholder="— Select currency —"
                                styles={customSelectStyles}
                                menuPlacement="auto"
                                menuPortalTarget={document.body}
                                menuPosition="fixed"
                                maxMenuHeight={180}
                                isSearchable
                                isDisabled={true}
                            />
                            {validated && !currency ? (
                                <div className="text-danger mt-1" style={{ fontSize: '0.75rem' }}>
                                    Please select a Currency.
                                </div>
                            ) : (
                                <Form.Text style={{ fontSize: '0.75rem', color: colors.textMuted, display: 'block', marginTop: '2px' }}>
                                    Auto-filled based on the selected country. Cannot be changed after project creation.
                                </Form.Text>
                            )}
                        </Form.Group>

                        <Form.Group className="mb-3">
                            <Form.Label className="fw-bold mb-1" style={{ fontSize: '0.85rem', color: colors.text }}>Unit System</Form.Label>
                            <Select
                                options={unitOptions}
                                value={unitSystem}
                                onChange={setUnitSystem}
                                placeholder="— Select unit system —"
                                styles={customSelectStyles}
                                menuPlacement="auto"
                                menuPortalTarget={document.body}
                                menuPosition="fixed"
                                maxMenuHeight={180}
                                isSearchable={false}
                            />
                            {validated && !unitSystem ? (
                                <div className="text-danger mt-1" style={{ fontSize: '0.75rem' }}>
                                    Please select a Unit System.
                                </div>
                            ) : (
                                <Form.Text style={{ fontSize: '0.75rem', color: colors.textMuted, display: 'block', marginTop: '2px' }}>
                                    Cannot be changed after project creation.
                                </Form.Text>
                            )}
                        </Form.Group>

                        <Form.Group className="mb-3">
                            <Form.Label className="fw-bold mb-1" style={{ fontSize: '0.85rem', color: colors.text }}>
                                Material Suggestions (SOR) <span style={{ fontWeight: 'normal', color: colors.textMuted }}>— optional</span>
                            </Form.Label>
                            <Select
                                options={sorOptions}
                                value={sorDatabase}
                                onChange={setSorDatabase}
                                placeholder="— None (choose later) —"
                                styles={customSelectStyles}
                                menuPlacement="auto"
                                menuPortalTarget={document.body}
                                menuPosition="fixed"
                                maxMenuHeight={180}
                                isClearable
                            />
                            <Form.Text style={{ fontSize: '0.75rem', color: colors.textMuted, display: 'block', marginTop: '2px' }}>
                                Auto-suggests material names, rates, and emission factors. Can be set or changed anytime in General Information.
                            </Form.Text>
                        </Form.Group>

                        <div className="d-flex justify-content-end gap-3 mt-3">
                            <Button
                                variant="primary"
                                type="submit"
                                style={{
                                    backgroundColor: brandColor,
                                    borderColor: brandColor,
                                    color: 'var(--app-bg-main)',
                                    fontWeight: 'bold',
                                    padding: '0.35rem 1.5rem',
                                    borderRadius: '4px',
                                    fontSize: '0.9rem'
                                }}
                            >
                                OK
                            </Button>
                            <Button
                                variant="secondary"
                                onClick={closeModal}
                                style={{
                                    backgroundColor: colors.cancelBtnBg,
                                    borderColor: colors.cancelBtnBorder,
                                    color: colors.cancelBtnColor,
                                    fontWeight: 'normal',
                                    padding: '0.35rem 1.25rem',
                                    borderRadius: '4px',
                                    fontSize: '0.9rem'
                                }}
                            >
                                Cancel
                            </Button>
                        </div>
                    </Form>
                </Modal.Body>
            </div>
        </Modal>
    );
};

export default NewProject;
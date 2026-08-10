import React, { useState, useEffect } from 'react';
import { Modal, Button, Form, Tabs, Tab } from 'react-bootstrap';
import Select from 'react-select';
import { data as countriesData } from './utils/countriesdata';
import ProfileAvatar from './ProfileAvatar';
import { getProfiles, saveProfile, deleteProfile, getActiveProfile } from '../utils/profileStorage';

const countryOptions = countriesData.map(c => ({ value: c.COUNTRY, label: c.COUNTRY }));

// The AI settings tab only exists in builds made with VITE_AI_ENABLED=true.
// The comparison stays inline so Vite folds it to a literal and drops the
// dynamic import (and the whole AI package) from flag-off bundles.
const AI_ENABLED = import.meta.env.VITE_AI_ENABLED === 'true';
const AiSettingsTabLazy = AI_ENABLED ? React.lazy(() => import('./ai/AiSettingsTab.jsx')) : null;

const getCustomSelectStyles = (isDark, brandColor) => ({
    control: (provided, state) => ({
        ...provided,
        fontSize: '14px',
        backgroundColor: isDark ? '#36393f' : '#ffffff',
        borderColor: state.isFocused ? brandColor : (isDark ? '#202225' : '#ced4da'),
        color: isDark ? '#fff' : '#333',
        minHeight: '36px',
        boxShadow: state.isFocused ? `0 0 0 1px ${brandColor}` : 'none',
        '&:hover': { borderColor: state.isFocused ? brandColor : (isDark ? '#4f545c' : '#adb5bd') }
    }),
    input: (provided) => ({ ...provided, color: isDark ? '#fff' : '#333' }),
    singleValue: (provided) => ({ ...provided, color: isDark ? '#b9bbbe' : '#495057' }),
    placeholder: (provided) => ({ ...provided, color: isDark ? '#72767d' : '#868e96' }),
    menu: (provided) => ({
        ...provided,
        backgroundColor: isDark ? '#2f3136' : '#ffffff',
        border: isDark ? '1px solid #202225' : '1px solid #e9ecef',
        zIndex: 9999
    }),
    menuPortal: base => ({ ...base, zIndex: 9999 }),
    option: (provided, state) => ({
        ...provided,
        fontSize: '13px',
        backgroundColor: state.isFocused ? (isDark ? '#4f545c' : '#f1f3f5') : 'transparent',
        color: isDark ? '#fff' : '#333',
        cursor: 'pointer',
        padding: '6px 12px'
    }),
    indicatorSeparator: () => ({ display: 'none' }),
    dropdownIndicator: (provided) => ({
        ...provided,
        color: isDark ? '#b9bbbe' : '#adb5bd',
        '&:hover': { color: isDark ? '#fff' : '#495057' }
    }),
});

const SettingsModal = ({ show, handleClose, isDarkMode, theme, initialUserName, userSettings, onSaveSettings, onLogout }) => {
    const [displayName, setDisplayName] = useState(initialUserName || '');
    const [appearanceMode, setAppearanceMode] = useState(userSettings?.appearanceMode || 'Auto(follow os)');
    const [lightTheme, setLightTheme] = useState(userSettings?.lightTheme || 'standard light');
    const [darkTheme, setDarkTheme] = useState(userSettings?.darkTheme || 'standard dark');
    
    // Profile state
    const [profiles, setProfiles] = useState({});
    const [selectedProfile, setSelectedProfile] = useState('+ New Profile');
    const [logoData, setLogoData] = useState(null);
    const [profileCountry, setProfileCountry] = useState(null);
    const [agencyName, setAgencyName] = useState('');
    const [contactName, setContactName] = useState('');
    const [agencyAddress, setAgencyAddress] = useState('');
    const [email, setEmail] = useState('');
    const [phone, setPhone] = useState('');
    const [activeTab, setActiveTab] = useState('general');

    // Load profiles when modal opens
    useEffect(() => {
        if (show) {
            setDisplayName(initialUserName || '');
            setAppearanceMode(userSettings?.appearanceMode || 'Auto(follow os)');
            setLightTheme(userSettings?.lightTheme || 'standard light');
            setDarkTheme(userSettings?.darkTheme || 'standard dark');
            
            // Load profiles
            const loadedProfiles = getProfiles();
            setProfiles(loadedProfiles);
            
            // Try to select active profile
            const active = getActiveProfile();
            if (active?.profile_name && loadedProfiles[active.profile_name]) {
                setSelectedProfile(active.profile_name);
                loadProfileData(active.profile_name, loadedProfiles[active.profile_name]);
            } else {
                setSelectedProfile('+ New Profile');
                clearProfileForm();
            }
        }
    }, [show, initialUserName, userSettings]);

    const loadProfileData = (name, data) => {
        setAgencyName(data.agency_name || '');
        setContactName(data.contact_person || '');
        setAgencyAddress(data.agency_address || '');
        setEmail(data.agency_email || '');
        setPhone(data.agency_phone || '');
        setLogoData(data.agency_logo || null);
        if (data.agency_country) {
            setProfileCountry({ value: data.agency_country, label: data.agency_country });
        } else {
            setProfileCountry(null);
        }
    };

    const clearProfileForm = () => {
        setAgencyName('');
        setContactName('');
        setAgencyAddress('');
        setEmail('');
        setPhone('');
        setLogoData(null);
        setProfileCountry(null);
    };

    const getProfileData = () => ({
        agency_name: agencyName,
        contact_person: contactName,
        agency_address: agencyAddress,
        agency_email: email,
        agency_phone: phone,
        agency_logo: logoData,
        agency_country: profileCountry?.value || ''
    });

    const handleProfileSelect = (e) => {
        const name = e.target.value;
        setSelectedProfile(name);
        
        if (name === '+ New Profile') {
            clearProfileForm();
        } else if (profiles[name]) {
            loadProfileData(name, profiles[name]);
        }
    };

    const handleDeleteProfile = () => {
        if (selectedProfile === '+ New Profile') return;
        
        if (window.confirm(`Delete '${selectedProfile}'?\nThis cannot be undone.`)) {
            deleteProfile(selectedProfile);
            const updated = getProfiles();
            setProfiles(updated);
            setSelectedProfile('+ New Profile');
            clearProfileForm();
        }
    };

    const handleSave = () => {
        // Only save profile if on Profiles tab
        if (activeTab === 'profiles') {
            const data = getProfileData();
            
            if (selectedProfile === '+ New Profile') {
                // Prompt for new profile name
                const name = window.prompt('Name for this profile:');
                if (!name) return; // User cancelled
                
                const trimmed = name.trim();
                if (!trimmed) {
                    alert('Profile name cannot be empty.');
                    return;
                }
                
                if (profiles[trimmed]) {
                    alert(`Profile '${trimmed}' already exists.`);
                    return;
                }
                
                saveProfile(trimmed, data);
                setProfiles(getProfiles());
                setSelectedProfile(trimmed);
            } else {
                // Update existing
                saveProfile(selectedProfile, data);
                setProfiles(getProfiles());
            }
        }
        
        // Save general settings
        if (onSaveSettings) {
            onSaveSettings({
                displayName,
                appearanceMode,
                lightTheme,
                darkTheme
            });
        }
        handleClose();
    };


    return (
        <Modal
            show={show}
            onHide={handleClose}
            centered
            size="md"
            backdrop="static"
            className="settings-modal"
            contentClassName="border-0 shadow-lg"
            style={{ fontFamily: '"Segoe UI", system-ui, sans-serif' }}
        >
            <style>{`
                .settings-modal .modal-content {
                    background-color: ${theme.bgCard};
                    color: ${theme.textPrimary};
                    border-radius: 8px;
                    overflow: hidden;
                }
                .settings-modal .modal-header {
                    background-color: ${theme.activeIconColor};
                    color: white;
                    border-bottom: none;
                    padding: 8px 16px;
                }
                .settings-modal .modal-title {
                    font-size: 14px;
                    font-weight: 500;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                }
                .settings-modal .btn-close-white {
                    font-size: 10px;
                }
                .settings-modal .nav-tabs {
                    border-bottom: 1px solid ${theme.border};
                    padding: 0 16px;
                    margin-top: 10px;
                }
                .settings-modal .nav-tabs .nav-link {
                    color: ${theme.textSecondary};
                    border: none;
                    border-bottom: 2px solid transparent;
                    padding: 8px 16px;
                    font-size: 14px;
                }
                .settings-modal .nav-tabs .nav-link.active {
                    color: ${theme.textPrimary};
                    background: transparent;
                    border-color: transparent transparent ${theme.activeIconColor} transparent;
                }
                .settings-modal .form-label {
                    font-weight: 600;
                    font-size: 13px;
                    color: ${theme.textPrimary};
                    margin-bottom: 2px;
                }
                .settings-modal .form-text {
                    font-size: 12px;
                    color: ${theme.textSecondary};
                    margin-bottom: 8px;
                }
                .settings-modal .form-control, .settings-modal .form-select {
                    background-color: ${theme.inputBg};
                    border: 1px solid ${theme.border};
                    color: ${theme.textPrimary};
                    font-size: 14px;
                    padding: 6px 12px;
                }
                .settings-modal .form-control:focus, .settings-modal .form-select:focus {
                    border-color: ${theme.activeIconColor};
                    box-shadow: 0 0 0 2px ${theme.activeIconColor}40;
                }
                .settings-modal .modal-footer {
                    border-top: none;
                    padding: 16px 24px;
                    background-color: ${theme.bgSidebar};
                }
                .settings-modal .btn-settings-save {
                    background-color: ${theme.inputBg};
                    border: 1px solid ${theme.activeIconColor};
                    color: ${theme.activeIconColor};
                    min-width: 80px;
                    font-size: 14px;
                }
                .settings-modal .btn-settings-save:hover {
                    background-color: ${theme.activeIconColor};
                    color: white;
                }
                .settings-modal .btn-settings-cancel {
                    background-color: ${theme.inputBg};
                    border: 1px solid ${theme.border};
                    color: ${theme.textPrimary};
                    min-width: 80px;
                    font-size: 14px;
                }
            `}</style>

            <Modal.Header>
                <Modal.Title>
                    <span className="d-inline-block" style={{ width: '12px', height: '12px', backgroundColor: theme.activeIconColor, marginRight: '4px' }}></span>
                    Settings
                </Modal.Title>
                <button type="button" className="btn-close btn-close-white" onClick={handleClose} aria-label="Close"></button>
            </Modal.Header>

            <Tabs defaultActiveKey="general" className="mb-3" onSelect={(k) => setActiveTab(k)}>
                <Tab eventKey="general" title="General">
                    <Modal.Body className="px-4 py-2" style={{ minHeight: '350px' }}>
                        <div style={{ border: `1px solid ${theme.border}`, padding: '20px', borderRadius: '4px', backgroundColor: theme.bgCard }}>

                            {/* Display Name */}
                            <Form.Group className="mb-4">
                                <Form.Label>Display Name</Form.Label>
                                <div className="form-text mt-0">Shown in reports and exports.</div>
                                <Form.Control
                                    type="text"
                                    value={displayName}
                                    onChange={(e) => setDisplayName(e.target.value)}
                                />
                            </Form.Group>

                            {/* Appearance Mode */}
                            <Form.Group className="mb-4">
                                <Form.Label>Appearance Mode</Form.Label>
                                <div className="form-text mt-0">Switch between light and dark mode. 'Auto(follow os)' follows your OS setting.</div>
                                <Form.Select value={appearanceMode} onChange={(e) => setAppearanceMode(e.target.value)}>
                                    <option value="Auto(follow os)">Auto(follow os)</option>
                                    <option value="light">light</option>
                                    <option value="dark">dark</option>
                                </Form.Select>
                            </Form.Group>

                            {/* Light Theme */}
                            <Form.Group className="mb-4">
                                <Form.Label>Light Theme</Form.Label>
                                <div className="form-text mt-0">Colour scheme used in light mode.</div>
                                <Form.Select value={lightTheme} onChange={(e) => setLightTheme(e.target.value)}>
                                    <option value="standard light">standard light</option>
                                    <option value="soft light">soft light</option>
                                    <option value="soft pink">soft pink</option>
                                </Form.Select>
                            </Form.Group>

                            {/* Dark Theme */}
                            <Form.Group className="mb-2">
                                <Form.Label>Dark Theme</Form.Label>
                                <div className="form-text mt-0">Colour scheme used in dark mode.</div>
                                <Form.Select value={darkTheme} onChange={(e) => setDarkTheme(e.target.value)}>
                                    <option value="Dracula">Dracula</option>
                                    <option value="Neon city standard dark">Neon city standard dark</option>
                                    <option value="standard dark">standard dark</option>
                                </Form.Select>
                            </Form.Group>

                            <div style={{ fontSize: '11px', color: theme.textSecondary, marginTop: '20px' }}>
                                Theme changes apply immediately on save.
                            </div>
                        </div>
                    </Modal.Body>
                </Tab>
                <Tab eventKey="profiles" title="Profiles">
                    <Modal.Body className="px-4 py-3" style={{ minHeight: '350px' }}>
                        <div className="overflow-y-auto" style={{ border: `1px solid ${theme.border}`, padding: '20px', borderRadius: '4px', backgroundColor: theme.bgCard, height: '400px' }}>
                            <p style={{ fontSize: '13px', color: theme.textSecondary, marginBottom: '20px' }}>
                                Profiles store your agency details - name, logo, and contact information. The active profile is used in generated reports and exports.
                            </p>

                            {/* Avatar */}
                            <div className="d-flex justify-content-center mb-4">
                                <ProfileAvatar
                                    size={80}
                                    profileName={selectedProfile !== '+ New Profile' ? selectedProfile : ''}
                                    logoData={logoData}
                                    onLogoChange={setLogoData}
                                    theme={theme}
                                />
                            </div>

                            {/* Profile selector + Delete button */}
                            <div className="d-flex gap-2 mb-4">
                                <Form.Select 
                                    value={selectedProfile} 
                                    onChange={handleProfileSelect}
                                    style={{ flex: 1 }}
                                >
                                    {Object.keys(profiles).sort().map(name => (
                                        <option key={name} value={name}>{name}</option>
                                    ))}
                                    <option value="+ New Profile">+ New Profile</option>
                                </Form.Select>
                                {selectedProfile !== '+ New Profile' && (
                                    <Button 
                                        variant="outline-danger" 
                                        size="sm"
                                        onClick={handleDeleteProfile}
                                    >
                                        Delete
                                    </Button>
                                )}
                            </div>

                            <Form.Group className="mb-4">
                                <Form.Label>Agency Name</Form.Label>
                                <Form.Control type="text" value={agencyName} onChange={e => setAgencyName(e.target.value)} />
                            </Form.Group>

                            <Form.Group className="mb-4">
                                <Form.Label>Assessor's Name</Form.Label>
                                <Form.Control type="text" value={contactName} onChange={e => setContactName(e.target.value)} />
                            </Form.Group>

                            <Form.Group className="mb-4">
                                <Form.Label>Agency Address</Form.Label>
                                <div className="form-text mt-0">Appears in the report footer.</div>
                                <Form.Control type="text" value={agencyAddress} onChange={e => setAgencyAddress(e.target.value)} />
                            </Form.Group>

                            <Form.Group className="mb-4">
                                <Form.Label>Country</Form.Label>
                                <div className="form-text mt-0">Country where the evaluating agency is based. Used for report localisation.</div>
                                <Select
                                    options={countryOptions}
                                    value={profileCountry}
                                    onChange={setProfileCountry}
                                    placeholder="— Search country —"
                                    styles={getCustomSelectStyles(isDarkMode, theme?.activeIconColor || '#8bc34a')}
                                    menuPlacement="auto"
                                    isSearchable
                                    menuPortalTarget={document.body}
                                    menuPosition="fixed"
                                />
                            </Form.Group>

                            <Form.Group className="mb-4">
                                <Form.Label>Email</Form.Label>
                                <Form.Control type="email" value={email} onChange={e => setEmail(e.target.value)} />
                            </Form.Group>

                            <Form.Group className="mb-4">
                                <Form.Label>Phone</Form.Label>
                                <Form.Control type="tel" value={phone} onChange={e => setPhone(e.target.value)} />
                            </Form.Group>

                        </div>
                    </Modal.Body>
                </Tab>
                {AiSettingsTabLazy && (
                    <Tab eventKey="ai" title="AI Assistant">
                        <Modal.Body className="px-4 py-2" style={{ minHeight: '350px' }}>
                            <React.Suspense fallback={null}>
                                <AiSettingsTabLazy theme={theme} />
                            </React.Suspense>
                        </Modal.Body>
                    </Tab>
                )}
            </Tabs>

            <Modal.Footer className="d-flex justify-content-between align-items-center">
                <Button variant="outline-danger" onClick={onLogout} style={{ fontSize: '14px', minWidth: '80px' }}>
                    Logout
                </Button>
                <div className="d-flex gap-2">
                    <Button className="btn-settings-save" onClick={handleSave}>
                        Save
                    </Button>
                    <Button className="btn-settings-cancel" onClick={handleClose}>
                        Cancel
                    </Button>
                </div>
            </Modal.Footer>
        </Modal>
    );
};

export default SettingsModal;

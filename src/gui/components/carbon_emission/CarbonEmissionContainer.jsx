/* eslint-disable no-unused-vars */
/* eslint-disable react-hooks/set-state-in-effect */
import React, { useState, useEffect } from 'react';
import MaterialEmissions from './MaterialEmissions';
import TransportationEmissions from './TransportationEmissions';
import MachineryEmissions from './MachineryEmissions';
import TrafficEmissions from './TrafficEmissions';
import SocialCost from './SocialCost';

const TABS = [
    { key: 'SocialCost', label: 'Social Cost of Carbon', component: SocialCost },
    { key: 'Material', label: 'Material Emissions', component: MaterialEmissions },
    { key: 'Transportation', label: 'Transportation Emissions', component: TransportationEmissions },
    { key: 'Machinery', label: 'Machinery/Equipment Emissions', component: MachineryEmissions },
    { key: 'Traffic', label: 'Traffic Rerouting Emissions', component: TrafficEmissions },
];

const CarbonEmissionContainer = ({ controller, initialTab = 'SocialCost', setActiveNode }) => {
    const [activeTab, setActiveTab] = useState(initialTab);

    useEffect(() => {
        setActiveTab(initialTab);
    }, [initialTab]);

    const handleTabClick = (tab) => {
        setActiveTab(tab.key);
        if (setActiveNode) setActiveNode(tab.label);
    };

    const ActiveComponent = TABS.find((t) => t.key === activeTab)?.component ?? SocialCost;

    return (
        <div className="d-flex flex-column h-100 overflow-hidden" style={{ backgroundColor: 'var(--app-bg-main)', color: 'var(--app-text-primary)' }}>
            {/* Native-style Tab Bar */}
            <div className="d-flex border-bottom px-2 flex-shrink-0 overflow-x-auto carbon-tab-strip" style={{ backgroundColor: 'var(--app-bg-card)', borderColor: 'var(--app-border-light)' }}>
                {TABS.map((tab) => {
                    const isActive = activeTab === tab.key;
                    return (
                        <button
                            key={tab.key}
                            className={`btn rounded-0 px-3 py-2 border-0 fw-medium ${isActive ? 'fw-bold active-tab-btn' : ''}`}
                            style={{
                                color: isActive ? 'var(--app-primary-accent)' : 'var(--app-text-secondary)',
                                borderBottom: isActive ? '2px solid var(--app-primary-accent)' : '2px solid transparent',
                                fontSize: '0.82rem',
                                whiteSpace: 'nowrap',
                                backgroundColor: 'transparent',
                                transition: 'color 0.2s ease'
                            }}
                            onClick={() => handleTabClick(tab)}
                        >
                            {tab.label}
                        </button>
                    );
                })}
            </div>

            {/* Active tab content */}
            <div className="flex-grow-1 overflow-y-auto custom-scrollbar">
                <div className="carbon-tab-content">
                    <ActiveComponent controller={controller} />
                </div>
            </div>

            <style>{`
                .carbon-tab-strip::-webkit-scrollbar {
                    height: 8px;
                }
                .carbon-tab-strip::-webkit-scrollbar-track {
                    background: var(--app-bg-card);
                }
                .carbon-tab-strip::-webkit-scrollbar-thumb {
                    background: var(--app-border-mid);
                    border-radius: 8px;
                }
                .carbon-tab-content {
                    min-height: 100%;
                }
                .custom-scrollbar::-webkit-scrollbar {
                    width: 14px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: var(--app-bg-main);
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: var(--app-text-muted);
                    border-radius: 10px;
                    border: 3px solid var(--app-bg-main);
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: var(--app-text-secondary);
                }
                .custom-scrollbar::-webkit-scrollbar-button:single-button {
                    background-color: var(--app-bg-main);
                    display: block;
                    background-size: 7px;
                    background-repeat: no-repeat;
                }
                .custom-scrollbar::-webkit-scrollbar-button:single-button:vertical:decrement {
                    height: 14px;
                    width: 14px;
                    background-position: center 6px;
                    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' fill='rgb(150,150,150)'><polygon points='50,0 0,100 100,100'/></svg>");
                }
                .custom-scrollbar::-webkit-scrollbar-button:single-button:vertical:increment {
                    height: 14px;
                    width: 14px;
                    background-position: center 4px;
                    background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='100' height='100' fill='rgb(150,150,150)'><polygon points='0,0 100,0 50,100'/></svg>");
                }
                .active-tab-btn {
                    color: var(--app-primary-accent) !important;
                }
                button:hover {
                    color: var(--app-text-primary) !important;
                    background-color: var(--app-bg-alt) !important;
                }
                .carbon-desktop-page {
                    padding: 16px 22px 24px;
                    color: var(--app-text-primary);
                    font-size: 0.82rem;
                }
                .carbon-desktop-page .form-control,
                .carbon-desktop-page .form-select,
                .carbon-desktop-page textarea {
                    background-color: var(--app-bg-alt);
                    color: var(--app-text-primary);
                    border-color: var(--app-border-mid);
                    border-radius: 4px;
                    min-height: 34px;
                    font-size: 0.82rem;
                }
                .carbon-desktop-page .form-control:focus,
                .carbon-desktop-page .form-select:focus,
                .carbon-desktop-page textarea:focus {
                    background-color: var(--app-bg-alt);
                    color: var(--app-text-primary);
                    border-color: var(--app-primary-accent);
                    box-shadow: 0 0 0 2px rgba(179, 136, 255, 0.18);
                }
                .carbon-desktop-page .form-control:disabled,
                .carbon-desktop-page .form-select:disabled {
                    opacity: 0.78;
                }
                .carbon-section {
                    margin-top: 28px;
                }
                .carbon-section-title {
                    color: var(--app-text-primary);
                    font-size: 1.02rem;
                    font-weight: 700;
                    margin-bottom: 12px;
                    padding-bottom: 12px;
                    border-bottom: 1px solid var(--app-border-light);
                }
                .carbon-field {
                    margin-bottom: 20px;
                }
                .carbon-label {
                    display: block;
                    color: var(--app-text-primary);
                    font-weight: 700;
                    font-size: 0.78rem;
                    margin-bottom: 3px;
                }
                .carbon-help {
                    color: var(--app-text-muted);
                    font-size: 0.74rem;
                    line-height: 1.35;
                    margin-bottom: 7px;
                }
                .carbon-required {
                    color: #ff6b6b;
                    margin-left: 2px;
                }
                .carbon-summary-strip {
                    border: 1px solid var(--app-border-mid);
                    background: var(--app-bg-card);
                    border-radius: 4px;
                    padding: 9px 12px;
                }
                .carbon-desktop-table {
                    --bs-table-bg: var(--app-bg-card);
                    --bs-table-color: var(--app-text-primary);
                    --bs-table-border-color: var(--app-border-mid);
                    font-size: 0.78rem;
                    border: 1px solid var(--app-border-mid);
                }
                .carbon-desktop-table th {
                    background: var(--app-bg-alt) !important;
                    color: var(--app-text-secondary) !important;
                    text-align: center;
                    vertical-align: middle;
                    font-weight: 700;
                }
                .carbon-desktop-table td {
                    vertical-align: middle;
                }
            `}</style>
        </div>
    );
};

export default CarbonEmissionContainer;

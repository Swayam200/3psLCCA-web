import { useEffect, useState } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import { formatNumber, parseNumber } from './carbonUtils';

const SOURCE_CUSTOM = 'Custom / Manual Override';

const SocialCost = () => {
    const { projectData, updateProjectData } = useProjectData();
    const currency = projectData.general_info?.project_currency || projectData.currency || 'INR';
    const saved = projectData.carbon_emission_data?.social_cost_data || {};
    const savedCustom = saved.custom || {};
    // Older projects may have stored the SCC under Ricke or NITI Aayog modes;
    // carry the numeric value forward as the custom value.
    const legacyCost = parseNumber(
        saved.result?.cost_of_carbon_local ??
        saved.cost_of_carbon_local ??
        saved.calculated_scc_local ??
        saved.custom_scc,
        0
    );

    const [custom, setCustom] = useState({
        entered_value: parseNumber(savedCustom.entered_value ?? savedCustom.scc_value ?? legacyCost, 0),
        source: savedCustom.source || '',
        comments: savedCustom.comments || '',
    });

    const currentCost = parseNumber(custom.entered_value);

    const saveData = (nextCustom = custom, nextCost = currentCost) => {
        const prev = projectData.carbon_emission_data || {};
        const result = {
            selected_mode: SOURCE_CUSTOM,
            cost_of_carbon_local: nextCost,
            currency,
            unit: `${currency}/kgCO2e`,
        };
        updateProjectData('carbon_emission_data', {
            ...prev,
            social_cost_data: {
                ...prev.social_cost_data,
                source: SOURCE_CUSTOM,
                custom: {
                    entered_value: parseNumber(nextCustom.entered_value),
                    currency,
                    unit: `${currency}/kgCO2e`,
                    source: nextCustom.source || '',
                    comments: nextCustom.comments || '',
                },
                result,
                cost_of_carbon_local: nextCost,
                calculated_scc_local: nextCost,
                currency,
            },
        });
    };

    // One-time migration: legacy Ricke / NITI Aayog projects carry their value
    // forward as a custom entry. Runs only while the stored mode is not yet
    // custom, so ordinary visits to this page write nothing. User edits save
    // explicitly below — persisting from a reactive effect is what looped
    // React elsewhere on this page (see MaterialEmissions).
    useEffect(() => {
        if ((saved.mode || saved.source) !== SOURCE_CUSTOM) saveData(custom, currentCost);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const updateCustom = (field, value) => {
        const next = { ...custom, [field]: value };
        setCustom(next);
        saveData(next, parseNumber(next.entered_value));
    };

    const resetCustom = () => {
        const next = { entered_value: 0, source: '', comments: '' };
        setCustom(next);
        saveData(next, 0);
    };

    return (
        <div className="carbon-desktop-page">
            {(saved.mode === 'NITI Aayog' || saved.ricke) && (
                <div className="alert alert-warning py-2" style={{ fontSize: '0.82rem' }}>
                    A legacy Social Cost of Carbon mode was found in this project. The numeric
                    value has been preserved below as a custom value.
                </div>
            )}

            <div className="carbon-section">
                <div className="carbon-section-title">Custom Social Cost of Carbon</div>
                <div className="carbon-field">
                    <label className="carbon-label">Social Cost of Carbon (SCC)</label>
                    <div className="carbon-help">Manual value to apply in backend carbon cost calculations.</div>
                    <div className="input-group input-group-sm">
                        <input className="form-control" type="number" value={custom.entered_value} onChange={(event) => updateCustom('entered_value', event.target.value)} />
                        <span className="input-group-text">{currency}/kgCO2e</span>
                    </div>
                </div>
                <div className="carbon-field">
                    <label className="carbon-label">Source</label>
                    <input className="form-control form-control-sm" value={custom.source} onChange={(event) => updateCustom('source', event.target.value)} />
                </div>
                <div className="carbon-field">
                    <label className="carbon-label">Comments</label>
                    <textarea className="form-control" rows="5" value={custom.comments} onChange={(event) => updateCustom('comments', event.target.value)} />
                </div>
            </div>
            <div className="carbon-summary-strip fw-bold">Social Cost of Carbon: {formatNumber(currentCost, 6)} {currency}/kgCO2e</div>
            <button className="btn btn-sm btn-outline-light mt-3 w-100" onClick={resetCustom}>Clear All</button>
        </div>
    );
};

export default SocialCost;

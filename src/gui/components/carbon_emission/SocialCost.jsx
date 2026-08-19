import { useEffect, useMemo, useState } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import { formatNumber, getProjectCountryIso3, parseNumber } from './carbonUtils';
import { loadCsccCountry, loadCsccIndex, prefetchCsccCountry } from '../../../lib/cscc';

import {
    SOURCE_RICKE,
    SOURCE_CUSTOM,
    SSP_OPTIONS,
    RCP_OPTIONS,
    DAMAGE_FUNCTION_OPTIONS,
    DAMAGE_PARAMETER_OPTIONS,
    CLIMATE_OPTIONS,
    DISCOUNT_OPTIONS,
    PERCENTILE_OPTIONS,
    computeRicke,
} from './rickeCompute';

const SocialCost = () => {
    const { projectData, updateProjectData } = useProjectData();
    const currency = projectData.general_info?.project_currency || projectData.currency || 'INR';
    const projectIso = getProjectCountryIso3(projectData);
    const saved = projectData.carbon_emission_data?.social_cost_data || {};
    const savedRicke = saved.ricke || {};
    const savedCustom = saved.custom || {};
    const legacyCost = parseNumber(
        saved.result?.cost_of_carbon_local ??
        saved.cost_of_carbon_local ??
        saved.calculated_scc_local ??
        saved.custom_scc,
        0
    );

    const initialSource = saved.source === SOURCE_CUSTOM || saved.mode === SOURCE_CUSTOM || saved.mode === 'custom'
        ? SOURCE_CUSTOM
        : SOURCE_RICKE;

    const [source, setSource] = useState(initialSource);
    // Desktop parity: every combo starts unselected ("-- select --") unless
    // the project already stored a choice. iso3 alone gets a default (the
    // project country, else WLD) and is locked whenever the project fixes it.
    const [ricke, setRicke] = useState({
        iso3: savedRicke.iso3 || projectIso || 'WLD',
        ssp: savedRicke.ssp || '',
        rcp: savedRicke.rcp || '',
        dmg_func: savedRicke.dmg_func || '',
        dmg_params: savedRicke.dmg_params || '',
        climate_uncertainty: savedRicke.climate_uncertainty || '',
        discounting: savedRicke.discounting || '',
        percentile: savedRicke.percentile || '',
        usd_to_local_rate: parseNumber(savedRicke.usd_to_local_rate ?? saved.usd_rate, 0),
        cpi_ratio: parseNumber(savedRicke.cpi_ratio, 1),
    });
    const [custom, setCustom] = useState({
        entered_value: parseNumber(savedCustom.entered_value ?? savedCustom.scc_value ?? legacyCost, 0),
        source: savedCustom.source || '',
        comments: savedCustom.comments || '',
    });
    const [countryList, setCountryList] = useState([]);
    // Which country's slice is materialized (or failed). "Loading" is
    // derived — the requested iso3 differing from the resolved one — so the
    // load effect never has to set state synchronously.
    const [db, setDb] = useState({ iso3: '', data: null, error: '' });

    // Warm the caches for the project's own country the moment the page
    // mounts — by the time the user opens Ricke mode the ~11 KB slice is
    // usually already local (session promise cache + browser HTTP cache).
    useEffect(() => {
        prefetchCsccCountry(projectIso || 'WLD');
        let active = true;
        loadCsccIndex()
            .then((index) => { if (active) setCountryList(index.countries || []); })
            .catch(() => { });
        return () => { active = false; };
    }, [projectIso]);

    // Load the selected country's slice whenever Ricke mode needs it.
    useEffect(() => {
        if (source !== SOURCE_RICKE || !ricke.iso3) return undefined;
        let active = true;
        loadCsccCountry(ricke.iso3)
            .then((data) => { if (active) setDb({ iso3: ricke.iso3, data, error: '' }); })
            .catch((error) => { if (active) setDb({ iso3: ricke.iso3, data: null, error: error.message }); });
        return () => { active = false; };
    }, [source, ricke.iso3]);

    const countryData = db.iso3 === ricke.iso3 ? db.data : null;
    const dbError = db.iso3 === ricke.iso3 ? db.error : '';
    const dbLoading = Boolean(ricke.iso3) && countryData === null && !dbError;
    const rickeResult = useMemo(
        () => computeRicke(ricke, countryData, currency),
        [ricke, countryData, currency]
    );

    const currentCost = source === SOURCE_RICKE ? rickeResult.cost : parseNumber(custom.entered_value);

    const saveData = (nextSource, nextRicke, nextCustom, nextCost) => {
        const prev = projectData.carbon_emission_data || {};
        updateProjectData('carbon_emission_data', {
            ...prev,
            social_cost_data: {
                ...prev.social_cost_data,
                source: nextSource,
                mode: nextSource,
                ricke: nextRicke,
                custom: {
                    entered_value: parseNumber(nextCustom.entered_value),
                    currency,
                    unit: `${currency}/kgCO2e`,
                    source: nextCustom.source || '',
                    comments: nextCustom.comments || '',
                },
                result: {
                    selected_mode: nextSource,
                    cost_of_carbon_local: nextCost,
                    currency,
                    unit: `${currency}/kgCO2e`,
                },
                cost_of_carbon_local: nextCost,
                calculated_scc_local: nextCost,
                currency,
            },
        });
    };

    // Persistence is event-driven (every handler below saves explicitly) —
    // reactive persist effects are what looped the carbon page (PR #5).
    // The one exception: the Ricke cost also changes when the country data
    // finishes loading, with no user event to hook. This effect fires only
    // while a fully-resolved Ricke result differs from the stored cost, and
    // the normalizer echoes stored Ricke costs verbatim, so it converges in
    // one write. It never touches incomplete or legacy states.
    const savedCost = parseNumber(saved.result?.cost_of_carbon_local ?? saved.cost_of_carbon_local, 0);
    useEffect(() => {
        const resolved = source === SOURCE_RICKE && rickeResult.waiting?.length === 0 &&
            !rickeResult.loadingData && !rickeResult.noResult;
        if (resolved && Math.abs(currentCost - savedCost) > 1e-9) {
            saveData(source, ricke, custom, currentCost);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [currentCost, source]);

    const updateRicke = (field, value) => {
        const next = { ...ricke, [field]: value };
        setRicke(next);
        saveData(source, next, custom, computeRicke(next, next.iso3 === db.iso3 ? db.data : null, currency).cost);
    };

    const updateCustom = (field, value) => {
        const next = { ...custom, [field]: value };
        setCustom(next);
        saveData(source, ricke, next, parseNumber(next.entered_value));
    };

    const changeSource = (value) => {
        setSource(value);
        saveData(value, ricke, custom, value === SOURCE_RICKE ? rickeResult.cost : parseNumber(custom.entered_value));
    };

    const resetRicke = () => {
        if (!window.confirm('Clear all Social Cost of Carbon selections?')) return;
        const next = {
            iso3: countryLocked ? projectIso : 'WLD',
            ssp: '',
            rcp: '',
            dmg_func: '',
            dmg_params: '',
            climate_uncertainty: '',
            discounting: '',
            percentile: '',
            usd_to_local_rate: 0,
            cpi_ratio: 1,
        };
        setRicke(next);
        saveData(source, next, custom, 0);
    };

    const resetCustom = () => {
        if (!window.confirm('Clear all Social Cost of Carbon selections?')) return;
        const next = { entered_value: 0, source: '', comments: '' };
        setCustom(next);
        saveData(source, ricke, next, 0);
    };

    // Desktop `_apply_country_lock`: lock iso3 to the project country when
    // that country exists in the dataset; otherwise leave it editable.
    const countryLocked = countryList.length > 0
        ? countryList.includes(projectIso)
        : (projectIso && projectIso !== 'WLD');
    const countryOptions = countryList.length > 0
        ? countryList
        : [ricke.iso3].filter(Boolean);

    const usdRateZero = parseNumber(ricke.usd_to_local_rate, 0) < 0.0001;
    const cpiZero = parseNumber(ricke.cpi_ratio, 0) < 0.0001;

    const selectInput = ({ label, description, value, options, onChange, disabled = false }) => (
        <div className="carbon-field" key={label}>
            <label className="carbon-label">{label}<span className="carbon-required">*</span></label>
            {description && <div className="carbon-help">{description}</div>}
            <select
                className={`form-select form-select-sm ${!value ? 'border-danger' : ''}`}
                value={value}
                disabled={disabled}
                onChange={(event) => onChange(event.target.value)}
            >
                <option value="">-- select --</option>
                {options.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
        </div>
    );

    return (
        <div className="carbon-desktop-page">
            <div className="carbon-field">
                <label className="carbon-label">Mode</label>
                <select className="form-select form-select-sm" value={source} onChange={(event) => changeSource(event.target.value)}>
                    <option value={SOURCE_RICKE}>{SOURCE_RICKE}</option>
                    <option value={SOURCE_CUSTOM}>{SOURCE_CUSTOM}</option>
                </select>
            </div>

            {source === SOURCE_RICKE ? (
                <>
                    <div className="carbon-section">
                        <div className="carbon-section-title">Socioeconomic &amp; Climate Scenarios</div>
                        {selectInput({
                            label: 'Country (ISO3)',
                            description: "The country for which to calculate the social cost. 'WLD' represents the global aggregate.",
                            value: ricke.iso3,
                            options: countryOptions,
                            onChange: (value) => updateRicke('iso3', value),
                            disabled: countryLocked,
                        })}
                        {selectInput({
                            label: 'Socioeconomic Pathway (SSP)',
                            description: 'Assumptions on future population, GDP, and energy use.',
                            value: ricke.ssp,
                            options: SSP_OPTIONS,
                            onChange: (value) => updateRicke('ssp', value),
                        })}
                        {selectInput({
                            label: 'Climate Trajectory (RCP)',
                            description: "Representative Concentration Pathway. Choose 'Closest RCP' to use the paper's default pairing.",
                            value: ricke.rcp,
                            options: RCP_OPTIONS,
                            onChange: (value) => updateRicke('rcp', value),
                        })}
                    </div>

                    <div className="carbon-section">
                        <div className="carbon-section-title">Damage Function &amp; Model Parameters</div>
                        {selectInput({
                            label: 'Damage Function',
                            description: 'The empirical model used to relate temperature change to economic damage.',
                            value: ricke.dmg_func,
                            options: DAMAGE_FUNCTION_OPTIONS,
                            onChange: (value) => updateRicke('dmg_func', value),
                        })}
                        {selectInput({
                            label: 'Damage Parameters',
                            description: 'Whether to use bootstrapped uncertainty or central parameter estimates.',
                            value: ricke.dmg_params,
                            options: DAMAGE_PARAMETER_OPTIONS,
                            onChange: (value) => updateRicke('dmg_params', value),
                        })}
                        {selectInput({
                            label: 'Climate Uncertainty',
                            description: 'Whether to use expected climate projections or bootstrapped uncertainty.',
                            value: ricke.climate_uncertainty,
                            options: CLIMATE_OPTIONS,
                            onChange: (value) => updateRicke('climate_uncertainty', value),
                        })}
                    </div>

                    <div className="carbon-section">
                        <div className="carbon-section-title">Discounting &amp; Valuation</div>
                        {selectInput({
                            label: 'Discounting Approach',
                            description: 'The method for calculating the present value of future damages (Pure Rate of Time Preference and Elasticity of Marginal Utility).',
                            value: ricke.discounting,
                            options: DISCOUNT_OPTIONS,
                            onChange: (value) => updateRicke('discounting', value),
                        })}
                        {selectInput({
                            label: 'Percentile',
                            description: 'The statistical percentile of the SCC distribution to use.',
                            value: ricke.percentile,
                            options: PERCENTILE_OPTIONS,
                            onChange: (value) => updateRicke('percentile', value),
                        })}
                    </div>

                    <div className="carbon-section">
                        <div className="carbon-section-title">Currency Adjustment</div>
                        <div className="carbon-field">
                            <label className="carbon-label">USD Conversion Rate</label>
                            <div className="carbon-help">Conversion rate for international scientific model outputs (base is USD 2015).</div>
                            <div className="input-group input-group-sm">
                                <input className="form-control" type="number" min="0" step="any" value={ricke.usd_to_local_rate} onChange={(event) => updateRicke('usd_to_local_rate', event.target.value)} />
                                <span className="input-group-text">{currency}/USD</span>
                            </div>
                            {usdRateZero && (
                                <div className="text-warning small mt-1">
                                    USD to Local Currency Conversion Rate is 0 - the Ricke et al. social cost of
                                    carbon will result in 0 in the local currency; enter the current USD-to-local
                                    exchange rate
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="carbon-section">
                        <div className="carbon-section-title">Inflation Adjustment (CPI)</div>
                        <div className="carbon-field">
                            <label className="carbon-label">CPI Ratio (Reference-Year CPI / 2018 CPI)</label>
                            <div className="carbon-help">
                                The Ricke et al. paper was published in 2018. Apply a CPI ratio (current year
                                CPI ÷ 2018 CPI) to adjust the output for inflation. Set to 1.0 to use the
                                original 2018 values.
                            </div>
                            <input className="form-control form-control-sm" type="number" min="0" step="any" value={ricke.cpi_ratio} onChange={(event) => updateRicke('cpi_ratio', event.target.value)} />
                            {cpiZero && (
                                <div className="text-warning small mt-1">
                                    CPI Ratio is 0 - no inflation adjustment will be applied to the SCC value
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="carbon-summary-strip mt-3" data-testid="ricke-result">
                        {rickeResult.noResult ? (
                            <div className="fw-bold text-danger">No Result</div>
                        ) : (
                            <div className="fw-bold">Social Cost of Carbon: {formatNumber(currentCost, 6)} {currency}/kgCO2e</div>
                        )}
                        {rickeResult.sccText && <div className="mt-1" style={{ whiteSpace: 'pre-line' }}>{rickeResult.sccText}</div>}
                        {rickeResult.ciText && <div className="text-secondary small mt-1" style={{ whiteSpace: 'pre-line' }}>{rickeResult.ciText}</div>}
                        {rickeResult.summary && <div className="text-secondary small mt-1" style={{ whiteSpace: 'pre-line' }}>{rickeResult.summary}</div>}
                        {rickeResult.breakdown && <div className="text-secondary small mt-1" style={{ whiteSpace: 'pre-line' }}>{rickeResult.breakdown}</div>}
                        <div className="text-secondary small mt-1">
                            {dbError
                                || (rickeResult.waiting?.length > 0 && `Waiting for: ${rickeResult.waiting.join(', ')}`)
                                || (rickeResult.loadingData && (dbLoading ? 'Loading country data…' : 'Country data not loaded.'))
                                || (rickeResult.noResult ?? '')}
                        </div>
                        <div className="small mt-2">
                            <a href="https://country-level-scc.github.io/explorer/" target="_blank" rel="noreferrer">
                                Country-level SCC Explorer
                            </a>
                        </div>
                    </div>
                    <button className="btn btn-sm btn-outline-light mt-3 w-100" onClick={resetRicke}>Clear All</button>
                </>
            ) : (
                <>
                    {saved.mode === 'NITI Aayog' && (
                        <div className="alert alert-warning py-2" style={{ fontSize: '0.82rem' }}>
                            Legacy NITI Aayog data was found. Desktop Carbon Emissions uses Ricke or Custom
                            mode, so the numeric value has been preserved below.
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
                </>
            )}
        </div>
    );
};

export default SocialCost;

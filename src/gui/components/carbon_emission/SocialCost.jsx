/* eslint-disable react-hooks/set-state-in-effect */
import { useEffect, useMemo, useState } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import { formatNumber, getProjectCountryIso3, parseNumber } from './carbonUtils';

const SOURCE_RICKE = 'K. Ricke et al. (Country-Level)';
const SOURCE_CUSTOM = 'Custom / Manual Override';

const SSP_OPTIONS = [
    'SSP1 (Sustainability)',
    'SSP2 (Middle of the Road)',
    'SSP3 (Regional Rivalry)',
    'SSP4 (Inequality)',
    'SSP5 (Fossil-fueled Development)',
];

const RCP_OPTIONS = [
    'Closest RCP (Default)',
    'RCP4.5 (≈ +2.5°C in 2100)',
    'RCP6.0 (≈ +3°C in 2100)',
    'RCP8.5 (≈ +4.5°C in 2100)',
];

const DAMAGE_FUNCTION_OPTIONS = [
    'BHM SR (Short Run)',
    'BHM RP SR (Rich/Poor Short Run)',
    'BHM LR (Long Run)',
    'BHM RP LR (Rich/Poor Long Run)',
];

const DAMAGE_PARAMETER_OPTIONS = [
    'Bootstrap (Full Uncertainty)',
    'Estimates (Central Params)',
];

const CLIMATE_OPTIONS = [
    'Expected (Central Projections)',
    'Uncertain (Bootstrapped)',
];

const DISCOUNT_OPTIONS = [
    'Growth-adjusted (prtp=2%, η=1.5)',
    'Growth-adjusted (prtp=1%, η=1.5)',
    'Growth-adjusted (prtp=2%, η=0.7)',
    'Growth-adjusted (prtp=1%, η=0.7)',
    'Fixed 3%',
    'Fixed 5%',
];

const PERCENTILE_OPTIONS = [
    '16.7% (Optimistic)',
    '50.0% (Central)',
    '83.3% (Pessimistic)',
];

const SSP_MAP = {
    [SSP_OPTIONS[0]]: 'SSP1',
    [SSP_OPTIONS[1]]: 'SSP2',
    [SSP_OPTIONS[2]]: 'SSP3',
    [SSP_OPTIONS[3]]: 'SSP4',
    [SSP_OPTIONS[4]]: 'SSP5',
};

const CLOSEST_RCP = { SSP1: 'rcp60', SSP2: 'rcp60', SSP3: 'rcp85', SSP4: 'rcp60', SSP5: 'rcp85' };
const RCP_MAP = {
    [RCP_OPTIONS[0]]: null,
    [RCP_OPTIONS[1]]: 'rcp45',
    [RCP_OPTIONS[2]]: 'rcp60',
    [RCP_OPTIONS[3]]: 'rcp85',
};
const DAMAGE_FUNCTION_MAP = {
    [DAMAGE_FUNCTION_OPTIONS[0]]: 'bhm_sr',
    [DAMAGE_FUNCTION_OPTIONS[1]]: 'bhm_richpoor_sr',
    [DAMAGE_FUNCTION_OPTIONS[2]]: 'bhm_lr',
    [DAMAGE_FUNCTION_OPTIONS[3]]: 'bhm_richpoor_lr',
};
const DAMAGE_PARAMETER_MAP = {
    [DAMAGE_PARAMETER_OPTIONS[0]]: 'bootstrap',
    [DAMAGE_PARAMETER_OPTIONS[1]]: 'estimates',
};
const CLIMATE_MAP = {
    [CLIMATE_OPTIONS[0]]: 'expected',
    [CLIMATE_OPTIONS[1]]: 'uncertain',
};
const DISCOUNT_MAP = {
    [DISCOUNT_OPTIONS[0]]: { prtp: '2', eta: '1p5', dr: 'NA' },
    [DISCOUNT_OPTIONS[1]]: { prtp: '1', eta: '1p5', dr: 'NA' },
    [DISCOUNT_OPTIONS[2]]: { prtp: '2', eta: '0p7', dr: 'NA' },
    [DISCOUNT_OPTIONS[3]]: { prtp: '1', eta: '0p7', dr: 'NA' },
    [DISCOUNT_OPTIONS[4]]: { prtp: 'NA', eta: 'NA', dr: '3' },
    [DISCOUNT_OPTIONS[5]]: { prtp: 'NA', eta: 'NA', dr: '5' },
};
let rickeDbPromise;

const parseRickeCsv = (text) => {
    const lines = text.trim().split(/\r?\n/);
    const header = lines.shift().split(',');
    const index = Object.fromEntries(header.map((name, idx) => [name, idx]));
    const rows = new Map();
    const iso3 = new Set();
    for (const line of lines) {
        if (!line) continue;
        const cells = line.split(',');
        iso3.add(cells[index.ISO3]);
        const key = [
            cells[index.ISO3],
            cells[index.run],
            cells[index.dmgfuncpar],
            cells[index.climate],
            cells[index.SSP],
            cells[index.RCP],
            cells[index.prtp],
            cells[index.eta],
            cells[index.dr],
        ].join('|');
        rows.set(key, {
            lo: parseNumber(cells[index['16.7%']], null),
            med: parseNumber(cells[index['50%']], null),
            hi: parseNumber(cells[index['83.3%']], null),
        });
    }
    return { rows, iso3: Array.from(iso3).sort() };
};

const loadRickeDb = async () => {
    if (!rickeDbPromise) {
        rickeDbPromise = fetch('/data/cscc_db_v2.csv')
            .then((response) => {
                if (!response.ok) throw new Error(`Unable to load Ricke SCC database (${response.status})`);
                return response.text();
            })
            .then(parseRickeCsv);
    }
    return rickeDbPromise;
};

const selectValue = (data, key, fallback) => data?.[key] || fallback;

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

    const initialSource = saved.source === SOURCE_CUSTOM || saved.source === SOURCE_RICKE
        ? saved.source
        : (saved.mode === SOURCE_CUSTOM || saved.mode === 'custom' ? SOURCE_CUSTOM : SOURCE_RICKE);

    const [source, setSource] = useState(initialSource);
    const [ricke, setRicke] = useState({
        iso3: savedRicke.iso3 || projectIso,
        ssp: selectValue(savedRicke, 'ssp', SSP_OPTIONS[0]),
        rcp: selectValue(savedRicke, 'rcp', RCP_OPTIONS[0]),
        dmg_func: selectValue(savedRicke, 'dmg_func', ''),
        dmg_params: selectValue(savedRicke, 'dmg_params', ''),
        climate_uncertainty: selectValue(savedRicke, 'climate_uncertainty', ''),
        discounting: selectValue(savedRicke, 'discounting', ''),
        percentile: selectValue(savedRicke, 'percentile', ''),
        usd_to_local_rate: parseNumber(savedRicke.usd_to_local_rate ?? saved.usd_rate, 83),
        cpi_ratio: parseNumber(savedRicke.cpi_ratio, 1),
    });
    const [custom, setCustom] = useState({
        entered_value: parseNumber(savedCustom.entered_value ?? savedCustom.scc_value ?? legacyCost, 0),
        source: savedCustom.source || '',
        comments: savedCustom.comments || '',
    });
    const [dbState, setDbState] = useState({ loading: false, error: '', data: null });

    useEffect(() => {
        if (source !== SOURCE_RICKE) return;
        let active = true;
        setDbState((state) => ({ ...state, loading: true, error: '' }));
        loadRickeDb()
            .then((data) => {
                if (active) setDbState({ loading: false, error: '', data });
            })
            .catch((error) => {
                if (active) setDbState({ loading: false, error: error.message, data: null });
            });
        return () => {
            active = false;
        };
    }, [source]);

    useEffect(() => {
        setRicke((prev) => ({ ...prev, iso3: projectIso }));
    }, [projectIso]);

    const rickeResult = useMemo(() => {
        const required = [
            ['Country (ISO3)', ricke.iso3],
            ['Socioeconomic Pathway (SSP)', ricke.ssp],
            ['Climate Trajectory (RCP)', ricke.rcp],
            ['Damage Function', ricke.dmg_func],
            ['Damage Parameters', ricke.dmg_params],
            ['Climate Uncertainty', ricke.climate_uncertainty],
            ['Discounting Approach', ricke.discounting],
            ['Percentile', ricke.percentile],
        ];
        const missing = required.filter(([, value]) => !value).map(([label]) => label);
        if (missing.length > 0) {
            return { cost: 0, status: `Select ${missing.join(', ')} to calculate the Ricke SCC.` };
        }
        if (!dbState.data) return { cost: 0, status: dbState.loading ? 'Loading Ricke SCC database...' : 'Ricke SCC database not loaded yet.' };
        const ssp = SSP_MAP[ricke.ssp];
        const rcpRaw = RCP_MAP[ricke.rcp];
        const rcp = rcpRaw || CLOSEST_RCP[ssp];
        const discount = DISCOUNT_MAP[ricke.discounting];
        if (!ssp || !discount) return { cost: 0, status: 'Select all Ricke parameters to calculate the SCC.' };
        const key = [
            ricke.iso3,
            DAMAGE_FUNCTION_MAP[ricke.dmg_func],
            DAMAGE_PARAMETER_MAP[ricke.dmg_params],
            CLIMATE_MAP[ricke.climate_uncertainty],
            ssp,
            rcp,
            discount.prtp,
            discount.eta,
            discount.dr,
        ].join('|');
        const row = dbState.data.rows.get(key);
        if (!row || row.lo === null || row.med === null || row.hi === null) {
            return { cost: 0, status: 'No data available for this combination in the DB.', key };
        }
        const raw = {
            [PERCENTILE_OPTIONS[0]]: row.lo,
            [PERCENTILE_OPTIONS[1]]: row.med,
            [PERCENTILE_OPTIONS[2]]: row.hi,
        }[ricke.percentile];
        const finalPerTonne = raw * parseNumber(ricke.cpi_ratio, 1) * parseNumber(ricke.usd_to_local_rate, 1);
        return {
            cost: finalPerTonne / 1000,
            status: `Raw: ${formatNumber(raw, 3)} USD/tCO2 | Final: ${formatNumber(finalPerTonne, 3)} ${currency}/tCO2`,
            range: `${formatNumber(row.lo, 3)} - ${formatNumber(row.hi, 3)} USD/tCO2`,
            key,
        };
    }, [currency, dbState, ricke]);

    const currentCost = source === SOURCE_RICKE ? rickeResult.cost : parseNumber(custom.entered_value);

    const saveData = (nextSource = source, nextRicke = ricke, nextCustom = custom, nextCost = currentCost) => {
        const prev = projectData.carbon_emission_data || {};
        const result = {
            selected_mode: nextSource,
            cost_of_carbon_local: nextCost,
            currency,
            unit: `${currency}/kgCO2e`,
        };
        updateProjectData('carbon_emission_data', {
            ...prev,
            social_cost_data: {
                ...prev.social_cost_data,
                source: nextSource,
                ricke: nextRicke,
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

    useEffect(() => {
        saveData(source, ricke, custom, currentCost);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [source, ricke, custom, currentCost, currency]);

    const updateRicke = (field, value) => setRicke((prev) => ({ ...prev, [field]: value }));
    const updateCustom = (field, value) => setCustom((prev) => ({ ...prev, [field]: value }));

    const resetRicke = () => setRicke({
        iso3: projectIso,
        ssp: SSP_OPTIONS[0],
        rcp: RCP_OPTIONS[0],
        dmg_func: '',
        dmg_params: '',
        climate_uncertainty: '',
        discounting: '',
        percentile: '',
        usd_to_local_rate: 83,
        cpi_ratio: 1,
    });

    const resetCustom = () => setCustom({ entered_value: 0, source: '', comments: '' });

    const selectInput = ({ label, description, value, options, onChange, disabled = false, required = false }) => (
        <div className="carbon-field" key={label}>
            <label className="carbon-label">
                {label}{required && <span className="carbon-required">*</span>}
            </label>
            {description && <div className="carbon-help">{description}</div>}
            <select
                className={`form-select form-select-sm ${required && !value ? 'border-danger' : ''}`}
                value={value}
                disabled={disabled}
                onChange={(event) => onChange(event.target.value)}
            >
                {required && <option value="">-- select --</option>}
                {options.map((option) => <option key={option} value={option}>{option}</option>)}
            </select>
        </div>
    );

    return (
        <div className="carbon-desktop-page">
            <div className="carbon-field">
                <label className="carbon-label">Mode</label>
                <select
                    className="form-select form-select-sm"
                    value={source}
                    onChange={(event) => setSource(event.target.value)}
                >
                    <option value={SOURCE_RICKE}>{SOURCE_RICKE}</option>
                    <option value={SOURCE_CUSTOM}>{SOURCE_CUSTOM}</option>
                </select>
            </div>

            {saved.mode === 'NITI Aayog' && (
                <div className="alert alert-warning py-2" style={{ fontSize: '0.82rem' }}>
                    Legacy NITI Aayog data was found. Desktop Carbon Emissions uses Ricke or Custom mode, so the numeric value has been preserved under Custom.
                </div>
            )}

            {source === SOURCE_RICKE ? (
                <>
                    <div className="carbon-section">
                        <div className="carbon-section-title">Socioeconomic & Climate Scenarios</div>
                        {selectInput({
                            label: 'Country (ISO3)',
                            description: "The country for which to calculate the social cost. 'WLD' represents the global aggregate.",
                            value: ricke.iso3,
                            options: [ricke.iso3, ...(dbState.data?.iso3 || []).filter((iso) => iso !== ricke.iso3)],
                            onChange: (value) => updateRicke('iso3', value),
                            disabled: projectIso !== 'WLD',
                            required: true,
                        })}
                        {selectInput({
                            label: 'Socioeconomic Pathway (SSP)',
                            description: 'Assumptions on future population, GDP, and energy use.',
                            value: ricke.ssp,
                            options: SSP_OPTIONS,
                            onChange: (value) => updateRicke('ssp', value),
                            required: true,
                        })}
                        {selectInput({
                            label: 'Climate Trajectory (RCP)',
                            description: "Representative Concentration Pathway. Choose 'Closest RCP' to use the paper's default pairing.",
                            value: ricke.rcp,
                            options: RCP_OPTIONS,
                            onChange: (value) => updateRicke('rcp', value),
                            required: true,
                        })}
                    </div>

                    <div className="carbon-section">
                        <div className="carbon-section-title">Damage Function & Model Parameters</div>
                        {selectInput({
                            label: 'Damage Function',
                            description: 'The empirical model used to relate temperature change to economic damage.',
                            value: ricke.dmg_func,
                            options: DAMAGE_FUNCTION_OPTIONS,
                            onChange: (value) => updateRicke('dmg_func', value),
                            required: true,
                        })}
                        {selectInput({
                            label: 'Damage Parameters',
                            description: 'Choose whether the full uncertainty distribution or central parameter estimates are used.',
                            value: ricke.dmg_params,
                            options: DAMAGE_PARAMETER_OPTIONS,
                            onChange: (value) => updateRicke('dmg_params', value),
                            required: true,
                        })}
                        {selectInput({
                            label: 'Climate Uncertainty',
                            description: 'Climate projection uncertainty treatment.',
                            value: ricke.climate_uncertainty,
                            options: CLIMATE_OPTIONS,
                            onChange: (value) => updateRicke('climate_uncertainty', value),
                            required: true,
                        })}
                    </div>

                    <div className="carbon-section">
                        <div className="carbon-section-title">Discounting & Valuation</div>
                        {selectInput({
                            label: 'Discounting Approach',
                            description: 'Discounting specification used for future climate damages.',
                            value: ricke.discounting,
                            options: DISCOUNT_OPTIONS,
                            onChange: (value) => updateRicke('discounting', value),
                            required: true,
                        })}
                        {selectInput({
                            label: 'Percentile',
                            description: 'Select optimistic, central, or pessimistic estimate from the uncertainty interval.',
                            value: ricke.percentile,
                            options: PERCENTILE_OPTIONS,
                            onChange: (value) => updateRicke('percentile', value),
                            required: true,
                        })}
                    </div>

                    <div className="carbon-section">
                        <div className="carbon-section-title">Currency Adjustment</div>
                        <div className="carbon-field">
                            <label className="carbon-label">USD Conversion Rate</label>
                            <div className="carbon-help">Conversion rate from USD to the project currency.</div>
                            <div className="input-group input-group-sm">
                                <input className="form-control" type="number" value={ricke.usd_to_local_rate} onChange={(event) => updateRicke('usd_to_local_rate', event.target.value)} />
                                <span className="input-group-text">{currency}/USD</span>
                            </div>
                        </div>
                    </div>

                    <div className="carbon-section">
                        <div className="carbon-section-title">Inflation Adjustment (CPI)</div>
                        <div className="carbon-field">
                            <label className="carbon-label">CPI Ratio (Reference-Year CPI / 2018 CPI)</label>
                            <div className="carbon-help">Use 1 when no CPI adjustment is required.</div>
                            <input className="form-control form-control-sm" type="number" value={ricke.cpi_ratio} onChange={(event) => updateRicke('cpi_ratio', event.target.value)} />
                        </div>
                    </div>

                    <div className="carbon-summary-strip mt-3">
                        <div className="fw-bold">Social Cost of Carbon: {formatNumber(currentCost, 6)} {currency}/kgCO2e</div>
                        <div className="text-secondary small mt-1">{dbState.error || rickeResult.status}</div>
                        {rickeResult.range && <div className="text-secondary small">66.7% Confidence Interval: {rickeResult.range}</div>}
                    </div>
                    <button className="btn btn-sm btn-outline-light mt-3 w-100" onClick={resetRicke}>Clear All</button>
                </>
            ) : (
                <>
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

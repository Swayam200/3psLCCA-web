/**
 * Pure Ricke et al. social-cost-of-carbon computation, shared by the
 * Social Cost page (interactive) and the calculation-time resolver
 * (desktop parity: the desktop engine resolves the SCC live from the
 * saved Ricke parameters at calculation time — the persisted chunk value
 * is only a cache and may lag or hold 0).
 *
 * Option labels and code maps mirror desktop scc_tabs/ricke.py verbatim.
 */
import { formatNumber, parseNumber } from './carbonUtils.js';
import { CLOSEST_RCP, lookupScc } from '../../../lib/cscc.js';

// Desktop scc_widget.py `_SELECTOR_LABELS`
export const SOURCE_RICKE = 'K. Ricke et al. (Country-Level)';
export const SOURCE_CUSTOM = 'Custom / Manual Override';

export const SSP_OPTIONS = [
    'SSP1 (Sustainability)',
    'SSP2 (Middle of the Road)',
    'SSP3 (Regional Rivalry)',
    'SSP4 (Inequality)',
    'SSP5 (Fossil-fueled Development)',
];

export const RCP_OPTIONS = [
    'Closest RCP (Default)',
    'RCP4.5 (≈ +2.5°C in 2100)',
    'RCP6.0 (≈ +3°C in 2100)',
    'RCP8.5 (≈ +4.5°C in 2100)',
];

export const DAMAGE_FUNCTION_OPTIONS = [
    'BHM SR (Short Run)',
    'BHM RP SR (Rich/Poor Short Run)',
    'BHM LR (Long Run)',
    'BHM RP LR (Rich/Poor Long Run)',
];

export const DAMAGE_PARAMETER_OPTIONS = [
    'Bootstrap (Full Uncertainty)',
    'Estimates (Central Params)',
];

export const CLIMATE_OPTIONS = [
    'Expected (Central Projections)',
    'Uncertain (Bootstrapped)',
];

export const DISCOUNT_OPTIONS = [
    'Growth-adjusted (prtp=2%, η=1.5)',
    'Growth-adjusted (prtp=1%, η=1.5)',
    'Growth-adjusted (prtp=2%, η=0.7)',
    'Growth-adjusted (prtp=1%, η=0.7)',
    'Fixed 3%',
    'Fixed 5%',
];

export const PERCENTILE_OPTIONS = [
    '16.7% (Optimistic)',
    '50.0% (Central)',
    '83.3% (Pessimistic)',
];

export const SSP_MAP = {
    [SSP_OPTIONS[0]]: 'SSP1',
    [SSP_OPTIONS[1]]: 'SSP2',
    [SSP_OPTIONS[2]]: 'SSP3',
    [SSP_OPTIONS[3]]: 'SSP4',
    [SSP_OPTIONS[4]]: 'SSP5',
};
export const RCP_MAP = {
    [RCP_OPTIONS[0]]: null,
    [RCP_OPTIONS[1]]: 'rcp45',
    [RCP_OPTIONS[2]]: 'rcp60',
    [RCP_OPTIONS[3]]: 'rcp85',
};
export const DAMAGE_FUNCTION_MAP = {
    [DAMAGE_FUNCTION_OPTIONS[0]]: 'bhm_sr',
    [DAMAGE_FUNCTION_OPTIONS[1]]: 'bhm_richpoor_sr',
    [DAMAGE_FUNCTION_OPTIONS[2]]: 'bhm_lr',
    [DAMAGE_FUNCTION_OPTIONS[3]]: 'bhm_richpoor_lr',
};
export const DAMAGE_PARAMETER_MAP = {
    [DAMAGE_PARAMETER_OPTIONS[0]]: 'bootstrap',
    [DAMAGE_PARAMETER_OPTIONS[1]]: 'estimates',
};
export const CLIMATE_MAP = {
    [CLIMATE_OPTIONS[0]]: 'expected',
    [CLIMATE_OPTIONS[1]]: 'uncertain',
};
export const DISCOUNT_MAP = {
    [DISCOUNT_OPTIONS[0]]: { prtp: '2', eta: '1p5', dr: 'NA' },
    [DISCOUNT_OPTIONS[1]]: { prtp: '1', eta: '1p5', dr: 'NA' },
    [DISCOUNT_OPTIONS[2]]: { prtp: '2', eta: '0p7', dr: 'NA' },
    [DISCOUNT_OPTIONS[3]]: { prtp: '1', eta: '0p7', dr: 'NA' },
    [DISCOUNT_OPTIONS[4]]: { prtp: 'NA', eta: 'NA', dr: '3' },
    [DISCOUNT_OPTIONS[5]]: { prtp: 'NA', eta: 'NA', dr: '5' },
};
export const PERCENTILE_INDEX = {
    [PERCENTILE_OPTIONS[0]]: 0,
    [PERCENTILE_OPTIONS[1]]: 1,
    [PERCENTILE_OPTIONS[2]]: 2,
};

export const REQUIRED_FIELDS = [
    ['Country', 'iso3'],
    ['SSP', 'ssp'],
    ['RCP', 'rcp'],
    ['Damage Function', 'dmg_func'],
    ['Damage Parameters', 'dmg_params'],
    ['Climate Uncertainty', 'climate_uncertainty'],
    ['Discounting', 'discounting'],
    ['Percentile', 'percentile'],
];

export const DP = 2; // desktop display_format.DECIMAL_PLACES

/**
 * Pure mirror of desktop ricke.py `_print_ricke_cost` + `get_cost`.
 * Returns everything the UI and the persisted result need:
 * waiting list, error reason, display strings, and the final
 * currency/kgCO2e cost (per-tCO2 value ÷ 1000, like desktop).
 */
export const computeRicke = (ricke, countryData, currency) => {
    const waiting = REQUIRED_FIELDS.filter(([, key]) => !ricke[key]).map(([label]) => label);
    if (waiting.length > 0) return { cost: 0, waiting };

    const ssp = SSP_MAP[ricke.ssp];
    const rcpRaw = RCP_MAP[ricke.rcp] ?? null;
    const rcp = rcpRaw !== null ? rcpRaw : CLOSEST_RCP[ssp];
    const params = {
        run: DAMAGE_FUNCTION_MAP[ricke.dmg_func],
        dmgfuncpar: DAMAGE_PARAMETER_MAP[ricke.dmg_params],
        climate: CLIMATE_MAP[ricke.climate_uncertainty],
        ssp,
        rcp,
        ...DISCOUNT_MAP[ricke.discounting],
    };
    const pctIdx = PERCENTILE_INDEX[ricke.percentile];

    const rcpDisplay = rcpRaw !== null ? ricke.rcp : `${ricke.rcp} → ${rcp}`;
    const summary = `Country: ${ricke.iso3}   ·   SSP: ${ricke.ssp}   ·   RCP: ${rcpDisplay}\n` +
        `Damage Function: ${ricke.dmg_func}   ·   Parameters: ${ricke.dmg_params}   ·   Climate: ${ricke.climate_uncertainty}\n` +
        `Discounting: ${ricke.discounting}   ·   Percentile: ${ricke.percentile}`;

    if (!countryData) return { cost: 0, waiting: [], summary, loadingData: true };

    const { values, reason } = lookupScc(countryData, params);
    if (reason !== 'ok') {
        return {
            cost: 0,
            waiting: [],
            summary,
            noResult: reason === 'na'
                ? 'No data available for this combination in the DB - please change one or more selections above.'
                : 'This combination was not found in the DB - please change one or more selections above.',
        };
    }

    const [lo, , hi] = values;
    const displayed = values[pctIdx];
    const cpiRatio = parseNumber(ricke.cpi_ratio, 1);
    const usdToLocal = parseNumber(ricke.usd_to_local_rate, 0);
    const afterCpi = displayed * cpiRatio;
    const final = afterCpi * usdToLocal;
    const adjLo = lo * cpiRatio * usdToLocal;
    const adjHi = hi * cpiRatio * usdToLocal;
    const cpiApplied = Math.abs(cpiRatio - 1.0) > 1e-6;

    return {
        cost: final / 1000, // USD/tCO2-derived value → currency/kgCO2e
        waiting: [],
        summary,
        sccText: cpiApplied
            ? `${formatNumber(final, DP)} ${currency} / tCO₂   (CPI-adjusted from ${formatNumber(displayed, DP)} in 2018 USD)`
            : `${formatNumber(final, DP)} ${currency} / tCO₂   (2018 USD)`,
        ciText: cpiApplied
            ? `66.7% Confidence Interval:  ${formatNumber(adjLo, DP)}  –  ${formatNumber(adjHi, DP)} ${currency} / tCO₂  (adjusted)\n` +
            `${formatNumber(lo, DP)}  –  ${formatNumber(hi, DP)} USD / tCO₂  (2018 USD)`
            : `66.7% Confidence Interval:  ${formatNumber(lo, DP)}  –  ${formatNumber(hi, DP)} ${currency} / tCO₂`,
        breakdown: `① Raw (2018 USD):  ${formatNumber(displayed, DP)} USD/tCO₂\n` +
            `② After CPI (× ${cpiRatio}):  ${formatNumber(afterCpi, DP)} USD/tCO₂\n` +
            `③ Final (× ${usdToLocal} ${currency}/USD):  ${formatNumber(final, DP)} ${currency}/tCO₂`,
    };
};

/**
 * Web project → desktop-shaped chunks for the LaTeX report engine.
 *
 * The report runtime (vendor/report-runtime) is desktop's own Python and
 * reads project data through desktop chunk names/shapes. This module is the
 * single translation point from the web app's project state to that
 * contract — the one piece of report code that is ours to keep in sync,
 * guarded by the golden round-trip test (npm run test:report).
 *
 * Shape sources: desktop common_requested_data._ALL_CHUNKS, the fixture
 * tests/fixtures/m20-desktop-chunks.json, and the field reads in
 * code_to_latex/* (see docs/report-latex-web-plan.md).
 */

const asArray = (value) => (Array.isArray(value) ? value : []);
const asObject = (value) => (value && typeof value === 'object' && !Array.isArray(value) ? value : {});

const numberOr = (value, fallback) => {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
};

/**
 * Web construction row (flat) → desktop row ({id, values, meta, state}).
 *
 * Imported projects carry the original desktop `values`/`meta` verbatim
 * (projectImport preserves them); the flat fields are the web-editable
 * view derived from them. For each field: if the flat value still equals
 * what import derived from `values`, the user didn't touch it — emit the
 * original verbatim (keeps null vs '' and any extra keys byte-stable).
 * Only a genuine web edit overrides.
 */
const desktopRow = (row) => {
    const prior = asObject(row.values);
    const hasPrior = row.values !== undefined;
    const emission = asObject(row.carbonEmission);

    // (flat value, import-derivation from prior, desktop key) per field.
    const pick = (flat, derived, priorValue, fallback) => {
        if (hasPrior) return flat === derived ? priorValue : flat;
        return flat !== undefined ? flat : fallback;
    };

    const values = {
        ...prior,
        material_name: pick(row.workName, prior.material_name ?? '', prior.material_name, row.workName ?? ''),
        quantity: pick(row.qty, prior.quantity !== undefined ? prior.quantity : 0, prior.quantity, numberOr(row.qty, 0)),
        unit: pick(row.unit, prior.unit ?? '', prior.unit, row.unit ?? ''),
        rate: pick(row.rate, prior.rate !== undefined ? prior.rate : 0, prior.rate, numberOr(row.rate, 0)),
        rate_source: pick(row.source, prior.rate_source ?? '', prior.rate_source, row.source ?? ''),
        conversion_factor: pick(
            row.conversionFactor,
            prior.conversion_factor !== undefined ? prior.conversion_factor : 1,
            prior.conversion_factor,
            numberOr(row.conversionFactor, 1),
        ),
        carbon_emission: pick(
            emission.factor,
            prior.carbon_emission !== undefined ? prior.carbon_emission : 0,
            prior.carbon_emission,
            numberOr(emission.factor, 0),
        ),
        carbon_unit: emission.perUnit ?? prior.carbon_unit ?? '',
        scrap_rate: pick(
            row.scrapRate,
            prior.scrap_rate !== undefined ? prior.scrap_rate : 0,
            prior.scrap_rate,
            numberOr(row.scrapRate, 0),
        ),
        post_demolition_recovery_percentage: pick(
            row.postDemolitionRecoveryPercentage,
            prior.post_demolition_recovery_percentage !== undefined ? prior.post_demolition_recovery_percentage : 0,
            prior.post_demolition_recovery_percentage,
            numberOr(row.postDemolitionRecoveryPercentage, 0),
        ),
    };

    return {
        id: row.id,
        values,
        meta: asObject(row.meta ?? { source: 'db' }),
        state: asObject(row.state ?? { in_trash: false }),
    };
};

/** Web array-of-sections → desktop {"Section Name": [rows]} chunk. */
const desktopStructureChunk = (sections) => {
    const chunk = {};
    asArray(sections).forEach((section, index) => {
        const name = section?.name || `Section ${index + 1}`;
        chunk[name] = asArray(section?.rows).map(desktopRow);
    });
    return chunk;
};

const desktopDiversion = (diversion) => {
    const data = asObject(diversion);
    return {
        mode: data.mode || '',
        emission_factors: asObject(data.emission_factors || data.factors),
        total_calculated_emissions: numberOr(data.total_calculated_emissions, 0),
        total_direct_emissions: numberOr(
            data.direct_entry?.total_direct_emissions ?? data.total_direct_emissions,
            0,
        ),
        remarks: data.remarks || '',
    };
};

/**
 * Build the desktop-shaped chunk dict the report runtime consumes.
 *
 * `results` / `currency` come from the Outputs page (the same values the
 * jsPDF report already receives) and feed comparison_cache — the chunk the
 * results section and plots read. Without results the report still renders
 * every input section; results/plots are simply omitted (mirrors desktop
 * behavior when no calculation has been run).
 */
export const desktopChunksForReport = (projectData = {}, { results = null, currency = '' } = {}) => {
    const carbon = asObject(projectData.carbon_emission_data);
    const generalInfo = asObject(projectData.general_info);
    const resolvedCurrency = currency || generalInfo.project_currency || projectData.currency || 'INR';

    return {
        general_info: generalInfo,
        bridge_data: asObject(projectData.bridge_data),
        financial_data: asObject(projectData.financial_data),
        traffic_and_road_data: asObject(projectData.traffic_data),
        maintenance_data: asObject(projectData.maintenance_repair_data),
        demolition_data: asObject(projectData.demolition_data),
        recycling_data: asObject(projectData.recycling_data),

        str_foundation: desktopStructureChunk(projectData.foundation_data),
        str_sub_structure: desktopStructureChunk(projectData.substructure_data),
        str_super_structure: desktopStructureChunk(projectData.superstructure_data),
        str_misc: desktopStructureChunk(projectData.miscellaneous_data),

        transport_data: {
            vehicles: [
                asArray(carbon.transport_emissions_data?.vehicles),
                asArray(carbon.transport_emissions_data?.raw_ui_entries),
                asArray(projectData.transport_data?.vehicles),
            ].find((list) => list.length > 0) || [],
        },
        machinery_emissions_data: asObject(carbon.machinery_emissions_data),
        social_cost_data: asObject(carbon.social_cost_data),
        material_emissions_data: asObject(carbon.material_emissions_data),
        diversion_emissions: desktopDiversion(carbon.diversion_emissions_data),

        comparison_cache: {
            is_valid: Boolean(results),
            analysis_period: numberOr(projectData.bridge_data?.analysis_period, 0),
            currency: resolvedCurrency,
            results: asObject(results),
        },
    };
};

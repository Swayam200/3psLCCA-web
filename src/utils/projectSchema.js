import { normalizeProjectSection } from './projectPageSchema.js';

export const PROJECT_SCHEMA_VERSION = 1;

export const CANONICAL_SECTION_KEYS = [
    'general_info',
    'bridge_data',
    'financial_data',
    'traffic_data',
    'transport_data',
    'foundation_data',
    'substructure_data',
    'superstructure_data',
    'miscellaneous_data',
    'carbon_emission_data',
    'maintenance_repair_data',
    'recycling_data',
    'demolition_data',
    'outputs_data',
];

const DEFAULT_PROJECT_META = {
    name: 'Bridge_Assessment_01',
    country: 'INDIA',
    currency: 'INR',
    unitSystem: 'Metric (SI)',
};

const EMPTY_OBJECT_SECTION_KEYS = [
    'bridge_data',
    'financial_data',
    'traffic_data',
    'transport_data',
    'carbon_emission_data',
    'maintenance_repair_data',
    'recycling_data',
    'demolition_data',
    'outputs_data',
];

const CONSTRUCTION_LEGACY_KEYS = {
    foundation_data: ['foundation_data', 'Foundation', 'foundation', 'str_foundation'],
    substructure_data: ['substructure_data', 'Sub Structure', 'SubStructure', 'sub_structure', 'str_sub_structure'],
    superstructure_data: ['superstructure_data', 'Super Structure', 'SuperStructure', 'super_structure', 'str_super_structure'],
    miscellaneous_data: ['miscellaneous_data', 'Miscellaneous', 'Misc', 'miscellaneous', 'str_misc'],
};

const isPlainObject = (value) => (
    value !== null &&
    typeof value === 'object' &&
    !Array.isArray(value)
);

const asObject = (value) => (isPlainObject(value) ? value : {});

const asArray = (value) => (Array.isArray(value) ? value : []);

const firstArrayValue = (project, legacyConstruction, keys) => {
    for (const key of keys) {
        const candidate = project?.[key] ?? legacyConstruction?.[key];
        if (Array.isArray(candidate)) return candidate;
        if (Array.isArray(candidate?.rows)) return [candidate];
        if (Array.isArray(candidate?.materials)) return candidate.materials;
        if (Array.isArray(candidate?.data)) return candidate.data;
    }
    return [];
};

export function createDefaultProject(overrides = {}) {
    const name = overrides.name || DEFAULT_PROJECT_META.name;
    const country = overrides.country || DEFAULT_PROJECT_META.country;
    const currency = overrides.currency || DEFAULT_PROJECT_META.currency;
    const unitSystem = overrides.unitSystem || DEFAULT_PROJECT_META.unitSystem;

    return {
        schema_version: PROJECT_SCHEMA_VERSION,
        name,
        country,
        currency,
        unitSystem,
        createdAt: overrides.createdAt || new Date().toISOString(),
        general_info: {
            project_name: name,
            project_country: country,
            project_currency: currency,
            unit_system: unitSystem,
            ...(overrides.general_info || {}),
        },
        bridge_data: {},
        financial_data: {},
        traffic_data: {},
        transport_data: {},
        foundation_data: [],
        substructure_data: [],
        superstructure_data: [],
        miscellaneous_data: [],
        carbon_emission_data: {},
        maintenance_repair_data: {},
        recycling_data: {},
        demolition_data: {},
        outputs_data: {},
    };
}

export function normalizeProjectData(project) {
    if (!project) return createDefaultProject();

    const source = isPlainObject(project) ? project : {};
    const normalized = {
        ...source,
        schema_version: Number(source.schema_version) || PROJECT_SCHEMA_VERSION,
    };

    const legacyMaintenance = asObject(source.maintenance_data);
    if (!isPlainObject(normalized.maintenance_repair_data) || Object.keys(normalized.maintenance_repair_data).length === 0) {
        normalized.maintenance_repair_data = legacyMaintenance;
    } else {
        normalized.maintenance_repair_data = asObject(normalized.maintenance_repair_data);
    }

    for (const key of EMPTY_OBJECT_SECTION_KEYS) {
        normalized[key] = asObject(normalized[key]);
    }

    const legacyConstruction = asObject(source.construction_work_data);
    for (const [canonicalKey, legacyKeys] of Object.entries(CONSTRUCTION_LEGACY_KEYS)) {
        normalized[canonicalKey] = asArray(normalized[canonicalKey]);
        if (normalized[canonicalKey].length === 0) {
            normalized[canonicalKey] = firstArrayValue(source, legacyConstruction, legacyKeys);
        }
    }

    const defaults = createDefaultProject(source);
    for (const key of CANONICAL_SECTION_KEYS) {
        if (normalized[key] === undefined) {
            normalized[key] = defaults[key];
        }
    }

    const generalInfo = asObject(normalized.general_info);
    normalized.name = normalized.name || generalInfo.project_name || defaults.name;
    normalized.country = normalized.country || generalInfo.project_country || defaults.country;
    normalized.currency = normalized.currency || generalInfo.project_currency || defaults.currency;
    normalized.unitSystem = normalized.unitSystem || generalInfo.unit_system || defaults.unitSystem;
    normalized.createdAt = normalized.createdAt || defaults.createdAt;

    normalized.general_info = {
        ...generalInfo,
        project_name: generalInfo.project_name || normalized.name,
        project_country: generalInfo.project_country || normalized.country,
        project_currency: generalInfo.project_currency || normalized.currency,
        unit_system: generalInfo.unit_system || normalized.unitSystem,
    };

    for (const key of CANONICAL_SECTION_KEYS) {
        normalized[key] = normalizeProjectSection(key, normalized[key], normalized);
    }

    // Keep older readers working while the web app migrates page-by-page.
    normalized.maintenance_data = {
        ...legacyMaintenance,
        ...normalized.maintenance_repair_data,
    };

    normalized.construction_work_data = {
        ...legacyConstruction,
        Foundation: { rows: normalized.foundation_data },
        'Sub Structure': { rows: normalized.substructure_data },
        'Super Structure': { rows: normalized.superstructure_data },
        Miscellaneous: { rows: normalized.miscellaneous_data },
    };

    return normalized;
}

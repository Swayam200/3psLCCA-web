import { normalizeProjectData } from './projectSchema.js';

/**
 * Maps project-creation form fields to general_info schema.
 */
export function mapCreationToGeneralInfo({ name, country, currency, unitSystem, sorDatabase }) {
    return {
        project_name: name || '',
        project_country: country || '',
        project_currency: currency || '',
        unit_system: unitSystem || '',
        // Optional at creation; settable/changeable later in General Information.
        sor_database: sorDatabase || '',
    };
}

/**
 * Backfills general_info from root-level creation fields for legacy projects.
 */
export function backfillGeneralInfo(project) {
    if (!project) return project;
    return normalizeProjectData(project);
}

/**
 * Builds a full project object from creation modal payload.
 */
export function buildProjectFromCreation(creationData) {
    const general_info = mapCreationToGeneralInfo(creationData);

    return normalizeProjectData({
        name: creationData.name,
        country: creationData.country,
        currency: creationData.currency,
        unitSystem: creationData.unitSystem,
        createdAt: creationData.createdAt || new Date().toISOString(),
        general_info,
    });
}

import JSZip from 'jszip';
import pako from 'pako';
import { normalizeProjectData } from './projectSchema.js';

const LCCA_MAGIC = [0x4C, 0x43, 0x43, 0x41]; // "LCCA"

/**
 * Decodes an LCCA binary chunk (decompressing using pako if the header is present)
 */
export function decodeLcca(uint8) {
    const isLcca = uint8[0] === LCCA_MAGIC[0] && uint8[1] === LCCA_MAGIC[1] && 
                   uint8[2] === LCCA_MAGIC[2] && uint8[3] === LCCA_MAGIC[3];
    
    if (isLcca) {
        const compressed = uint8.slice(4);
        const decompressed = pako.inflate(compressed);
        const text = new TextDecoder().decode(decompressed);
        return JSON.parse(text);
    } else {
        const text = new TextDecoder().decode(uint8);
        return JSON.parse(text);
    }
}

/**
 * Maps a single construction work row, converting nested values to flat fields.
 */
function mapConstructionRow(row, rowIndex, sectionId) {
    if (!row) return null;
    const values = row.values || {};
    return {
        id: row.id || `${sectionId}-row-${rowIndex + 1}`,
        workName: row.workName || values.material_name || row.material_name || '',
        qty: row.qty !== undefined ? row.qty : (values.quantity !== undefined ? values.quantity : 0),
        unit: row.unit || values.unit || '',
        rate: row.rate !== undefined ? row.rate : (values.rate !== undefined ? values.rate : 0),
        source: row.source || values.rate_source || '',
        conversionFactor: row.conversionFactor !== undefined ? row.conversionFactor : (values.conversion_factor !== undefined ? values.conversion_factor : 1),
        carbonEmission: {
            factor: row.carbonEmission?.factor !== undefined ? row.carbonEmission.factor : (values.carbon_emission !== undefined ? values.carbon_emission : 0)
        },
        scrapRate: row.scrapRate !== undefined ? row.scrapRate : (values.scrap_rate !== undefined ? values.scrap_rate : 0),
        postDemolitionRecoveryPercentage: row.postDemolitionRecoveryPercentage !== undefined ? row.postDemolitionRecoveryPercentage : (values.post_demolition_recovery_percentage !== undefined ? values.post_demolition_recovery_percentage : 0),
        state: row.state || { in_trash: false },
        // Preserve the source-of-truth desktop fields verbatim so exports and
        // the LaTeX report engine can reproduce them losslessly (the flat
        // fields above are the web-editable view).
        ...(row.values ? { values: row.values } : {}),
        ...(row.meta ? { meta: row.meta } : {})
    };
}

/**
 * Converts LCCA structural categories object (e.g. { "Excavation": [...] })
 * or array of sections to the web application's array-of-sections structure.
 */
function mapConstructionSection(data, prefix) {
    if (!data) return [];
    
    // If it is already an array of sections
    if (Array.isArray(data)) {
        return data.map((sec, idx) => {
            const secId = sec.id || `${prefix}-${idx + 1}`;
            return {
                ...sec,
                id: secId,
                name: sec.name || `Section ${idx + 1}`,
                rows: (sec.rows || []).map((row, rowIdx) => mapConstructionRow(row, rowIdx, secId)).filter(Boolean)
            };
        });
    }

    // If it is an object representing categories (keys are category names, values are array of rows or { rows: [...] })
    return Object.entries(data).map(([sectionName, sectionContent], idx) => {
        const secId = `${prefix}-${idx + 1}`;
        const rawRows = Array.isArray(sectionContent) ? sectionContent : (sectionContent.rows || []);
        return {
            id: secId,
            name: sectionName,
            rows: rawRows.map((row, rowIdx) => mapConstructionRow(row, rowIdx, secId)).filter(Boolean)
        };
    });
}

const CHUNK_MAPPINGS = {
    general_info: (project, data) => { project.general_info = data; },
    bridge_data: (project, data) => { project.bridge_data = data; },
    financial_data: (project, data) => { project.financial_data = data; },
    traffic_data: (project, data) => { project.traffic_data = data; },
    traffic_and_road_data: (project, data) => { project.traffic_data = data; },
    demolition_data: (project, data) => { project.demolition_data = data; },
    recycling_data: (project, data) => { project.recycling_data = data; },
    maintenance_data: (project, data) => { project.maintenance_repair_data = data; },
    maintenance_repair_data: (project, data) => { project.maintenance_repair_data = data; },
    outputs_data: (project, data) => { project.outputs_data = data; },
    
    // Construction work chunks mapped to Foundation, Super Structure, Sub Structure, Miscellaneous
    foundation: (project, data) => { project.foundation_data = mapConstructionSection(data, 'foundation'); },
    foundation_data: (project, data) => { project.foundation_data = mapConstructionSection(data, 'foundation'); },
    str_foundation: (project, data) => { project.foundation_data = mapConstructionSection(data, 'foundation'); },
    
    substructure: (project, data) => { project.substructure_data = mapConstructionSection(data, 'substructure'); },
    substructure_data: (project, data) => { project.substructure_data = mapConstructionSection(data, 'substructure'); },
    str_sub_structure: (project, data) => { project.substructure_data = mapConstructionSection(data, 'substructure'); },
    
    superstructure: (project, data) => { project.superstructure_data = mapConstructionSection(data, 'superstructure'); },
    superstructure_data: (project, data) => { project.superstructure_data = mapConstructionSection(data, 'superstructure'); },
    str_super_structure: (project, data) => { project.superstructure_data = mapConstructionSection(data, 'superstructure'); },
    
    miscellaneous: (project, data) => { project.miscellaneous_data = mapConstructionSection(data, 'miscellaneous'); },
    miscellaneous_data: (project, data) => { project.miscellaneous_data = mapConstructionSection(data, 'miscellaneous'); },
    str_misc: (project, data) => { project.miscellaneous_data = mapConstructionSection(data, 'miscellaneous'); },
    miscellaneous_construction_work: (project, data) => { project.miscellaneous_data = mapConstructionSection(data, 'miscellaneous'); },

    // Carbon emissions chunks
    carbon_emission_data: (project, data) => { project.carbon_emission_data = data; },
    material_emissions_data: (project, data) => {
        project.carbon_emission_data = project.carbon_emission_data || {};
        project.carbon_emission_data.material_emissions_data = data;
    },
    transportation_emissions_data: (project, data) => {
        project.carbon_emission_data = project.carbon_emission_data || {};
        project.carbon_emission_data.transportation_emissions_data = data;
        project.carbon_emission_data.transport_emissions_data = data;
    },
    transport_data: (project, data) => {
        project.carbon_emission_data = project.carbon_emission_data || {};
        project.carbon_emission_data.transportation_emissions_data = data;
        project.carbon_emission_data.transport_emissions_data = data;
    },
    machinery_emissions_data: (project, data) => {
        project.carbon_emission_data = project.carbon_emission_data || {};
        project.carbon_emission_data.machinery_emissions_data = data;
    },
    diversion_emissions: (project, data) => {
        project.carbon_emission_data = project.carbon_emission_data || {};
        project.carbon_emission_data.diversion_emissions_data = data;
    },
    social_cost_of_carbon: (project, data) => {
        project.carbon_emission_data = project.carbon_emission_data || {};
        project.carbon_emission_data.social_cost_data = data;
    },
    social_cost_data: (project, data) => {
        project.carbon_emission_data = project.carbon_emission_data || {};
        project.carbon_emission_data.social_cost_data = data;
    }
};

/**
 * Extracts, parses, maps, and normalizes a .3ps (ZIP) project file client-side.
 * Returns the fully normalized project object.
 */
export async function import3psFile(arrayBuffer) {
    let zip;
    try {
        zip = await JSZip.loadAsync(arrayBuffer);
    } catch (err) {
        throw new Error("Corrupted or invalid .3ps zip archive.");
    }

    const project = {};
    let manifest = null;

    // First pass: look for manifest.json
    if (zip.files["manifest.json"]) {
        try {
            const manifestText = await zip.files["manifest.json"].async("text");
            manifest = JSON.parse(manifestText);
        } catch (e) {
            console.warn("Failed to parse manifest.json", e);
        }
    }

    // Second pass: iterate through files and process chunks
    for (const [relativePath, file] of Object.entries(zip.files)) {
        if (file.dir) continue;

        if (relativePath.startsWith("chunks/")) {
            const chunkName = relativePath.split("/").pop().split(".")[0];
            const mapper = CHUNK_MAPPINGS[chunkName];
            
            if (mapper) {
                try {
                    const buffer = await file.async("uint8array");
                    const chunkContent = decodeLcca(buffer);
                    mapper(project, chunkContent);
                } catch (err) {
                    console.error(`Failed to parse chunk "${chunkName}":`, err);
                    throw new Error(`Parsing failure in chunk "${chunkName}": ${err.message}`);
                }
            } else {
                console.warn(`Unmapped chunk found in zip: ${chunkName}`);
            }
        }
    }

    // Verify minimum required sections exist (general_info or bridge_data)
    if (!project.general_info && !project.bridge_data) {
        throw new Error("Missing required sections: general info or bridge data.");
    }

    // Normalize project structure using existing logic
    const normalized = normalizeProjectData(project);

    // Populate metadata
    normalized.id = manifest?.project_id || `proj_${Date.now()}`;
    normalized.name = normalized.name || normalized.general_info?.project_name || manifest?.project_id || "Imported Project";

    return normalized;
}

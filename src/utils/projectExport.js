import JSZip from 'jszip';
import pako from 'pako';

const LCCA_MAGIC = [0x4C, 0x43, 0x43, 0x41]; // "LCCA"

/**
 * Encodes json data with LCCA magic header + zlib compression (using pako)
 */
export function encodeLcca(jsonData) {
    const jsonString = JSON.stringify(jsonData);
    const textBytes = new TextEncoder().encode(jsonString);
    const compressed = pako.deflate(textBytes);
    const output = new Uint8Array(4 + compressed.length);
    output.set(LCCA_MAGIC, 0);
    output.set(compressed, 4);
    return output;
}

/**
 * Creates a .3ps (ZIP) archive of the project data client-side.
 */
export async function export3psFile(projectData) {
    const zip = new JSZip();

    // 1. Write manifest.json
    const manifest = {
        project_id: projectData.id || `proj_${Date.now()}`,
        schema_version: projectData.schema_version || 1,
        exported_at: new Date().toISOString()
    };
    zip.file('manifest.json', JSON.stringify(manifest, null, 2));

    // 2. Add sections as chunks
    const chunkKeys = [
        'general_info',
        'bridge_data',
        'financial_data',
        'traffic_data',
        'foundation_data',
        'substructure_data',
        'superstructure_data',
        'miscellaneous_data',
        'carbon_emission_data',
        'maintenance_repair_data',
        'recycling_data',
        'demolition_data',
        'outputs_data'
    ];

    for (const key of chunkKeys) {
        if (projectData[key] !== undefined) {
            // Encode LCCA compressed chunk
            const encoded = encodeLcca(projectData[key]);
            zip.file(`chunks/${key}.json`, encoded);
        }
    }

    // Generate zip blob
    const blob = await zip.generateAsync({ type: 'blob' });
    return blob;
}

/**
 * Top-level report engine.
 *
 * Called from Outputs.jsx when the user clicks "Download Report".
 * Reports are generated client-side with jsPDF.
 *
 * @see reportGenerator.js
 */
import { generateFullReport } from './reportGenerator.js';

export const generateReport = async ({
    projectInputs,
    results,
    computedData,
    addLog = () => {},
    chartRefs = [],
    uploadedFileName,
    selections = {},
    calculationMetadata = {},
    options = {},
} = {}) => {
    const generated = await generateFullReport(
        projectInputs,
        results,
        computedData,
        addLog,
        chartRefs,
        uploadedFileName,
        selections,
        calculationMetadata,
        options,
    );

    return {
        ...generated,
        engine: 'jspdf',
        fallbackUsed: false,
    };
};

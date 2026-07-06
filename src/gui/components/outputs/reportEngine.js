/**
 * Top-level report engine dispatcher.
 *
 * Called from Outputs.jsx when the user clicks "Download Report".
 * Tries SwiftLaTeX (browser LaTeX → PDF) first, and falls back to the
 * legacy jsPDF report generator if SwiftLaTeX is unavailable or fails.
 *
 * @see latexReportEngine.js  — SwiftLaTeX compilation path
 * @see reportGenerator.js    — legacy jsPDF fallback
 */
import { generateLatexReportPdf } from './latexReportEngine.js';
import { generateFullReport } from './reportGenerator.js';

const DEFAULT_REPORT_ENGINE = 'swiftlatex';

const canUseSwiftLatex = () => (
    typeof window !== 'undefined'
    && typeof Worker !== 'undefined'
    && typeof Blob !== 'undefined'
    && typeof URL !== 'undefined'
);

const safeReportFileName = (projectInputs = {}, uploadedFileName) => {
    if (uploadedFileName) {
        return uploadedFileName.replace(/\.[^/.]+$/, '') + '_Report.pdf';
    }

    const projectName = projectInputs?.general_info?.project_name
        || projectInputs?.bridge_data?.bridge_name
        || 'LCCA_Report';

    const baseName = String(projectName)
        .trim()
        .replace(/[^\w.-]+/g, '_')
        .replace(/^_+|_+$/g, '');

    return `${baseName || 'LCCA_Report'}_Report.pdf`;
};

const downloadBlob = (blob, fileName) => {
    const href = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = href;
    anchor.download = fileName;
    anchor.style.display = 'none';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(href);
};

const generateJsPdfReport = async ({
    projectInputs,
    results,
    computedData,
    addLog,
    chartRefs,
    uploadedFileName,
    selections,
    calculationMetadata,
    options,
}) => {
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
        fallbackUsed: options?.fallbackUsed || false,
    };
};

export const generateReport = async ({
    projectInputs,
    results,
    computedData,
    addLog = () => {},
    chartRefs = [],
    uploadedFileName,
    selections = {},
    calculationMetadata = {},
    preferredEngine = import.meta.env?.VITE_LCCA_REPORT_ENGINE || DEFAULT_REPORT_ENGINE,
    options = {},
} = {}) => {
    const fileName = safeReportFileName(projectInputs, uploadedFileName);
    const shouldTrySwiftLatex = preferredEngine !== 'jspdf' && canUseSwiftLatex();

    if (shouldTrySwiftLatex) {
        try {
            addLog('Generating desktop-style LaTeX report in browser...');
            const generated = await generateLatexReportPdf({
                projectInputs,
                results,
                computedData,
                selections,
                calculationMetadata,
                fileName,
                onStatus: (message) => addLog(`SwiftLaTeX: ${message}`),
            });

            if (options.save !== false) {
                downloadBlob(generated.blob, generated.fileName);
            }
            addLog(`Report "${generated.fileName}" generated successfully using SwiftLaTeX.`);
            return {
                ...generated,
                engine: 'swiftlatex',
                fallbackUsed: false,
            };
        } catch (error) {
            addLog(`SwiftLaTeX report failed: ${error.message}`);
            addLog('Falling back to the existing jsPDF report generator...');
        }
    } else if (preferredEngine !== 'jspdf') {
        addLog('SwiftLaTeX report engine is unavailable in this environment. Falling back to jsPDF.');
    }

    return generateJsPdfReport({
        projectInputs,
        results,
        computedData,
        addLog,
        chartRefs,
        uploadedFileName,
        selections,
        calculationMetadata,
        options: {
            ...options,
            fallbackUsed: preferredEngine !== 'jspdf',
        },
    });
};

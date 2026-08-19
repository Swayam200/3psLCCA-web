import React, { useState, useEffect, useRef } from 'react';
import { useProjectData } from '../../../contexts/ProjectDataContext';
import { Button, Form, ProgressBar } from 'react-bootstrap';
import JSZip from 'jszip';
import pako from 'pako';
import { FaCheckCircle, FaFileUpload } from 'react-icons/fa';
import { computeAllSummaries } from './lifecycleSummary';
import { generateReport } from './reportEngine';
import ReportSectionModal from './ReportSectionModal';
import ResultsView from './ResultsView';
import { buildCalculationProjectInputs } from '../../../utils/projectDerivations';
import {
    calculateLcca,
    getLccaEngineDescription,
    getLccaEngineMode,
    initializeLccaEngine,
} from '../../../lib/lccaApi';

// The AI assistant only exists in builds made with VITE_AI_ENABLED=true. The
// comparison must stay inline (not a shared constant) so Vite folds it to a
// literal and drops the dynamic import — and with it the whole src/lib/ai
// package — from flag-off bundles (enforced by tests/ai/bundleExclusion.test.js).
const AI_ENABLED = import.meta.env.VITE_AI_ENABLED === 'true';
const AiCueLazy = AI_ENABLED ? React.lazy(() => import('../ai/AiResultsCue.jsx')) : null;
const AiCueSlot = (props) => (AiCueLazy ? (
    <React.Suspense fallback={null}><AiCueLazy {...props} /></React.Suspense>
) : null);

const Outputs = ({ addLog, navTrigger }) => {
    const { projectData, updateProjectData } = useProjectData();

    const projectInputs = React.useMemo(() => {
        return projectData ? buildCalculationProjectInputs(projectData) : null;
    }, [projectData]);

    const [view, setView] = useState('validation'); // 'validation' or 'results'
    const [analysisPeriod, setAnalysisPeriod] = useState(
        () => parseInt(projectData?.bridge_data?.analysis_period) || 0
    );
    const [uploadedResults, setUploadedResults] = useState(null);
    const [calculationResults, setCalculationResults] = useState(() => projectData?.outputs_data?.results || null);
    const [fileError, setFileError] = useState(null);
    const [computedData, setComputedData] = useState(null);
    const [uploadedFileName, setUploadedFileName] = useState(null);
    const [isCalculating, setIsCalculating] = useState(false);
    const [calculationPhase, setCalculationPhase] = useState('idle');
    const [engineMetadata, setEngineMetadata] = useState(
        () => projectData?.outputs_data?.engine || {}
    );
    const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
    const [reportProgress, setReportProgress] = useState(null); // { message, percent }
    const [showReportModal, setShowReportModal] = useState(false);

    const reportRef = useRef();
    const pieChartRef = useRef();
    const barChartRef = useRef();
    const fileInputRef = useRef();
    const LCCA_MAGIC = [0x4C, 0x43, 0x43, 0x41]; // "LCCA"

    useEffect(() => {
        // Keep the analysis period aligned when a different project is loaded.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setAnalysisPeriod(parseInt(projectData?.bridge_data?.analysis_period) || 0);
    }, [projectData?.bridge_data?.analysis_period]);

    const resultsToUse = uploadedResults || calculationResults;

    const decodeLcca = (uint8) => {
        // Check for "LCCA" magic header
        const isLcca = uint8[0] === LCCA_MAGIC[0] && uint8[1] === LCCA_MAGIC[1] && 
                       uint8[2] === LCCA_MAGIC[2] && uint8[3] === LCCA_MAGIC[3];
        
        if (isLcca) {
            // Compressed: Magic (4 bytes) + Zlib data
            const compressed = uint8.slice(4);
            const decompressed = pako.inflate(compressed);
            const text = new TextDecoder().decode(decompressed);
            return JSON.parse(text);
        } else {
            // Plain JSON
            const text = new TextDecoder().decode(uint8);
            return JSON.parse(text);
        }
    };

    useEffect(() => {
        // Reset to validation view whenever a navigation trigger occurs
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setView('validation');
    }, [navTrigger]);

    useEffect(() => {
        if (resultsToUse) {
            const summaries = computeAllSummaries(resultsToUse);
            // Results can be restored from saved project data while mounted.
            // eslint-disable-next-line react-hooks/set-state-in-effect
            setComputedData(summaries);
        } else {
            setComputedData(null);
        }
    }, [resultsToUse]);

    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        setUploadedFileName(file.name);
        addLog(`Reading file: ${file.name}...`);
        const reader = new FileReader();
        
        reader.onload = async (e) => {
            const arrayBuffer = e.target.result;
            const uint8 = new Uint8Array(arrayBuffer);
            
            // Check for ZIP signature (PK\x03\x04)
            const isZip = uint8[0] === 0x50 && uint8[1] === 0x4B && uint8[2] === 0x03 && uint8[3] === 0x04;
            
            try {
                let json;
                if (isZip) {
                    addLog("Detected ZIP archive. Unzipping project data...");
                    const zip = await JSZip.loadAsync(arrayBuffer);
                    const outputFile = zip.file("chunks/outputs_data.lcca");
                    
                    if (outputFile) {
                        const content = await outputFile.async("uint8array");
                        json = decodeLcca(content);
                        addLog("Extracted and decoded outputs from project archive.");
                    } else {
                        throw new Error("Missing 'chunks/outputs_data.lcca' in archive.");
                    }
                } else {
                    // Try decoding as LCCA binary or plain JSON
                    json = decodeLcca(uint8);
                }

                // Flexible results detection
                const candidateResults = json.results || 
                                       (json.data && (json.data.results || json.data)) || 
                                       (json.chunks?.outputs_data?.results || json.chunks?.outputs_data) ||
                                       json;
                
                if (candidateResults.initial_stage || candidateResults.results || candidateResults.status === "success") {
                    const finalResults = candidateResults.results || candidateResults;
                    setUploadedResults(finalResults);
                    setFileError(null);
                    addLog(`File "${file.name}" loaded successfully.`);
                    
                    const summaries = computeAllSummaries(finalResults);
                    setComputedData(summaries);
                } else {
                    const keys = Object.keys(json).join(", ");
                    setFileError(`Invalid file format. Keys found: [${keys}].`);
                }
            } catch (err) {
                setFileError(`Failed to parse file: ${err.message}`);
            }
        };
        reader.readAsArrayBuffer(file);
    };

    const handleProceed = async () => {
        if (!uploadedResults && !projectInputs) {
            setFileError("Please enter project data or upload a .3psLCCA archive first.");
            return;
        }

        if (uploadedResults) {
            const summaries = computeAllSummaries(uploadedResults);
            setComputedData(summaries);
            setView('results');
            addLog("Uploaded calculation results loaded.");
            return;
        }

        setIsCalculating(true);
        setCalculationPhase('loading');
        setFileError(null);

        try {
            const initialized = await initializeLccaEngine((message) => addLog(message));
            const engineDescription = await getLccaEngineDescription();
            addLog(`Using the ${engineDescription}.`);
            const nextEngineMetadata = {
                source: getLccaEngineMode(),
                ...(initialized?.engineVersion ? { coreVersion: initialized.engineVersion } : {}),
                ...(initialized?.pyodideVersion ? { pyodideVersion: initialized.pyodideVersion } : {}),
            };
            setEngineMetadata(nextEngineMetadata);
            setCalculationPhase('calculating');
            // Desktop parity: the recycling total and the social cost of
            // carbon are resolved fresh at calculation time (from material
            // rows and the saved Ricke parameters), like desktop's live
            // widgets do — never trusted from possibly-stale stored values.
            const { prepareProjectForCalculation } = await import('../../../utils/calculationPrep.js');
            const prepared = await prepareProjectForCalculation(projectData);
            if (prepared.recycling) {
                updateProjectData('recycling_data', prepared.recycling);
                addLog(`Recycling: recovered value ${Math.round(prepared.recycling.total_recovered_value).toLocaleString('en-IN')} from ${prepared.recycling.included_count} of ${prepared.recycling.total_count} materials.`);
            }
            if (prepared.socialCost) {
                updateProjectData('carbon_emission_data', prepared.project.carbon_emission_data);
                addLog(`Social cost of carbon resolved: ${prepared.socialCost.cost.toFixed(3)} per kgCO₂e.`);
            }
            addLog("Running lifecycle cost calculation...");
            // Send the DERIVED inputs, not the raw project: the derivation
            // computes desktop-identical totals (material kgCO₂e, recycling,
            // construction sums); the adapter's raw-row fallback does not.
            const response = await calculateLcca({
                project: buildCalculationProjectInputs(prepared.project),
                analysisPeriodYears: analysisPeriod,
            });

            if (response.status !== 'success') {
                const errors = response.validation?.errors || ['Calculation failed.'];
                setFileError(errors.join(' '));
                addLog(`Calculation failed: ${errors.join(' ')}`);
                return;
            }

            const summaries = computeAllSummaries(response.results);
            const calculatedAt = new Date().toISOString();
            const completedEngineMetadata = {
                ...nextEngineMetadata,
                calculatedAt,
            };
            setEngineMetadata(completedEngineMetadata);
            setCalculationResults(response.results);
            setComputedData(summaries);
            updateProjectData('outputs_data', {
                results: response.results,
                computed: response.computed || {},
                validation: response.validation || { errors: [], warnings: [] },
                analysis_period_years: analysisPeriod,
                calculated_at: calculatedAt,
                source: getLccaEngineMode(),
                engine: completedEngineMetadata,
            });
            setView('results');
            addLog("Calculation completed successfully.");
        } catch (err) {
            const message = `Calculation engine unavailable or failed: ${err.message}`;
            setFileError(message);
            addLog(message);
        } finally {
            setIsCalculating(false);
            setCalculationPhase('idle');
        }
    };

    const handleDownloadReport = () => {
        if (!computedData) {
            addLog("Error: Calculation results are not ready yet. Please click 'Proceed' or wait for data to load.");
            return;
        }
        // Start the heavy one-time downloads (Python runtime, TeX engine)
        // while the user is still choosing sections in the modal.
        import('./latexReportEngine.js')
            .then(({ warmUpLatexReport }) => warmUpLatexReport())
            .catch(() => {});
        setShowReportModal(true);
    };

    const handleConfirmReport = async (selections) => {
        setShowReportModal(false);
        if (isGeneratingPdf) return;

        setIsGeneratingPdf(true);
        addLog("Preparing professional LCCA report...");
        try {
            const charts = [pieChartRef, barChartRef];
            const resultsForReport = resultsToUse;
            if (!resultsForReport) {
                throw new Error("Calculation results are not ready. Please run the backend calculation first.");
            }

            // Preferred engine: the desktop app's own LaTeX pipeline running
            // fully in the browser (desktop-identical PDF). jsPDF remains the
            // automatic fallback if WASM is unavailable or the compile fails.
            try {
                const { generateLatexReport, downloadPdf, progressPercent } = await import('./latexReportEngine.js');
                let lastPercent = 0;
                setReportProgress({ message: 'Starting…', percent: 0 });
                const { pdf, fileName, plotError } = await generateLatexReport({
                    projectData,
                    results: resultsForReport,
                    selections,
                    onProgress: (message) => {
                        addLog(message);
                        const percent = progressPercent(message);
                        if (percent !== null) lastPercent = percent;
                        setReportProgress({ message, percent: lastPercent });
                    },
                });
                if (plotError) addLog(`Warning: report plots unavailable (${plotError}).`);
                setReportProgress({ message: 'Report ready — downloading…', percent: 100 });
                downloadPdf(pdf, fileName);
                addLog(`LaTeX report ready: ${fileName} (${(pdf.length / 1024 / 1024).toFixed(2)} MB).`);
                return;
            } catch (latexError) {
                console.error("LaTeX report engine failed, falling back to jsPDF:", latexError);
                addLog(`LaTeX engine unavailable (${latexError.message}). Generating fallback-layout report instead...`);
                setReportProgress(null);
            }

            await generateReport({
                projectInputs,
                results: resultsForReport,
                computedData,
                addLog,
                chartRefs: charts,
                uploadedFileName,
                selections,
                calculationMetadata: {
                    source: projectData?.outputs_data?.source || getLccaEngineMode(),
                    calculated_at: projectData?.outputs_data?.calculated_at || engineMetadata.calculatedAt,
                    ...projectData?.outputs_data?.engine,
                    ...engineMetadata,
                },
            });
        } catch (err) {
            console.error("PDF Export Error:", err);
            addLog(`Error: ${err.message}`);
        } finally {
            setIsGeneratingPdf(false);
            setReportProgress(null);
        }
    };

    const renderValidation = () => (
        <div className="p-4" style={{ color: 'var(--app-text-primary)', position: 'relative' }}>
            <h2 className="mb-4" style={{ color: 'var(--app-primary-accent)' }}>Outputs</h2>
            
            <Form.Group className="mb-4">
                <Form.Label className="fw-bold" style={{ color: 'var(--app-text-primary)' }}>Project Results Data (.3psLCCAFile) *</Form.Label>
                <div className="mb-2" style={{ fontSize: '0.85rem', color: 'var(--app-text-secondary)' }}>Upload a previously calculated project file to view its outputs.</div>
                <div className="d-flex gap-3 align-items-center">
                    <Button 
                        variant="outline-secondary" 
                        onClick={() => fileInputRef.current.click()}
                        style={{ borderColor: 'var(--app-border-mid)', color: 'var(--app-text-primary)' }}
                    >
                        <FaFileUpload className="me-2" /> {uploadedResults ? "Change File" : "Choose File"}
                    </Button>
                    <input 
                        type="file" 
                        ref={fileInputRef} 
                        className="d-none"
                        accept=".3psLCCA,.3psLCCAFile,.json"
                        onChange={handleFileUpload}
                    />
                    {uploadedResults && <span style={{ fontSize: '0.9rem', color: 'var(--app-primary-accent)' }}><FaCheckCircle className="me-1" /> File loaded</span>}
                </div>
                {fileError && <div className="mt-2 text-danger" style={{ fontSize: '0.85rem' }}>{fileError}</div>}
            </Form.Group>

            <Form.Group className="mb-4">
                <Form.Label className="fw-bold" style={{ color: 'var(--app-text-primary)' }}>Analysis Period</Form.Label>
                <div className="mb-2" style={{ fontSize: '0.85rem', color: 'var(--app-text-secondary)' }}>Total time horizon used for life cycle cost evaluation.</div>
                <Form.Control 
                    type="text" 
                    disabled={true}
                    value={`${analysisPeriod} (years)`}
                    style={{ backgroundColor: 'var(--app-input-bg)', border: '1px solid var(--app-input-border)', color: 'var(--app-input-text)', opacity: 0.6 }}
                />
            </Form.Group>

            <div
                className="mb-2"
                style={{ fontSize: '0.82rem', color: 'var(--app-text-secondary)' }}
                data-testid="lcca-engine-indicator"
            >
                Calculation engine: {getLccaEngineMode() === 'browser' ? 'In-browser (3psLCCA-core via CDN)' : 'FastAPI backend'}
                {engineMetadata.coreVersion && ` | Core ${engineMetadata.coreVersion}`}
            </div>

            <Button 
                className="w-100 mt-4 py-2" 
                disabled={isCalculating || (!uploadedResults && !projectInputs)}
                style={{ 
                    backgroundColor: 'var(--app-primary-accent)', 
                    border: 'none', 
                    color: '#000', 
                    fontWeight: 'bold', 
                    opacity: (isCalculating || (!uploadedResults && !projectInputs) ? 0.5 : 1)
                }}
                onClick={handleProceed}
            >
                {calculationPhase === 'loading'
                    ? 'Preparing calculation engine...'
                    : calculationPhase === 'calculating'
                        ? 'Calculating...'
                        : 'Proceed with Calculation ▸'}
            </Button>

            <div className="mt-4"><AiCueSlot label="Ask the AI assistant about this project" /></div>
        </div>
    );

    const renderResults = () => {
        if (!computedData) return null;

        const analysisPeriodYears = parseInt(projectData?.bridge_data?.analysis_period) || 0;
        const yearOfConstruction = parseInt(projectData?.bridge_data?.year_of_construction) || 0;
        const currency = projectData?.general_info?.project_currency || projectData?.currency || 'INR';

        return (
            <div ref={reportRef} ref-id="report-container" className="p-4" style={{ color: 'var(--app-text-primary)', position: 'relative', backgroundColor: 'var(--app-bg-main)' }}>
                {/* Desktop layout: page title, then the report button under it */}
                <h2 className="mb-3" style={{ color: 'var(--app-primary-accent)' }}>Results</h2>
                <div className="mb-4">
                    <Button
                        onClick={handleDownloadReport}
                        disabled={isGeneratingPdf}
                        style={{ backgroundColor: 'var(--app-primary-accent)', border: 'none', color: '#1e1e28', fontWeight: 600, opacity: isGeneratingPdf ? 0.6 : 1 }}
                    >
                        {isGeneratingPdf ? (
                            <><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Generating...</>
                        ) : (
                            'Generate PDF Report'
                        )}
                    </Button>
                </div>

                {isGeneratingPdf && reportProgress && (
                    <div className="mb-4" data-testid="report-progress">
                        <div className="d-flex justify-content-between mb-1" style={{ fontSize: '0.82rem', color: 'var(--app-text-secondary)' }}>
                            <span>{reportProgress.message}</span>
                            <span>{reportProgress.percent}%</span>
                        </div>
                        <ProgressBar
                            now={reportProgress.percent}
                            animated
                            style={{ height: '6px', backgroundColor: 'var(--app-input-bg)' }}
                        />
                        <div className="mt-1" style={{ fontSize: '0.75rem', color: 'var(--app-text-secondary)' }}>
                            First report on this device downloads the engine (~60 MB, cached afterwards) — later reports take seconds.
                        </div>
                    </div>
                )}

                <div
                    className="mb-3"
                    style={{ fontSize: '0.82rem', color: 'var(--app-text-secondary)' }}
                    data-testid="lcca-engine-provenance"
                >
                    Calculated with: {(engineMetadata.source || projectData?.outputs_data?.engine?.source) === 'browser'
                        ? 'In-browser engine (3psLCCA-core via CDN)'
                        : (engineMetadata.source || projectData?.outputs_data?.engine?.source) === 'backend'
                            ? 'FastAPI backend'
                            : 'previously saved results'}
                    {engineMetadata.coreVersion && ` | Core ${engineMetadata.coreVersion}`}
                    {engineMetadata.calculatedAt && ` | ${new Date(engineMetadata.calculatedAt).toLocaleString()}`}
                </div>

                <div className="mb-4"><AiCueSlot /></div>

                <ResultsView
                    results={resultsToUse}
                    currency={currency}
                    analysisPeriod={analysisPeriodYears}
                    yearOfConstruction={yearOfConstruction}
                    pieChartRef={pieChartRef}
                    barChartRef={barChartRef}
                />

                <Button
                    variant="outline-secondary"
                    className="mt-4"
                    style={{ color: 'var(--app-text-secondary)', borderColor: 'var(--app-border-mid)' }}
                    onClick={() => setView('validation')}
                >
                    ← Back to Validation
                </Button>
            </div>
        );
    };

    return (
        <div style={{ minHeight: '100%', backgroundColor: 'var(--app-bg-main)', position: 'relative' }}>
            <style>{`
                .custom-output-table td { border-bottom: 1px solid var(--app-border-light) !important; }
            `}</style>
            {view === 'validation' ? renderValidation() : renderResults()}
            
            <ReportSectionModal 
                show={showReportModal} 
                onHide={() => setShowReportModal(false)} 
                onConfirm={handleConfirmReport} 
            />
        </div>
    );
};

export default Outputs;

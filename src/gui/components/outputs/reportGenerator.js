import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import { BREAKDOWN_STAGES, STAGE_DEFS, computeStagePillarTotals } from './breakdownStages.js';
import { SECTION_KEYS } from './reportSections.js';
import { buildReportModel } from './reportModel.js';

/**
 * Generates a modular, professional PDF report based on project data and user selections.
 */
export const generateFullReport = async (
    projectInputs,
    results,
    computedData,
    addLog,
    chartRefs,
    uploadedFileName,
    selections,
    calculationMetadata = {},
    options = {},
) => {
    addLog("Initializing professional report generation...");
    
    // Results might be passed as 'results' (from uploaded file) or we might need to derive them
    const finalResults = results || {};

    try {
        const doc = new jsPDF('p', 'mm', 'a4');
        const config = {
            pageWidth: doc.internal.pageSize.getWidth(),
            pageHeight: doc.internal.pageSize.getHeight(),
            margin: 20,
            primaryColor: [0, 51, 102], // Dark Blue
            accentColor: [0, 102, 204],  // Light Blue
            textColor: [40, 40, 40],
            greyColor: [150, 150, 150]
        };
        const report = buildReportModel(projectInputs, calculationMetadata);

        // 1. Title Page
        if (selections[SECTION_KEYS.KEY_SHOW_TITLE_PAGE]) {
            addTitlePage(doc, report, config);
        }

        // 2. Introduction
        if (selections[SECTION_KEYS.KEY_SHOW_INTRODUCTION]) {
            addIntroductionPage(doc, config);
        }

        // 3. Input Data Section
        await addInputDataSection(doc, report, selections, config, addLog);

        // 4. LCCA Results Section
        if (selections[SECTION_KEYS.KEY_SHOW_LCCA_RESULTS]) {
            await addResultsSection(doc, finalResults, computedData, chartRefs, config, addLog);
        }

        // 5. Appendix / Methodology (Always include)
        addAppendix(doc, report, config);

        // 6. Global Header/Footer/Page Numbers
        applyPageDecoration(doc, config);

        // Save File
        const bridgeName = report.project.name || "Bridge";
        let finalFileName = "LCCA_Report.pdf";
        if (uploadedFileName) {
            finalFileName = uploadedFileName.replace(/\.[^/.]+$/, "") + "_Report.pdf";
        } else {
            finalFileName = `${bridgeName.replace(/\s+/g, '_')}_Report.pdf`;
        }

        addLog("Finalizing PDF...");
        if (options.save !== false) doc.save(finalFileName);
        addLog(`Report "${finalFileName}" generated successfully.`);
        return {
            fileName: finalFileName,
            arrayBuffer: options.returnArrayBuffer ? doc.output('arraybuffer') : null,
        };

    } catch (err) {
        console.error("Fatal Error in PDF Generation:", err);
        addLog(`FATAL ERROR: ${err.message}`);
        throw err;
    }
};

// --- Helper Components ---

const addTitlePage = (doc, report, config) => {
    const { pageWidth, margin } = config;
    
    // Title
    doc.setFontSize(26);
    doc.setTextColor(...config.primaryColor);
    doc.setFont("helvetica", "bold");
    doc.text("Bridge Life Cycle Cost Analysis Report", pageWidth / 2, 80, { align: 'center' });
    
    doc.setFontSize(14);
    doc.setFont("helvetica", "italic");
    doc.setTextColor(100, 100, 100);
    doc.text("Professional Assessment & Sustainability Matrix", pageWidth / 2, 92, { align: 'center' });
    
    // Project Metadata Box
    doc.setDrawColor(220, 220, 220);
    doc.setFillColor(249, 250, 251);
    doc.roundedRect(margin, 120, pageWidth - (margin * 2), 65, 3, 3, 'FD');
    
    doc.setTextColor(0, 0, 0);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.text("Project Information", margin + 10, 132);
    
    doc.setFont("helvetica", "normal");
    doc.setFontSize(11);
    const bridgeName = report.project.name;
    const projectCode = report.project.code;
    const description = report.project.description;
    
    let currentY = 145;
    doc.text(`Project Name:`, margin + 10, currentY);
    doc.setFont("helvetica", "bold");
    doc.text(bridgeName, margin + 45, currentY);
    
    currentY += 8;
    doc.setFont("helvetica", "normal");
    doc.text(`Project Code:`, margin + 10, currentY);
    doc.setFont("helvetica", "bold");
    doc.text(projectCode, margin + 45, currentY);
    
    currentY += 10;
    doc.setFont("helvetica", "normal");
    doc.text(`Summary:`, margin + 10, currentY);
    doc.setFontSize(10);
    const splitDesc = doc.splitTextToSize(description, pageWidth - (margin * 2) - 30);
    doc.text(splitDesc, margin + 10, currentY + 6);

    currentY += 20;
    doc.setFontSize(9);
    doc.setFont("helvetica", "normal");
    doc.text(
        `Country: ${report.project.country} | Currency: ${report.project.currency} | Units: ${report.project.unitSystem}`,
        margin + 10,
        currentY,
    );
    
    // Signatures Area
    const sigY = 230;
    doc.setFontSize(11);
    doc.setFont("helvetica", "bold");
    doc.text(`Evaluated By: ${report.project.evaluator}`, margin, sigY);
    doc.line(margin, sigY + 20, margin + 60, sigY + 20);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.text("Signature & Date", margin, sigY + 25);
    
    doc.setFont("helvetica", "bold");
    doc.setFontSize(11);
    doc.text(`Reviewed By: ${report.project.reviewer}`, pageWidth / 2 + 10, sigY);
    doc.line(pageWidth / 2 + 10, sigY + 20, pageWidth / 2 + 70, sigY + 20);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.text("Signature & Date", pageWidth / 2 + 10, sigY + 25);
    
    // Brand Footer
    doc.setFontSize(8);
    doc.setTextColor(150, 150, 150);
    doc.text("Generated via 3psLCCA Web Interface | IIT Bombay", pageWidth / 2, 285, { align: 'center' });
};

const addIntroductionPage = (doc, config) => {
    doc.addPage();
    const { margin, pageWidth } = config;
    
    doc.setFontSize(18);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(...config.primaryColor);
    doc.text("1  Introduction", margin, 25);
    
    doc.setFontSize(11);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(0, 0, 0);
    
    const introText = "This report summarizes the findings of a Life Cycle Cost Analysis (LCCA) performed for the designated bridge project. LCCA is a method for assessing the total cost of ownership of an asset over its entire life cycle, including initial costs, maintenance, road user impacts, and environmental externalities.\n\nThe analysis presented herein follows a standard methodology to ensure economic transparency and environmental accountability, facilitating data-driven decision-making for bridge infrastructure management.";
    
    doc.text(doc.splitTextToSize(introText, pageWidth - (margin * 2)), margin, 40);
    
    doc.setDrawColor(...config.accentColor);
    doc.setLineWidth(0.5);
    doc.line(margin, 70, pageWidth - margin, 70);
};

const addInputDataSection = async (doc, report, selections, config, addLog) => {
    const { margin, pageHeight } = config;
    let sectionNumber = 0;
    let cursor = 45;

    doc.addPage();
    doc.setFontSize(18);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(...config.primaryColor);
    doc.text("2  Input Data", margin, 25);
    doc.setFontSize(11);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(0, 0, 0);
    doc.text("Project inputs used for the life cycle assessment.", margin, 35);

    const ensureSpace = (minimum = 35) => {
        const tableEnd = doc.lastAutoTable?.finalY;
        if (tableEnd && tableEnd > cursor) cursor = tableEnd + 12;
        if (cursor + minimum > pageHeight - 22) {
            doc.addPage();
            cursor = 25;
        }
        return cursor;
    };

    const table = (title, head, body, options = {}) => {
        if (!body?.length) return;
        sectionNumber += 1;
        ensureSpace(options.minimumSpace || 40);
        doc.setFontSize(12);
        doc.setFont("helvetica", "bold");
        doc.setTextColor(...config.primaryColor);
        doc.text(`2.${sectionNumber} ${title}`, margin, cursor);
        autoTable(doc, {
            startY: cursor + 5,
            head: [head],
            body,
            theme: options.theme || 'striped',
            headStyles: { fillColor: config.primaryColor },
            styles: { fontSize: options.fontSize || 8, overflow: 'linebreak', cellPadding: 2 },
            margin: { left: margin, right: margin },
            rowPageBreak: 'avoid',
            ...options.autoTable,
        });
        cursor = doc.lastAutoTable.finalY + 12;
    };

    if (selections[SECTION_KEYS.KEY_SHOW_BRIDGE_DESC]) {
        addLog("Adding bridge description table...");
        table("Bridge Geometry and Description", ['Parameter', 'Value'], report.bridgeRows, { fontSize: 8.5 });
    }

    if (selections[SECTION_KEYS.KEY_SHOW_FINANCIAL]) {
        addLog("Adding financial data table...");
        table("Financial Inputs", ['Variable', 'Value', 'Source'], report.financialRows, { fontSize: 8.5 });
    }

    if (selections[SECTION_KEYS.KEY_SHOW_CONSTRUCTION]) {
        addLog("Adding construction work data...");
        table(
            "Construction Data",
            ['Category', 'Component', 'Material', 'Quantity', 'Unit', 'Rate', 'Source', `Total (${report.project.currency})`],
            report.constructionRows.map((row) => [
                row.category, row.component, row.material, row.quantity, row.unit,
                row.rate, row.source, row.total,
            ]),
            { fontSize: 6.5, minimumSpace: 55 },
        );
    }

    if (selections[SECTION_KEYS.KEY_SHOW_USE_STAGE]) {
        table(
            "Maintenance and End-of-Life Inputs",
            ['Activity', 'Cost basis', 'Frequency', 'Duration'],
            report.maintenanceRows,
            { fontSize: 7.5 },
        );
    }

    if (selections[SECTION_KEYS.KEY_SHOW_ROAD_TRAFFIC]) {
        if (report.trafficMode === 'GLOBAL') {
            table("Global Road-User Cost Input", ['Parameter', 'Value'], report.globalTrafficRows);
        } else {
            table("Road and Traffic Parameters", ['Parameter', 'Value'], report.roadRows);
        }
    }
    if (report.trafficMode !== 'GLOBAL' && selections[SECTION_KEYS.KEY_SHOW_AVG_TRAFFIC]) {
        table(
            "Average Daily Traffic",
            ['Vehicle category', 'Vehicles/day', 'Accident share (%)', 'PWR'],
            report.vehicleRows,
        );
    }
    if (report.trafficMode !== 'GLOBAL' && selections[SECTION_KEYS.KEY_SHOW_PEAK_HOUR] && report.peakRows.length) {
        table("Peak-Hour Distribution", ['Peak period', 'Daily traffic fraction'], report.peakRows);
    }

    if (selections[SECTION_KEYS.KEY_SHOW_SOCIAL_CARBON]) {
        table("Social Cost of Carbon", ['Parameter', 'Value'], report.socialCarbonRows);
    }
    if (selections[SECTION_KEYS.KEY_SHOW_MATERIAL_EMISSION]) {
        table(
            "Materials Included in Carbon Emissions",
            ['Category', 'Component', 'Material', 'Quantity', 'Unit', 'Conversion', 'Emission factor', 'Factor unit', 'Total kgCO2e'],
            report.materialIncluded.map((row) => [
                row.category, row.component, row.material, row.quantity, row.unit,
                row.conversionFactor, row.emissionFactor, row.emissionUnit, row.total,
            ]),
            { fontSize: 6.2, minimumSpace: 55 },
        );
        table(
            "Materials Excluded from Carbon Emissions",
            ['Category', 'Component', 'Material', 'Reason'],
            report.materialExcluded.map((row) => [row.category, row.component, row.material, row.reason]),
        );
    }
    if (selections[SECTION_KEYS.KEY_SHOW_TRANSPORT_EMISSION]) {
        table(
            "Transport Emissions",
            ['Vehicle', 'Origin', 'Distance (km)', 'Trips', 'Emissions (kgCO2e)'],
            report.transportRows.map((row) => [row.vehicle, row.origin, row.distance, row.trips, row.emissions]),
        );
    }
    if (selections[SECTION_KEYS.KEY_SHOW_ONSITE_EMISSION]) {
        table(
            "Machinery and Equipment Emissions",
            ['Equipment/source', 'Energy source', 'Consumption', 'Days', 'Emission factor', 'Emissions (kgCO2e)'],
            report.machineryRows.map((row) => [
                row.equipment, row.source, row.consumption, row.days, row.factor, row.emissions,
            ]),
        );
    }
    if (selections[SECTION_KEYS.KEY_SHOW_VEHICLE_EMISSION]) {
        table("Traffic Diversion Emissions", ['Parameter', 'Value'], report.diversionRows);
    }
    if (selections[SECTION_KEYS.KEY_SHOW_RECYCLING]) {
        table(
            "Materials Included in Recycling",
            ['Material', 'Recovery (%)', 'Scrap rate', `Recovered value (${report.project.currency})`],
            report.recyclingIncluded,
        );
        table("Materials Excluded from Recycling", ['Material', 'Reason'], report.recyclingExcluded);
    }
};

const addResultsSection = async (doc, results, computedData, chartRefs, config, addLog) => {
    doc.addPage();
    const { margin, pageWidth, pageHeight } = config;
    
    doc.setFontSize(18);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(...config.primaryColor);
    doc.text("3  LCCA Results", margin, 25);
    
    doc.setFontSize(11);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(0, 0, 0);
    doc.text("The following tables and figures summarize the findings of the Life Cycle Cost Analysis.", margin, 35);

    // Summary Table
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.text("3.1 Present Value Summary", margin, 45);

    const totalLcc = Object.values(computedData.stagewise).reduce((a, b) => a + b, 0);
    const rows = [
        ["Initial Stage Costs", (computedData.stagewise.initial / 1e6).toFixed(2), "M INR"],
        ["Use & Reconstruction Costs", (computedData.stagewise.use_reconstruction / 1e6).toFixed(2), "M INR"],
        ["End-of-Life Costs", (computedData.stagewise.end_of_life / 1e6).toFixed(2), "M INR"],
        ["TOTAL LCC (Present Value)", (totalLcc / 1e6).toFixed(2), "M INR"]
    ];

    autoTable(doc, {
        startY: 50,
        head: [['Lifecycle Phase', 'Cost (PV)', 'Unit']],
        body: rows,
        theme: 'grid',
        headStyles: { fillColor: [40, 167, 69] }, // Green for results
        styles: { fontSize: 10, fontStyle: 'bold' }
    });

    // Charts Integration
    if (chartRefs && chartRefs.length > 0) {
        addLog("Capturing result diagrams...");
        let currentY = doc.lastAutoTable.finalY + 20;
        
        for (let i = 0; i < chartRefs.length; i++) {
            const ref = chartRefs[i];
            if (ref && ref.current) {
                const imgData = await captureChartAsPng(ref.current, addLog, i);
                if (imgData) {
                    const imgWidth = 140;
                    const imgHeight = 100; // Approximate
                    
                    if (currentY + imgHeight > pageHeight - 40) {
                        doc.addPage();
                        currentY = 40;
                    }
                    
                    doc.setFontSize(10);
                    doc.setFont("helvetica", "italic");
                    doc.setTextColor(100, 100, 100);
                    doc.text(`Figure 3-${i+1}: ${i===0 ? "Sustainability Matrix" : "Lifecycle Phase Distribution"}`, pageWidth / 2, currentY - 5, { align: 'center' });
                    doc.addImage(imgData, 'PNG', (pageWidth - imgWidth) / 2, currentY, imgWidth, imgHeight);
                    currentY += imgHeight + 30;
                }
            }
        }
    }

    // Consolidated Table
    doc.addPage();
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(...config.primaryColor);
    doc.text("3.2 Consolidated Stage Summary", margin, 25);
    
    doc.setFontSize(10);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(0, 0, 0);
    doc.text("Disaggregation of costs across Economic, Environmental, and Social pillars.", margin, 35);

    const stageSummaryRows = STAGE_DEFS.map(([label, key, pillars]) => {
        const totals = computeStagePillarTotals(results, key, pillars);
        if (!totals) return [label, "0.00", "0.00", "0.00", "0.00"];
        const stageTotal = Object.values(totals).reduce((a, b) => a + b, 0);
        return [
            label,
            (totals.economic / 1e6).toFixed(2),
            (totals.environmental / 1e6).toFixed(2),
            (totals.social / 1e6).toFixed(2),
            (stageTotal / 1e6).toFixed(2)
        ];
    });

    // Add Grand Total row
    const pillarTotals = computedData.pillar_totals;
    stageSummaryRows.push([
        { content: 'Grand Total', styles: { fontStyle: 'bold', fillColor: [240, 240, 240] } },
        { content: (pillarTotals.eco / 1e6).toFixed(2), styles: { fontStyle: 'bold', fillColor: [240, 240, 240] } },
        { content: (pillarTotals.env / 1e6).toFixed(2), styles: { fontStyle: 'bold', fillColor: [240, 240, 240] } },
        { content: (pillarTotals.social / 1e6).toFixed(2), styles: { fontStyle: 'bold', fillColor: [240, 240, 240] } },
        { content: (totalLcc / 1e6).toFixed(2), styles: { fontStyle: 'bold', fillColor: [240, 240, 240] } }
    ]);

    autoTable(doc, {
        startY: 40,
        head: [['Stage', 'Economic (M)', 'Environmental (M)', 'Social (M)', 'Total (M INR)']],
        body: stageSummaryRows,
        theme: 'striped',
        headStyles: { fillColor: config.primaryColor },
        styles: { fontSize: 8 }
    });

    // Itemized Details (Optional inclusion or always?)
    doc.setFontSize(14);
    doc.setFont("helvetica", "bold");
    doc.text("3.3 Itemized Detail Breakdown", margin, doc.lastAutoTable.finalY + 15);
    
    const itemizedRows = [];
    BREAKDOWN_STAGES.forEach((stage) => {
        const stageData = results[stage.resultKey];
        if (!stageData) return;
        
        stage.rows.forEach((row) => {
            const val = stageData[row.pillar]?.[row.key] || 0;
            if (val !== 0) {
                itemizedRows.push([
                    stage.label,
                    row.label,
                    (val / 1e6).toFixed(2)
                ]);
            }
        });
    });

    autoTable(doc, {
        startY: doc.lastAutoTable.finalY + 20,
        head: [['Lifecycle Stage', 'Cost Item', 'Value (M INR)']],
        body: itemizedRows,
        theme: 'grid',
        headStyles: { fillColor: [100, 100, 100] },
        styles: { fontSize: 8 },
        rowPageBreak: 'avoid'
    });
};

const addAppendix = (doc, report, config) => {
    doc.addPage();
    const { margin, pageWidth } = config;
    
    doc.setFontSize(16);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(...config.primaryColor);
    doc.text("Appendix: Assumptions & Methodology", margin, 25);
    
    doc.setFontSize(9);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(50, 50, 50);
    
    const text = `Methodology: The Lifecycle Cost Analysis follows the ISO 15686-5 standard. All future costs are discounted to present values using the specified discount rate. Environmental costs are estimated based on the Social Cost of Carbon as defined in the project inputs. Social costs account for road user delays and safety impacts during construction and maintenance events.

Calculation engine: ${report.calculation.source}. Core version: ${report.calculation.coreVersion}. Calculated at: ${report.calculation.calculatedAt}.

Software: Generated using 3psLCCA Web Application developed for the FOSSEE project, IIT Bombay. This tool provides a collaborative environment for lifecycle engineering of bridge structures.`;
    
    doc.text(doc.splitTextToSize(text, pageWidth - (margin * 2)), margin, 35);
};

const applyPageDecoration = (doc, config) => {
    const pageCount = doc.internal.getNumberOfPages();
    const { pageWidth, pageHeight, margin } = config;
    
    for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        
        // Footer line
        doc.setDrawColor(230, 230, 230);
        doc.setLineWidth(0.2);
        doc.line(margin, pageHeight - 15, pageWidth - margin, pageHeight - 15);
        
        // Page Number
        doc.setFontSize(8);
        doc.setTextColor(150, 150, 150);
        doc.setFont("helvetica", "normal");
        doc.text(`Page ${i} of ${pageCount}`, pageWidth - margin, pageHeight - 10, { align: 'right' });
        doc.text("Confidential | 3psLCCA Professional Report", margin, pageHeight - 10);
    }
};

const captureChartAsPng = async (container, addLog, index) => {
    try {
        if (!container) {
            console.warn(`Chart container ${index} is null`);
            return null;
        }

        const svgElement = container.querySelector('svg');
        if (!svgElement) {
            console.warn(`No SVG found in chart container ${index}`);
            return null;
        }

        // Clone the SVG to avoid modifying the UI
        const clonedSvg = svgElement.cloneNode(true);
        
        // Set explicit dimensions if they are missing or "100%"
        const width = svgElement.clientWidth || 600;
        const height = svgElement.clientHeight || 400;
        clonedSvg.setAttribute('width', width);
        clonedSvg.setAttribute('height', height);

        // FORCE dark text color for the PDF report (which has a white background)
        // This ensures labels are visible even if the user is in Dark Mode on the web app
        const reportTextColor = '#333333';
        
        // Find all text elements and set their fill explicitly
        clonedSvg.querySelectorAll('text').forEach(text => {
            text.setAttribute('fill', reportTextColor);
            // Also handle inline styles if they exist
            if (text.style.fill) text.style.fill = reportTextColor;
            if (text.style.color) text.style.color = reportTextColor;
        });

        // Handle axis lines and ticks if they use currentColor or CSS variables
        clonedSvg.querySelectorAll('path.domain, .tick line').forEach(el => {
            el.setAttribute('stroke', reportTextColor);
            if (el.style.stroke) el.style.stroke = reportTextColor;
        });

        const serializer = new XMLSerializer();
        const svgString = serializer.serializeToString(clonedSvg);
        const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
        const url = URL.createObjectURL(svgBlob);
        
        return new Promise((resolve) => {
            const img = new Image();
            img.crossOrigin = "anonymous";
            img.onload = () => {
                const canvas = document.createElement('canvas');
                const scale = 3.0; // High resolution
                canvas.width = width * scale;
                canvas.height = height * scale;
                const ctx = canvas.getContext('2d');
                
                // Ensure a solid white background for the image
                ctx.fillStyle = "white";
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                
                ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                URL.revokeObjectURL(url);
                resolve(canvas.toDataURL('image/png'));
            };
            img.onerror = (e) => {
                console.error("SVG Image Load Error:", e);
                URL.revokeObjectURL(url);
                addLog(`Warning: Failed to capture chart ${index + 1}.`);
                resolve(null);
            };
            img.src = url;
        });
    } catch (err) {
        console.error("Error in captureChartAsPng:", err);
        addLog(`Error capturing chart: ${err.message}`);
        return null;
    }
};

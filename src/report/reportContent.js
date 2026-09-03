/**
 * Static report text, ported from the desktop report modules
 * (code_to_latex/pdf_generation_v3/{lcca_report_builder,appendix_A_content,
 * appendix_B_content}.py). Only prose and equations live here; every number
 * in the report comes from reportDocument.js.
 *
 * Equations are KaTeX/LaTeX strings — the desktop's own math, minus the
 * page-fitting macros (\resizebox, \makebox) that have no meaning in HTML.
 */

export const REPORT_TITLE = 'Bridge Life Cycle Cost Analysis Report';

export const PREPARED_USING = {
    label: '3psLCCA',
    url: 'https://osdag.iitb.ac.in/3pslcca',
    display: 'osdag.iitb.ac.in/3pslcca',
};

export const DISCLAIMER =
    'Generated using 3psLCCA. The software is provided without any warranty, express or implied. '
    + 'The life cycle cost analysis (LCCA) results depend on user-provided inputs. The evaluating '
    + 'agency is solely responsible for the accuracy of the input data and for any use of the results.';

export const INTRODUCTION =
    'Life Cycle Cost is the total cost incurred by the bridge throughout its life. This report presents '
    + 'Life Cycle Cost Assessment (LCCA) based on the Three Pillars of Sustainability-Life Cycle Cost '
    + '(3PS-LCC) framework, which considers the economic, social, and environmental pillars over the '
    + 'selected analysis period. The various life-cycle stages and sustainability pillars considered in '
    + 'the 3PS-LCC framework are illustrated in Figure 1.';

export const FRAMEWORK_FIGURE = {
    src: 'report-assets/framework-3ps-lcc.png',
    caption: '3PS-LCC framework',
};

export const APP_LOGO = 'report-assets/3pslcca-header.png';

/** Intro sentences that precede the input tables (lcca_report_builder REPORT_SCHEMA). */
export const TABLE_INTROS = {
    traffic: (ref) => `Table ${ref} presents the traffic and road parameters recorded for this project, including road classification, speed limits, and associated data used in the life cycle cost assessment.`,
    adt: (ref) => `Table ${ref} presents the average daily traffic composition across different vehicle categories, which forms the basis for estimating road user costs and diversion emissions during the construction phase.`,
    diversion: (ref) => `Table ${ref} summarises the carbon emissions attributable to traffic diversion during the construction phase, accounting for the additional travel distance and vehicle composition on the diversion route.`,
    peak: (ref) => `Table ${ref} presents the peak hour traffic distribution used to assess congestion-related impacts and road user costs during the construction phase.`,
    scc: () => 'The social cost of carbon (SCC) quantifies the monetary value of environmental damage caused by each unit of CO₂e emitted. The following section presents the SCC values and parameters adopted in this assessment.',
    material: (incRef, excRef) => `Table ${incRef} lists the materials included in the carbon emissions calculation along with their respective emission factors, quantities, and total CO₂e contributions.${excRef ? ` Materials excluded from the assessment are detailed in Table ${excRef}.` : ''}`,
    transport: (ref) => `Table ${ref} presents the estimated carbon emissions from transporting materials to and from the project site, calculated based on vehicle type, load capacity, and travel distance.`,
    machinery: () => 'The following section presents the carbon emissions from machinery and equipment operated on-site during the construction phase, calculated based on fuel and electricity consumption, operational hours, and corresponding emission factors.',
    results: (ref) => `Table ${ref} presents a comprehensive summary of the life cycle cost analysis results, expressed as present values. The costs are organised by life cycle stage — Initial Stage, Use Stage, Reconstruction, and End-of-Life — and further broken down by sustainability pillar: Economic, Environmental, and Social.`,
    figures: (refs) => `The life cycle cost results are further illustrated through the following figures. ${refs.map((r) => `Figure ${r}`).join(', ')} present the distribution of costs across the three sustainability pillars (Economic, Environmental, and Social) and the four life cycle stages, providing a visual overview of the relative contributions to the total life cycle cost.`,
};

export const CONSTRUCTION_LEGEND = [
    ['—', 'Database value (default)'],
    ['#', 'Manually entered'],
    ['§', 'Modified from database'],
    ['†', 'Imported from Excel'],
    ['‡', 'Imported from Excel and modified'],
];

export const SUMMARY_LEAD =
    'The LCCA results indicate the relative contribution of construction, road user, and environmental costs, '
    + 'supporting informed and sustainable bridge planning decisions.';

/* ── Appendix A ──────────────────────────────────────────────────────────── */

export const APPENDIX_A = {
    title: 'Appendix A: Assumptions',
    intro:
        'This Life Cycle Cost Assessment (LCCA) has been carried out using a deterministic, software-based '
        + 'approach. The analysis is based on standard engineering practice, published guidelines, and '
        + 'reasonable assumptions adopted to ensure consistency, transparency, and comparability of results. '
        + 'The key assumptions adopted in the present study are summarised below.',
    items: [
        { text: 'The analysis period corresponds to the design/service life of the bridge as specified in the project data.', bold: 'design/service life of the bridge' },
        { text: 'The study includes: initial construction, routine inspection, periodic maintenance, major inspections, repairs, replacement of bearings and expansion joints, reconstruction, demolition and disposal, and associated road user costs.' },
        { text: 'Only greenhouse gas (GHG) emissions are considered for environmental cost monetisation.' },
        { text: 'Other impacts such as noise pollution, local business impacts, regional economic disruptions, and broader social externalities are outside the scope of this study.' },
        { text: 'Components not explicitly defined in the input data or methodology are excluded.' },
        { text: 'Future technological advancement, policy changes, traffic growth variations, or economic structural shifts are not considered.' },
        { text: 'All costs are converted into present value terms.' },
        { text: 'The discounting approach is based on standard economic theory where future costs and benefits are adjusted to present value using a constant discount rate.' },
        { text: 'Inflation and interest rates are assumed constant over the analysis period.' },
        { text: 'Real interest rate principles are used in deriving the discount relationship.' },
        {
            text: 'Wholesale Price Index (WPI) ratios are used for escalation of specific cost components based on their respective commodity categories. WPI categories are used for adjusting the following components:',
            children: [
                'Passenger and crew cost → “All Commodities”',
                'Property damage and spare parts → “Manufacture of parts and accessories for motor vehicles”',
                'Human injury cost → “Medical accessories”',
                'Petrol → “Mineral Oils”',
                'Diesel → “HSD (High Speed Diesel)”',
                'Engine oil → “Lube oils”',
                'Grease and related oils → “Mineral oil (grouped)”',
                'Tyre costs (by vehicle category) → Corresponding tyre index categories',
                'Fixed and depreciation cost → “Manufacture of motor vehicles, trailers and semi-trailers”',
                'Commodity holding cost → “Fuel & Power”',
            ],
        },
        { text: 'Initial construction costs are based on estimated quantities and prevailing unit rates from SOR.' },
        { text: 'Carbon emissions during construction are calculated using emission factors for material, transportation and energy consumption.' },
        { text: 'Emission factors are assumed constant over the entire analysis period.' },
        { text: 'Transportation of materials occurs under normal traffic and operating conditions.' },
        { text: 'Maintenance and repair emissions are assumed proportional to initial construction emissions.' },
        { text: 'Demolition and disposal emissions are assumed proportional to construction emissions.' },
        { text: 'Recycling is assumed to generate cost recovery (treated as negative cost).' },
        { text: 'Environmental cost is calculated by monetising carbon emissions using a single Social Cost of Carbon (SCC) value.' },
        { text: 'Average Daily Traffic (ADT) is assumed constant within each defined analysis period.' },
        { text: 'Traffic composition (cars, two-wheelers, buses, LCVs, HCVs, MCVs) is based on input data.' },
        { text: 'Traffic diversion during construction, maintenance, repair, replacement, reconstruction, and demolition is assumed over a predefined detour length.' },
        { text: 'Vehicle operating cost, value of time, and accident cost are calculated using standard equations and accepted parameters.' },
        { text: 'Uniform traffic flow and average operating conditions are assumed during rerouting.' },
        { text: 'Routine inspections, periodic maintenance, major inspections, and repairs occur at fixed predefined intervals.' },
        { text: 'Maintenance and repair costs are calculated as a percentage of initial construction or superstructure cost.' },
        { text: 'Replacement activities are limited to bearings and expansion joints.' },
        { text: 'Reconstruction involves demolition of the existing bridge followed by construction of a new bridge with similar functional characteristics.' },
        { text: 'All interventions occur as scheduled without unplanned delays unless explicitly stated.' },
    ],
};

/* ── Appendix B ──────────────────────────────────────────────────────────── */

const TWO_LANE_NOTE = '(Note: This table of equation is only for two lane road)';
const TWO_LANE_EQ_NOTE = '(Note: This equation is only for two lane road)';

/** [symbol (LaTeX), meaning] — desktop glossary order. */
export const APPENDIX_B_GLOSSARY = [
    ['A_{Di}', 'Accident distribution'],
    ['A_{Ne}', 'Number of accidents for each vehicle type'],
    ['A_{Tn}', 'Total number of accidents in the stipulated time'],
    ['C_{Di}', 'Distance related cost'],
    ['CF_D', 'Distance related congestion factor'],
    ['CF_T', 'Time related congestion factor'],
    ['C_{Ti}', 'Time related cost'],
    ['DC_m', 'Duration of construction in months'],
    ['D_{ma}', 'Number of equipment usage days'],
    ['D_{wm}', 'Number of working days in a month'],
    ['Di', 'Distance travelled for transportation of material'],
    ['EF_m', 'Emission factor for materials'],
    ['EF_{ma}', 'Emission factor for energy consumption'],
    ['EF_{tp}', 'Emission factor for transportation'],
    ['EF_v', 'Vehicular emission factor'],
    ['E_{VD}', 'Vehicle damage cost'],
    ['E_{Vi}', 'Economic cost of injury'],
    ['Q_{rm}', 'Quantity of recycle material'],
    ['RE_c', 'Recycling cost'],
    ['T_{AT}', 'Additional travel time'],
    ['T_{VP}', 'Time value'],
    ['V/C', 'Volume-Capacity ratio'],
    ['V_{CD}', 'Vehicle counts per day'],
    ['\\mathrm{AC}', 'Accident cost'],
    ['\\mathrm{CC}', 'Cargo capacity'],
    ['\\mathrm{CFU}', 'Price of fuel'],
    ['\\mathrm{CHC}', 'Commodity holding cost'],
    ['\\mathrm{COF}', 'Conversion factor'],
    ['\\mathrm{CR}', 'Crash rate'],
    ['\\mathrm{CW}', 'Crew cost'],
    ['\\mathrm{DC}', 'Depreciation cost'],
    ['\\mathrm{D_{cf}}', 'Demolition and disposal cost'],
    ['\\mathrm{D_{cr}}', 'Demolition and disposal cost for reconstruction'],
    ['\\mathrm{DC_{y}}', 'Duration of construction (years)'],
    ['\\mathrm{DF_{EC}}', 'Emission cost for end-of-life demolition'],
    ['\\mathrm{DR_{EC}}', 'Emission cost for demolition during reconstruction'],
    ['\\mathrm{EOL}', 'Engine oil consumption'],
    ['\\mathrm{EOLC}', 'Engine oil cost'],
    ['\\mathrm{EOL_{P}}', 'Engine oil price'],
    ['\\mathrm{F_{C}}', 'Fuel cost'],
    ['\\mathrm{FC_{CB}}', 'Fuel consumption petrol'],
    ['\\mathrm{FC_{CS}}', 'Fuel consumption diesel'],
    ['\\mathrm{FL}', 'Fall'],
    ['\\mathrm{FXC}', 'Fixed cost'],
    ['\\mathrm{G}', 'Grease consumption'],
    ['\\mathrm{GC}', 'Grease cost'],
    ['\\mathrm{G_{P}}', 'Grease price'],
    ['I', 'Interest rate'],
    ['\\mathrm{IC}', 'Initial construction cost'],
    ['\\mathrm{IR}', 'Investment ratio'],
    ['\\mathrm{LC}', 'Maintenance labour cost'],
    ['\\mathrm{MIc}', 'Major inspection cost'],
    ['\\mathrm{MR_{c}}', 'Major repair cost'],
    ['\\mathrm{MR_{EC}}', 'Major repair emission cost'],
    ['n', 'Design life (years)'],
    ['\\mathrm{NP}', 'New vehicle cost'],
    ['\\mathrm{O_{Avg}}', 'Average occupancy of a vehicle'],
    ['\\mathrm{OL}', 'Other oil consumption'],
    ['\\mathrm{OLC}', 'Other oil cost'],
    ['\\mathrm{OL_{P}}', 'Other oil price'],
    ['\\mathrm{P_{IC}}', 'Percentage of initial construction cost'],
    ['\\mathrm{P_{IEC}}', 'Percentage of initial carbon emission'],
    ['\\mathrm{PMc}', 'Periodic maintenance cost'],
    ['\\mathrm{PM_{EC}}', 'Periodic maintenance emission cost'],
    ['\\mathrm{PT}', 'Passenger time cost'],
    ['\\mathrm{PWF}', 'Present Worth Factor'],
    ['\\mathrm{PWR}', 'Power weight ratio'],
    ['Q', 'Quantity of material'],
    ['r', 'Discount rate'],
    ['R', 'Rate of material'],
    ['\\mathrm{RC_{BE}}', 'Replacement cost of bearing and expansion joint'],
    ['\\mathrm{RCN}', 'Reconstruction cost'],
    ['\\mathrm{RD}', 'Rerouting distance'],
    ['\\mathrm{REC_{EC}}', 'Reconstruction emission cost'],
    ['\\mathrm{RG}', 'Roughness'],
    ['\\mathrm{RI_{c}}', 'Routine inspection cost'],
    ['\\mathrm{R}', 'Rate of recycle material'],
    ['\\mathrm{RS}', 'Rise'],
    ['\\mathrm{RUC}', 'Road user cost'],
    ['\\mathrm{SP}', 'Spare part cost'],
    ['\\mathrm{TC}', 'Time cost'],
    ['\\mathrm{TYC}', 'Tyre cost'],
    ['\\mathrm{TCe}', 'Cost of each tyre'],
    ['\\mathrm{TCR}', 'Time cost for reconstruction'],
    ['\\mathrm{TL}', 'Tyre life'],
    ['\\mathrm{TN}', 'Number of tyres'],
    ['\\mathrm{UPD}', 'Utilisation per day'],
    ['\\mathrm{VOC}', 'Vehicle operating cost'],
    ['\\mathrm{VOT}', 'Value of time cost'],
    ['\\mathrm{W}', 'Width of carriageway'],
    ['\\mathrm{WPI}', 'Wholesale price index'],
    ['\\mathrm{WZM}', 'Work zone multiplier'],
    ['x', 'Periodic interval (years)'],
    ['\\mathrm{ADT}', 'Average daily traffic'],
    ['\\mathrm{IEC}', 'Initial emission cost'],
    ['\\mathrm{IAEC}', 'Initial carbon emission cost from on-site activities'],
    ['\\mathrm{IETC}', 'Initial carbon emission cost due to transportation of material'],
    ['\\mathrm{SCC}', 'Social cost of carbon'],
    ['\\mathrm{VEC}', 'Vehicular emission cost'],
    ['\\mathrm{ECR}', 'Energy consumption rate'],
    ['H', 'Average machinery hours per day'],
];

const VOC = (sub) => `VOC_{${sub}} = ${sub === 'cn' ? '' : '\\mathrm{PWF} \\times '}D_{wm} \\times DC_m \\times RD \\left[ \\sum_{j=1}^{o} \\left\\{ (C_{Ti})_{j} (V_{CD})_{j} (CF_{T})_{j} (WPI_{Ti})_{j} \\right\\} + \\sum_{k=1}^{p} \\left\\{ (C_{Di})_{k} (V_{CD})_{k} (CF_{D})_{k} (WPI_{Di})_{k} \\right\\} \\right]`;
const VOT = (sub) => `VOT_{${sub}} = ${sub === 'cn' ? '' : '\\mathrm{PWF} \\times '}D_{wm} \\times DC_m \\times T_{AT} \\left[ \\sum_{j=1}^{o} \\left\\{ (T_{VP})_{j} (V_{CD})_{j} (O_{Avg})_{j} (WPI_{Ti})_{j} \\right\\} + \\sum_{k=1}^{p} \\left\\{ (CHC_{T})_{k} (V_{CD})_{k} (WPI_{Di})_{k} \\right\\} \\right]`;
const AC = (sub) => `AC_{${sub}} = ${sub === 'cn' ? '' : '\\mathrm{PWF} \\times '}A_{Tn} \\left[ \\sum_{j=1}^{o} \\left\\{ (E_{Vi})_{j} (A_{Di})_{j} (WPI_{me})_{j} \\right\\} + \\sum_{k=1}^{p} \\left\\{ (E_{VD})_{k} (A_{Ne})_{k} (WPI_{sp})_{k} \\right\\} \\right]`;
const RUC_BLOCK = (sub, title) => [
    { type: 'li', text: title },
    { type: 'eq', tex: `RUC_{${sub}} = VOC_{${sub}} + VOT_{${sub}} + AC_{${sub}}` },
    { type: 'eq', tex: VOC(sub) },
    { type: 'note', text: '(Refer to table B-1 to B-10 to calculate distance and time related costs for VOC)' },
    { type: 'eq', tex: VOT(sub) },
    { type: 'eq', tex: AC(sub) },
];
const VEC_RE = (name) => `\\mathrm{${name}} = \\mathrm{PWF} \\times \\mathrm{SCC} \\times D_{wm} \\times \\mathrm{DC}_m \\times \\mathrm{RD} \\times \\sum_{k=1}^{p} (\\mathrm{ADT})_k (\\mathrm{EF}_v)_k`;

/**
 * Appendix B as an ordered list of blocks:
 *   h3/h4 headings · p paragraphs · eq display equations (LaTeX) ·
 *   table {caption, rows:[label, tex]} · note/warn italic lines · li bullets.
 */
export const APPENDIX_B = {
    title: 'Appendix B: Calculation methodology',
    intro: 'This chapter presents the calculation method and equations used for cost calculations. The glossary for the terms used in the equations are mentioned below.',
    blocks: [
        { type: 'h3', text: 'B.1 Initial Cost' },
        { type: 'h4', text: 'B.1.1 Economic cost' },
        { type: 'p', text: 'Initial construction cost' },
        { type: 'eq', tex: 'IC = \\sum_{i=1}^{n} Q_i \\times R_i' },
        { type: 'p', text: 'Time cost' },
        { type: 'eq', tex: 'TC = IC \\times I \\times DC_y \\times IR' },

        { type: 'h4', text: 'B.1.2 Social cost' },
        { type: 'p', text: 'Road user cost during construction' },
        { type: 'eq', tex: 'RUC_{cn} = VOC_{cn} + VOT_{cn} + AC_{cn}' },
        { type: 'eq', tex: VOC('cn') },
        { type: 'p', text: 'Distance related costs' },
        { type: 'eq', tex: 'F_{Cp} = CFU_{Pe} \\times FC_{CS} \\qquad F_{Cd} = CFU_{Di} \\times FC_{CB} \\qquad F_{C} = CFU \\times FC' },
        {
            type: 'table', caption: 'Table B-1 Fuel Consumption equations for different vehicles', rows: [
                ['Small and Big Car', '\\begin{aligned} FC_{CS} &= 30 + \\tfrac{844.085}{V} + 0.003V^2 + (0.001 \\times RG) + (0.3414 \\times RS) - (0.2225 \\times FL) \\\\ FC_{CB} &= 35 + \\tfrac{983.503}{V} + 0.003V^2 + (0.002 \\times RG) + (0.339 \\times RS) - (0.4785 \\times FL) \\end{aligned}'],
                ['Two-wheeler', 'FC = 2.704 + \\tfrac{439.656}{V} + 0.00349V^2 + (0.000157 \\times RG) + (0.3642 \\times RS) - (0.2709 \\times FL)'],
                ['Buses', 'FC = 34.23 + \\tfrac{4054.42}{V} + 0.02149V^2 + (0.001246 \\times RG) + (3.4557 \\times RS) - (1.8454 \\times FL)'],
                ['LCV', 'FC_{CB} = 22.504 + \\tfrac{1708.244}{V} + 0.02591V^2 + (0.001612 \\times RG) + (5.6863 \\times RS) - (0.8744 \\times FL)'],
                ['HCV', 'FC_{CB} = 50.0 + \\tfrac{8049.955}{V} + 0.012V^2 + (0.005 \\times RG) + (4.565 \\times RS) - (4.904 \\times FL) - (7.285 \\times PWR)'],
                ['MCV', 'FC_{CB} = 90.0 + \\tfrac{14489.919}{V} + 0.0216V^2 + (0.01 \\times RG) + (8.217 \\times RS) - (8.8272 \\times FL) - (13.113 \\times PWR)'],
            ],
        },
        {
            type: 'table', caption: 'Table B-2 Speed equations for different vehicles', rows: [
                ['Small Car', 'V = 81.19 - (0.7892 \\times RF) - [0.001891 \\times (RG - 2000)]'],
                ['Big Car', 'V = 81.92 - (0.7963 \\times RF) - [0.001915 \\times (RG - 2000)]'],
                ['Two-wheeler', 'V = 59.71 - (0.7892 \\times RF) - [0.001891 \\times (RG - 2000)]'],
                ['Buses', 'V = 54.23 - (0.4111 \\times RF) - [0.00098 \\times (RG - 2000)]'],
                ['LCV', 'V = 57.41 - (0.5119 \\times RF) - [0.00102 \\times (RG - 2000)]'],
                ['HCV', 'V = 96.52 - (0.5040 \\times RF) - [0.00100 \\times (RG - 2000)]'],
                ['MCV', 'V = 44.79 - (0.3994 \\times RF) - [0.00079 \\times (RG - 2000)]'],
            ],
        },
        { type: 'warn', text: TWO_LANE_NOTE },
        { type: 'eq', tex: 'SP = \\frac{SP}{NP} \\times NP' },
        {
            type: 'table', caption: 'Table B-3 Spare part to New vehicle cost ratio for different vehicles', rows: [
                ['Small Car', '\\tfrac{SP}{NP} = 0.0075 \\times (RG - 2000) \\times 10^{-5}'],
                ['Big Car', '\\tfrac{SP}{NP} = 0.0045 \\times (RG - 2000) \\times 10^{-5}'],
                ['Two-wheeler', '\\tfrac{SP}{NP} = [-55.879 + (0.024 \\times RG)] \\times 10^{-5}'],
                ['Buses', '\\tfrac{SP}{NP} = e^{-9.7871 + (0.007373 \\times RF) + (0.0000723 \\times RG) + \\frac{1.925}{W}}'],
                ['LCV', '\\tfrac{SP}{NP} = e^{-10.5615 + (0.000141 \\times RG) + \\frac{3.493}{W}}'],
                ['HCV and MCV', '\\tfrac{SP}{NP} = e^{-9.492638 + (0.0001413 \\times RG) + \\frac{3.493}{W}}'],
            ],
        },
        { type: 'eq', tex: 'LC = a \\times SP' },
        { type: 'note', text: 'a for small car and big car = 1.79934, Two-wheeler = 0.5498, Buses = 1.1781, LCV = 0.85773, HCV and MCV = 0.7912' },
        { type: 'eq', tex: 'TC = \\frac{TC_e \\times TN}{TL}' },
        {
            type: 'table', caption: 'Table B-4 Tyre Life equations for different vehicles', rows: [
                ['Small and big car', 'TL = 68771 - (147.9 \\times RF) - (26.72 \\times RG/W)'],
                ['Two-wheeler', 'TL = 47340 - (101.8 \\times RF) - (18.39 \\times RG/W)'],
                ['Buses', 'TL = 38519 - (389.52 \\times RF) - (1.32 \\times RG) + (983.829 \\times W)'],
                ['LCV', 'TL = 22382 - (375.3 \\times RF) - (1.037 \\times RG) + (3817 \\times W)'],
                ['HCV', 'TL = 24662 - (413.6 \\times RF) - (1.142 \\times RG) + (4205 \\times W)'],
                ['MCV', 'TL = 23726 - (398 \\times RF) - (1.0099 \\times RG) + (4046 \\times W)'],
            ],
        },
        { type: 'eq', tex: 'EOLC = EOL \\times EOL_{P} \\times 10^{-3}' },
        {
            type: 'table', caption: 'Table B-5 Engine oil consumption for different vehicles', rows: [
                ['Small and big car', 'EOL = 1.8807 + (0.036615 \\times RF) + (0.000578 \\times RG/W)'],
                ['Two-wheeler', 'EOL = 0.405 + (0.007899 \\times RF) + (0.000125 \\times RG/W)'],
                ['Buses', 'EOL = 0.4303 + (0.001494 \\times RF) + (0.0007885 \\times RG/W)'],
                ['LCV', 'EOL = 0.80679 + (0.019496 \\times RF) + (0.0001297 \\times RG/W)'],
                ['HCV', 'EOL = 1.0277 + (0.02495 \\times RF) + (0.0001782 \\times RG/W)'],
                ['MCV', 'EOL = 1.3826 + (0.03348 \\times RF) + (0.002319 \\times RG/W)'],
            ],
        },
        { type: 'eq', tex: 'OLC = OL \\times OLP \\times 10^{-4}' },
        {
            type: 'table', caption: 'Table B-6 Other oil consumption equations for different vehicles', rows: [
                ['Small and big car and two-wheeler', 'OL = 1.631 + (0.05167 \\times RF) + (0.001867 \\times RG/W)'],
                ['Buses', 'OL = 3.3201 + (0.002889 \\times RF) + (0.0008217 \\times RG) - (0.3295 \\times W)'],
                ['LCV', 'OL = 2.0415 + (0.0001058 \\times RG)'],
                ['HCV and MCV', 'OL = 5.1037 + (0.0002646 \\times RG)'],
            ],
        },
        { type: 'eq', tex: 'GC = G \\times G_{P} \\times 10^{4}' },
        {
            type: 'table', caption: 'Table B-7 Grease consumption equations for different vehicles', rows: [
                ['Small car, big car and two-wheeler', 'G = 2.816 + (0.2007 \\times RF)'],
                ['Buses', 'G = 4.992 + (0.03376 \\times RF) + (0.3634 \\times W)'],
                ['LCV', 'G = 0.3661 + (0.0283 \\times RF) + (0.000251 \\times RG)'],
                ['HCV and MCV', 'G = 0.9153 + (0.0707 \\times RF) + (0.000627 \\times RG)'],
            ],
        },
        { type: 'p', text: 'Time related costs', bold: true },
        { type: 'eq', tex: 'FXC = \\frac{b}{UPD}' },
        { type: 'note', text: 'b for small car and big car = 395.65, Two-wheeler = 24.32, Buses = 772.89, LCV = 723.80, HCV = 924.28, MCV = 1238.26' },
        {
            type: 'table', caption: 'Table B-8 Utilisation per day equations for different vehicles', rows: [
                ['Small car', 'UPD = 6.7127 \\times V'],
                ['Big Car', 'UPD = 6.7378 \\times V'],
                ['Two-wheeler', 'UPD = 2.119 \\times V'],
                ['Buses', 'UPD = 22.7134 + (12.2569 \\times V)'],
                ['LCV', 'UPD = 28.807 + (2.1836 \\times V)'],
                ['HCV', 'UPD = 55.6719 + (4.22 \\times V)'],
                ['MCV', 'UPD = 77.7233 + (5.8915 \\times V)'],
            ],
        },
        { type: 'eq', tex: 'DC = \\frac{c}{UPD}' },
        { type: 'note', text: 'c for small and big cars = 42.83, Two-wheeler = 4.26, Buses = 221, LCV = 120.9, HCV = 154.54 and MCV = 238.54' },
        { type: 'p', text: 'For Car and Two wheelers,' },
        { type: 'eq', tex: 'PT = \\frac{d}{V}' },
        { type: 'p', text: 'For Buses,' },
        { type: 'eq', tex: 'PT = \\frac{d}{UPD}' },
        { type: 'note', text: 'd for small and big car = 328.06, Two-wheeler = 70.29, Buses = 15509.8' },
        { type: 'warn', text: TWO_LANE_EQ_NOTE },
        { type: 'eq', tex: 'CW = \\frac{e}{UPD}' },
        { type: 'note', text: 'e for Buses = 3775.3, LCV = 900, HCV = 1500 and MCV = 1800' },
        { type: 'eq', tex: 'CHC = \\frac{f}{UPD}' },
        { type: 'note', text: 'f for LCV = 71.35, HCV = 218.75, MCV = 409.28' },
        { type: 'warn', text: TWO_LANE_EQ_NOTE },
        { type: 'p', text: 'Time related congestion factors', bold: true },
        {
            type: 'table', caption: 'Table B-9 Time related congestion factor equations for different vehicles', rows: [
                ['Cars', 'CF_T = 1.087 + (0.483 \\times V/C)'],
                ['Two-wheelers', 'CF_T = 0.804 + (0.865 \\times V/C)'],
                ['Buses', 'CF_T = 0.864 + (0.543 \\times V/C)'],
                ['LCV', 'CF_T = 0.925 + (0.573 \\times V/C)'],
                ['HCV and MCV', 'CF_T = 0.878 + (0.561 \\times V/C)'],
            ],
        },
        { type: 'warn', text: TWO_LANE_EQ_NOTE },
        { type: 'p', text: 'Distance related congestion factor', bold: true },
        {
            type: 'table', caption: 'Table B-10 Distance related congestion factor equations for different vehicles', rows: [
                ['Cars', 'CF_D = 0.893 + (0.259 \\times V/C)'],
                ['Two-wheelers', 'CF_D = 0.917 + (0.112 \\times V/C)'],
                ['Buses', 'CF_D = 0.800 + (1.1 \\times V/C)'],
                ['LCV', 'CF_D = 0.9 + (1.0 \\times V/C)'],
                ['HCV', 'CF_D = 0.925 + (0.482 \\times V/C)'],
                ['MCV', 'CF_D = 0.900 + (1.4 \\times V/C)'],
            ],
        },
        { type: 'warn', text: TWO_LANE_EQ_NOTE },
        { type: 'eq', tex: VOT('cn') },
        { type: 'eq', tex: AC('cn') },
        { type: 'eq', tex: 'A_{Tn} = D_{wm} \\times DC_m \\times CR \\times WZM \\times RD \\times 10^{-6}' },

        { type: 'h4', text: 'B.1.3 Environmental cost' },
        { type: 'li', text: 'Embodied carbon emission cost during construction' },
        { type: 'eq', tex: 'IEC = SCC \\times \\sum_{j=1}^{o} \\left[ Q_{j} \\times (COF)_{j} \\times (EF_{m})_{j} \\right]' },
        { type: 'li', text: 'Vehicular emission cost during construction due to rerouting' },
        { type: 'eq', tex: 'VEC = SCC \\times D_{wm} \\times DC_m \\times RD \\times \\sum_{k=1}^{p} \\left[ ADT_{k} \\times (EF_{v})_{k} \\right]' },
        { type: 'li', text: 'Carbon emissions from on-site activities during construction' },
        { type: 'eq', tex: 'IAEC = SCC \\times \\sum_{j=1}^{o} \\left[ (ECR)_{j} \\times (H)_{j} \\times (D_{ma})_{j} \\times (EF_{ma})_{j} \\right]' },
        { type: 'li', text: 'Carbon emission cost due to transportation of construction material' },
        { type: 'eq', tex: 'IETC = SCC \\times \\sum_{j=1}^{o} \\left[ Q_{j} \\times Di_{j} \\times (EF_{tp})_{j} \\right]' },

        { type: 'h3', text: 'B.2 Use Stage Cost' },
        { type: 'h4', text: 'B.2.1 Economic cost' },
        { type: 'li', text: 'Routine Inspection cost' },
        { type: 'eq', tex: 'RI_c = \\mathrm{PWF} \\times P_{Ics}' },
        { type: 'eq', tex: '\\mathrm{PWF} = \\sum_{i=1}^{\\mathrm{int}\\left(\\frac{n}{x}\\right)-1} \\frac{(1+f)^{i x}}{(1+r)^{i x}}' },
        { type: 'li', text: 'Periodic maintenance cost' },
        { type: 'eq', tex: 'PM_c = \\mathrm{PWF} \\times P_{ICm}' },
        { type: 'li', text: 'Major repair cost' },
        { type: 'eq', tex: 'MR_c = \\mathrm{PWF} \\times P_{ICr}' },
        { type: 'li', text: 'Major inspection cost' },
        { type: 'eq', tex: 'MI_c = \\mathrm{PWF} \\times P_{ICi}' },
        { type: 'li', text: 'Replacement cost of bearings and expansion joints' },
        { type: 'eq', tex: 'RC_{BE} = \\mathrm{PWF} \\times P_{SCr}' },

        { type: 'h4', text: 'B.2.2 Social cost' },
        ...RUC_BLOCK('mr', 'Road user cost due to rerouting during major repairs'),
        ...RUC_BLOCK('rbe', 'Road user cost due to rerouting during replacement of bearings and expansion joints'),

        { type: 'h4', text: 'B.2.3 Environmental cost' },
        { type: 'li', text: 'Carbon emission cost due to periodic maintenance' },
        { type: 'eq', tex: 'PM_{EC} = \\mathrm{PWF} \\times P_{IECp}' },
        { type: 'li', text: 'Carbon emission cost due to major repairs' },
        { type: 'eq', tex: 'MR_{EC} = \\mathrm{PWF} \\times P_{IECm}' },
        { type: 'li', text: 'Carbon emission due to rerouting of vehicles during major repairs' },
        { type: 'eq', tex: VEC_RE('VEC_{MR}') },
        { type: 'li', text: 'Carbon emission cost due to replacement of bearings and expansion joints' },
        { type: 'eq', tex: 'RC_{BEE} = \\mathrm{PWF} \\times P_{IESr}' },
        { type: 'li', text: 'Carbon emission due to rerouting of vehicles during replacement of bearings and expansion joints' },
        { type: 'eq', tex: VEC_RE('VEC_{RE}') },

        { type: 'h3', text: 'B.3 End-of-Life Stage Cost Calculation' },
        { type: 'h4', text: 'B.3.1 Economic cost' },
        { type: 'li', text: 'Demolition and disposal cost for reconstruction' },
        { type: 'eq', tex: 'D_{cr} = \\mathrm{PWF} \\times P_{ICd}' },
        { type: 'li', text: 'Reconstruction cost' },
        { type: 'eq', tex: '\\mathrm{RCN} = \\mathrm{PWF} \\times \\mathrm{IC}' },
        { type: 'li', text: 'Time cost for reconstruction of bridge' },
        { type: 'eq', tex: '\\mathrm{TCR} = \\bigl| \\mathrm{PWF} \\times \\mathrm{TC} \\bigr|' },
        { type: 'li', text: 'Demolition cost at end of life' },
        { type: 'eq', tex: 'D_{cf} = \\mathrm{PWF} \\times P_{ICd}' },
        { type: 'li', text: 'Recycling cost' },
        { type: 'eq', tex: 'RE_c = \\mathrm{PWF} \\times \\sum_{i=0}^{m} (RS)_i \\times (Q_{rm})_i' },

        { type: 'h4', text: 'B.3.2 Social cost' },
        ...RUC_BLOCK('dr', 'Road user cost due to rerouting of vehicles during demolition for reconstruction'),
        ...RUC_BLOCK('re', 'Road user cost due to rerouting of vehicles during reconstruction'),
        ...RUC_BLOCK('df', 'Road user cost due to rerouting of vehicles during demolition at the end of life'),

        { type: 'h4', text: 'B.3.3 Environmental cost' },
        { type: 'p', text: 'Carbon Emission Cost', bold: true },
        { type: 'li', text: 'Carbon emission cost due to demolition and disposal for reconstruction' },
        { type: 'eq', tex: '\\mathrm{DR}_{\\mathrm{EC}} = \\mathrm{PWF} \\times P_{\\mathrm{IECd}}' },
        { type: 'li', text: 'Carbon emission cost due to rerouting of vehicles during demolition for reconstruction' },
        { type: 'eq', tex: VEC_RE('VEC}_{\\mathrm{DR') },
        { type: 'li', text: 'Carbon emission cost due to reconstruction' },
        { type: 'eq', tex: '\\mathrm{REC}_{\\mathrm{EC}} = \\mathrm{PWF} \\times \\mathrm{IEC}' },
        { type: 'li', text: 'Carbon emission cost due to rerouting of vehicles during reconstruction' },
        { type: 'eq', tex: VEC_RE('VEC}_{\\mathrm{REC') },
        { type: 'li', text: 'Carbon emission cost due to demolition and disposal at end of life' },
        { type: 'eq', tex: '\\mathrm{DF}_{\\mathrm{EC}} = \\mathrm{PWF} \\times P_{\\mathrm{IECd}}' },
        { type: 'li', text: 'Carbon emission cost due to rerouting of vehicles during demolition at end of life' },
        { type: 'eq', tex: VEC_RE('VEC}_{\\mathrm{DF') },
    ],
};

/**
 * Desktop-equivalent LaTeX document generator for the 3psLCCA web report.
 *
 * Produces a complete LaTeX document string that mirrors the desktop Python
 * report (title page, ToC, input tables, LCCA results, Appendix A/B/C).
 * The output is compiled to PDF by the SwiftLaTeX WebAssembly engine in the
 * browser — no server, no CDN, no network requests.
 *
 * Package profiles:
 *   DESKTOP_REQUIRED_LATEX_PACKAGES — full list used by the Python desktop app
 *   STATIC_SWIFTLATEX_PACKAGES     — browser-compatible subset used here
 *
 * @see latexReportEngine.js  — calls this to build the payload for SwiftLaTeX
 * @see reportEngine.js       — top-level dispatcher (SwiftLaTeX → jsPDF fallback)
 */
import { SECTION_KEYS } from './reportSections.js';
import { APPENDIX_A_LATEX, APPENDIX_B_LATEX } from './desktopAppendices.js';

export const DESKTOP_REQUIRED_LATEX_PACKAGES = [
  ['inputenc', ['utf8']],
  ['fontenc', ['T1']],
  ['mathptmx'],
  ['microtype', ['protrusion=true', 'expansion=false']],
  ['geometry', ['a4paper', 'top=2.5cm', 'bottom=2.5cm', 'left=2.5cm', 'right=2.5cm']],
  ['setspace'],
  ['booktabs'],
  ['array'],
  ['longtable'],
  ['tabularx'],
  ['multirow'],
  ['makecell'],
  ['graphicx'],
  ['float'],
  ['pdflscape'],
  ['adjustbox'],
  ['caption'],
  ['amsmath'],
  ['xcolor'],
  ['colortbl'],
  ['enumitem'],
  ['fancyhdr'],
  ['lastpage'],
  ['titlesec'],
  ['etoolbox'],
  ['hyperref', ['hidelinks', 'hypertexnames=false']],
  ['bookmark'],
  ['tikz'],
  ['tcolorbox', ['most']],
];

export const STATIC_SWIFTLATEX_PACKAGES = [
  ['inputenc', ['utf8']],
  ['booktabs'],
  ['array'],
  ['longtable'],
  ['tabularx'],
  ['graphicx'],
  ['pdflscape'],
  ['adjustbox'],
  ['caption'],
  ['amsmath'],
  ['xcolor'],
  ['fancyhdr'],
  ['hyperref', ['hidelinks', 'hypertexnames=false']],
  ['bookmark'],
  ['tikz'],
  ['tcolorbox'],
];

const isEnabled = (selections, key) => selections?.[key] !== false;

export const escapeLatex = (input) => String(input ?? '—')
  .replaceAll('\\', String.raw`\textbackslash{}`)
  .replaceAll('&', String.raw`\&`)
  .replaceAll('%', String.raw`\%`)
  .replaceAll('$', String.raw`\$`)
  .replaceAll('#', String.raw`\#`)
  .replaceAll('_', String.raw`\_`)
  .replaceAll('{', String.raw`\{`)
  .replaceAll('}', String.raw`\}`)
  .replaceAll('~', String.raw`\textasciitilde{}`)
  .replaceAll('^', String.raw`\textasciicircum{}`);

const packageLine = ([name, options]) => (
  options?.length
    ? String.raw`\usepackage[${options.join(',')}]` + `{${name}}`
    : String.raw`\usepackage` + `{${name}}`
);

const section = (title) => String.raw`\section{${escapeLatex(title)}}`;
const subsection = (title) => String.raw`\subsection{${escapeLatex(title)}}`;
const subsubsection = (title) => String.raw`\subsubsection{${escapeLatex(title)}}`;
const clearpage = () => String.raw`\clearpage`;

const currencyNumber = (value) => Number(value || 0).toLocaleString('en-IN', {
  maximumFractionDigits: 2,
});

const rowsToLongtable = (caption, label, headers, rows, { size = String.raw`\footnotesize` } = {}) => {
  if (!rows?.length) {
    return [
      String.raw`\begin{quote}`,
      String.raw`\textit{No data available for ${escapeLatex(caption)}.}`,
      String.raw`\end{quote}`,
    ].join('\n');
  }

  const columnSpec = headers
    .map(() => String.raw`>{\raggedright\arraybackslash}X`)
    .join('');

  const headerLine = headers.map((header) => String.raw`\textbf{${escapeLatex(header)}}`).join(' & ') + String.raw`\\`;
  const bodyLines = rows.map((row) => row.map(escapeLatex).join(' & ') + String.raw`\\`);

  return [
    String.raw`\begin{table}[h!]`,
    String.raw`\centering`,
    size,
    String.raw`\caption{${escapeLatex(caption)}}\label{${label}}`,
    String.raw`\begin{tabularx}{\linewidth}{${columnSpec}}`,
    String.raw`\toprule`,
    headerLine,
    String.raw`\midrule`,
    ...bodyLines,
    String.raw`\bottomrule`,
    String.raw`\end{tabularx}`,
    String.raw`\normalsize`,
    String.raw`\end{table}`,
  ].join('\n');
};

const groupedConstructionTables = (report) => {
  const groups = new Map();
  for (const row of report.constructionRows || []) {
    const key = row.category || 'Structure Work';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push([
      row.component,
      row.material,
      row.quantity,
      row.unit,
      row.rate,
      row.source,
      currencyNumber(row.total),
    ]);
  }

  if (!groups.size) {
    return rowsToLongtable('Structure Work Data', 'tab:structure_work_data', ['Material', 'Quantity'], []);
  }

  return Array.from(groups.entries()).map(([category, rows], index) => rowsToLongtable(
    `Structure Work Data: ${category}`,
    `tab:structure_work_data_${index + 1}`,
    ['Component', 'Material', 'Quantity', 'Unit', 'Rate/Unit', 'Rate Source', `Total (${report.project.currency})`],
    rows,
  )).join('\n\n');
};

const titlePage = (report) => [
  String.raw`\begin{titlepage}`,
  String.raw`\thispagestyle{empty}`,
  String.raw`\definecolor{eco}{HTML}{9E9EFF}\definecolor{env}{HTML}{8AD400}\definecolor{soc}{HTML}{FF5A2A}`,
  String.raw`\definecolor{ink}{HTML}{1E2630}\definecolor{slate}{HTML}{45505E}\definecolor{body}{HTML}{2B2B2B}`,
  String.raw`\definecolor{hair}{HTML}{D9DDE3}\definecolor{ftxt}{HTML}{8A8AA0}\definecolor{cardbg}{HTML}{F5F6F8}`,
  String.raw`\newcommand{\tribar}[1]{\noindent\makebox[\textwidth]{\textcolor{eco}{\rule{0.3333\textwidth}{#1}}\textcolor{env}{\rule{0.3333\textwidth}{#1}}\textcolor{soc}{\rule{0.3334\textwidth}{#1}}}}`,
  String.raw`\newcommand{\SecHead}[1]{{\large\bfseries\color{ink}#1}}`,
  String.raw`\begin{tikzpicture}[remember picture,overlay]`,
  String.raw`  \fill[eco] (current page.north west) rectangle ($(current page.north west)!0.3333!(current page.south west)+(0.6cm,0)$);`,
  String.raw`  \fill[env] ($(current page.north west)!0.3333!(current page.south west)$) rectangle ($(current page.north west)!0.6667!(current page.south west)+(0.6cm,0)$);`,
  String.raw`  \fill[soc] ($(current page.north west)!0.6667!(current page.south west)$) rectangle ($(current page.south west)+(0.6cm,0)$);`,
  String.raw`\end{tikzpicture}`,
  String.raw`\vspace*{0.45cm}`,
  String.raw`\noindent\begin{minipage}[c]{0.48\textwidth}\raggedright`,
  String.raw`\fbox{\parbox[c][1.5cm][c]{4cm}{\centering [Agency Logo]}}`,
  String.raw`\end{minipage}\hfill`,
  String.raw`\begin{minipage}[c]{0.48\textwidth}\raggedleft`,
  String.raw`\fbox{\parbox[c][1.0cm][c]{4cm}{\centering [3psLCCA Logo]}}`,
  String.raw`\end{minipage}`,
  String.raw`\vspace{0.45cm}`,
  String.raw`\noindent{\fontsize{24}{28}\selectfont\bfseries\color{ink}Bridge Life Cycle Cost Analysis Report\par}`,
  String.raw`\vspace{3mm}`,
  String.raw`\tribar{1.6pt}`,
  String.raw`\vspace{0.3cm}`,
  String.raw`\noindent\fbox{\begin{minipage}{0.94\textwidth}`,
  String.raw`\SecHead{Project information}\par\vspace{2mm}`,
  String.raw`\renewcommand{\arraystretch}{1.3}`,
  String.raw`\noindent\begin{tabular}{@{}>{\bfseries\color{slate}}p{3.6cm}>{\color{body}}p{\dimexpr\linewidth-4.0cm\relax}@{}}`,
  String.raw`Project name: & ${escapeLatex(report.project.name)} \\`,
  String.raw`Project code: & ${escapeLatex(report.project.code)} \\`,
  String.raw`Project description: & ${escapeLatex(report.project.description)} \\`,
  String.raw`Prepared using: & 3psLCCA (\href{https://osdag.iitb.ac.in/3pslcca}{osdag.iitb.ac.in/3pslcca}) \\`,
  String.raw`\end{tabular}`,
  String.raw`\end{minipage}}`,
  String.raw`\vfill`,
  String.raw`\noindent\begin{minipage}[t]{0.47\textwidth}`,
  String.raw`{\bfseries Evaluated by}\\[2mm]`,
  String.raw`Name: ${escapeLatex(report.project.evaluator)}\\`,
  String.raw`Organization: ${escapeLatex(report.project.agency)}\\`,
  String.raw`Address:\\`,
  String.raw`Email:\\`,
  String.raw`Phone:\\[6mm]`,
  String.raw`Signature`,
  String.raw`\end{minipage}\hfill`,
  String.raw`\begin{minipage}[t]{0.47\textwidth}`,
  String.raw`{\bfseries Reviewed by}\\[2mm]`,
  String.raw`Name: ${escapeLatex(report.project.reviewer)}\\`,
  String.raw`Organization:\\`,
  String.raw`Address:\\`,
  String.raw`Email:\\`,
  String.raw`Phone:\\[6mm]`,
  String.raw`Signature`,
  String.raw`\end{minipage}`,
  String.raw`\vfill`,
  String.raw`\noindent{\color{hair}\rule{\textwidth}{0.6pt}}\\[3mm]`,
  String.raw`\noindent\begin{minipage}[t]{0.5\textwidth}`,
  String.raw`{\bfseries\color{slate}3psLCCA}\\`,
  String.raw`{\bfseries\color{slate}Osdag, IIT Bombay}\\`,
  String.raw`\href{https://osdag.iitb.ac.in/3pslcca}{osdag.iitb.ac.in/3pslcca}`,
  String.raw`\end{minipage}\hfill`,
  String.raw`\begin{minipage}[t]{0.46\textwidth}`,
  String.raw`{\footnotesize\color{ftxt}Generated using 3psLCCA. The software is provided without any warranty, express or implied. The life cycle cost analysis (LCCA) results depend on user-provided inputs. The evaluating agency is solely responsible for the accuracy of the input data and for any use of the results.\par}`,
  String.raw`\end{minipage}`,
  String.raw`\end{titlepage}`,
].join('\n');

const frontMatter = () => [
  clearpage(),
  String.raw`\pagenumbering{roman}`,
  String.raw`\tableofcontents`,
  clearpage(),
  String.raw`\addcontentsline{toc}{section}{List of Tables}`,
  String.raw`\listoftables`,
  clearpage(),
  String.raw`\addcontentsline{toc}{section}{List of Figures}`,
  String.raw`\listoffigures`,
  clearpage(),
  String.raw`\pagenumbering{arabic}`,
].join('\n');

const introduction = () => [
  section('Introduction to LCCA'),
  'Life Cycle Cost Assessment evaluates the bridge across economic, social, and environmental cost components over the selected analysis period.',
  String.raw`\begin{figure}[h!]`,
  String.raw`\centering`,
  String.raw`\begin{tikzpicture}[scale=0.92]`,
  String.raw`\draw[rounded corners, thick, fill=blue!5] (0,0) rectangle (12,4);`,
  String.raw`\node[font=\bfseries] at (6,3.55) {3PS Life Cycle Cost Assessment};`,
  String.raw`\node[draw, rounded corners, fill=blue!12, minimum width=2.7cm, minimum height=0.8cm] at (2.2,2.2) {Economic};`,
  String.raw`\node[draw, rounded corners, fill=green!15, minimum width=2.7cm, minimum height=0.8cm] at (6,2.2) {Environmental};`,
  String.raw`\node[draw, rounded corners, fill=orange!15, minimum width=2.7cm, minimum height=0.8cm] at (9.8,2.2) {Social};`,
  String.raw`\node[font=\small] at (6,0.9) {Initial Stage \quad Use Stage \quad Reconstruction \quad End-of-Life};`,
  String.raw`\end{tikzpicture}`,
  String.raw`\caption{3PS Life Cycle Cost Assessment}`,
  String.raw`\end{figure}`,
].join('\n\n');

const inputData = (report, selections) => {
  const parts = [clearpage(), section('Input data')];

  if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_BRIDGE_DESC)) {
    parts.push(subsection('Bridge geometry and description'));
    parts.push(rowsToLongtable('Bridge Data Summary', 'tab:bridge_data', ['Bridge Identification', 'Value'], report.bridgeRows));
  }

  if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_FINANCIAL)) {
    parts.push(subsection('Financial inputs'));
    parts.push(rowsToLongtable('Financial Data Summary', 'tab:financial_data', ['Financial Data', 'Value', 'Source'], report.financialRows));
  }

  if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_CONSTRUCTION)) {
    parts.push(subsection('Construction data'));
    parts.push(groupedConstructionTables(report));
  }

  if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_USE_STAGE)) {
    parts.push(subsection('Maintenance data'));
    parts.push(rowsToLongtable('Maintenance Data Summary', 'tab:maintenance_data', ['Activity', 'Cost', 'Frequency', 'Duration'], report.maintenanceRows));
  }

  if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_ROAD_TRAFFIC)) {
    parts.push(subsection('Traffic data'));
    if (report.trafficMode === 'GLOBAL') {
      parts.push(subsubsection('Traffic and Road Data'));
      parts.push(rowsToLongtable('Traffic and Road Data', 'tab:traffic_and_road_data', ['Parameter', 'Value'], report.globalTrafficRows));
    } else {
      parts.push(subsubsection('Traffic and Road Data'));
      parts.push(rowsToLongtable('Road Data', 'tab:road_data', ['Parameter', 'Value'], report.roadRows));
      if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_AVG_TRAFFIC)) {
        parts.push(subsubsection('Average Daily Traffic'));
        parts.push(rowsToLongtable('Vehicle Traffic Data', 'tab:vehicle_data', ['Vehicle', 'Vehicles/day', 'Accident %', 'PWR'], report.vehicleRows));
      }
      if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_PEAK_HOUR) && report.peakRows.length) {
        parts.push(subsubsection('Peak Hour Distribution'));
        parts.push(rowsToLongtable('Peak Hour Distribution', 'tab:peak_hour_distribution', ['Peak period', 'Daily traffic fraction'], report.peakRows));
      }
    }
  }

  parts.push(subsection('Environmental input data'));
  if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_SOCIAL_CARBON)) {
    parts.push(subsubsection('Social Cost of Carbon'));
    parts.push(rowsToLongtable('Social Cost Data', 'tab:social_cost_carbon', ['Parameter', 'Value'], report.socialCarbonRows));
  }
  if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_MATERIAL_EMISSION)) {
    parts.push(subsubsection('Material Emission Factors'));
    parts.push(rowsToLongtable(
      'Material Emissions',
      'tab:material_emissions',
      ['Category', 'Component', 'Material', 'Quantity', 'Unit', 'Emission Factor', 'Total kgCO2e'],
      report.materialIncluded.map((row) => [
        row.category, row.component, row.material, row.quantity, row.unit, row.emissionFactor, row.total,
      ]),
    ));
  }
  if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_TRANSPORT_EMISSION)) {
    parts.push(subsubsection('Transport Emissions'));
    parts.push(rowsToLongtable(
      'Transport Emissions',
      'tab:transport_emissions',
      ['Vehicle', 'Origin', 'Distance km', 'Trips', 'Emissions kgCO2e'],
      report.transportRows.map((row) => [row.vehicle, row.origin, row.distance, row.trips, row.emissions]),
    ));
  }
  if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_ONSITE_EMISSION)) {
    parts.push(subsubsection('Machinery and Equipment Emissions'));
    parts.push(rowsToLongtable(
      'Machinery and Equipment Emissions',
      'tab:machinery_emissions',
      ['Equipment', 'Source', 'Consumption', 'Days', 'Factor', 'Emissions kgCO2e'],
      report.machineryRows.map((row) => [row.equipment, row.source, row.consumption, row.days, row.factor, row.emissions]),
    ));
  }
  if (report.trafficMode !== 'GLOBAL' && isEnabled(selections, SECTION_KEYS.KEY_SHOW_VEHICLE_EMISSION)) {
    parts.push(subsubsection('Traffic Diversion Emissions'));
    parts.push(rowsToLongtable('Traffic Diversion Emissions', 'tab:diversion_emissions', ['Parameter', 'Value'], report.diversionRows));
  }

  if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_RECYCLING)) {
    parts.push(subsection('Recycling data'));
    parts.push(rowsToLongtable('Recycling Included Materials', 'tab:recycling_included', ['Material', 'Recovery %', 'Scrap Rate', 'Recovered Value'], report.recyclingIncluded));
    parts.push(rowsToLongtable('Recycling Excluded Materials', 'tab:recycling_excluded', ['Material', 'Reason'], report.recyclingExcluded));
  }

  return parts.join('\n\n');
};

const resultRows = (results = {}, computedData = {}) => {
  const rows = [];
  const stageLabels = {
    initial_stage: 'Initial Stage',
    use_stage: 'Use Stage',
    reconstruction: 'Reconstruction Stage',
    end_of_life: 'End-of-Life Stage',
  };

  for (const [stageKey, stage] of Object.entries(results || {})) {
    if (!stage || typeof stage !== 'object' || Array.isArray(stage)) continue;
    for (const [pillar, values] of Object.entries(stage)) {
      if (!values || typeof values !== 'object' || Array.isArray(values)) continue;
      for (const [metric, value] of Object.entries(values)) {
        const amount = Number(value);
        if (!Number.isFinite(amount)) continue;
        rows.push([
          stageLabels[stageKey] || stageKey.replaceAll('_', ' '),
          pillar,
          metric.replaceAll('_', ' '),
          currencyNumber(amount),
        ]);
      }
    }
  }

  if (computedData?.total !== undefined) {
    rows.push(['Total', 'All pillars', 'Total life cycle cost', currencyNumber(computedData.total)]);
  }
  return rows;
};

const sumNumbers = (value, key = '') => {
  if (typeof value === 'number') return key === 'total_scrap_value' ? -value : value;
  if (Array.isArray(value)) return value.reduce((sum, item) => sum + sumNumbers(item), 0);
  if (value && typeof value === 'object') {
    return Object.entries(value).reduce((sum, [childKey, child]) => sum + sumNumbers(child, childKey), 0);
  }
  return 0;
};

const summaryText = (results = {}) => {
  const stages = [
    ['initial_stage', 'Initial stage'],
    ['use_stage', 'Use stage'],
    ['reconstruction', 'Reconstruction'],
    ['end_of_life', 'End-of-life'],
  ].map(([key, label]) => [label, sumNumbers(results[key] || {})]);

  const pillars = ['economic', 'environmental', 'social'].map((pillar) => [
    pillar[0].toUpperCase() + pillar.slice(1),
    Object.values(results || {}).reduce((sum, stage) => sum + sumNumbers(stage?.[pillar] || {}), 0),
  ]);

  const grandTotal = stages.reduce((sum, [, value]) => sum + value, 0);
  const [stageLabel, stageValue] = stages.reduce((best, item) => (item[1] > best[1] ? item : best), ['', 0]);
  const [pillarLabel, pillarValue] = pillars.reduce((best, item) => (item[1] > best[1] ? item : best), ['', 0]);
  const stagePct = grandTotal ? ((stageValue / grandTotal) * 100).toFixed(2) : '';
  const pillarPct = grandTotal ? ((pillarValue / grandTotal) * 100).toFixed(2) : '';

  return [
    clearpage(),
    section('Summary and conclusions'),
    'The LCCA results indicate the relative contribution of construction, road user, and environmental costs, supporting informed and sustainable bridge planning decisions.',
    stageLabel
      ? `The most contributing stage of the life cycle is \\textbf{${escapeLatex(stageLabel)}} contributing to around \\textbf{${stagePct}\\%} of the total life cycle cost.`
      : 'The most contributing stage of the life cycle is not available for this calculation.',
    pillarLabel
      ? `The most contributing pillar is \\textbf{${escapeLatex(pillarLabel)}} contributing to around \\textbf{${pillarPct}\\%} of the total life cycle cost.`
      : 'The most contributing pillar is not available for this calculation.',
  ].join('\n\n');
};

const stripDesktopIncompatibleLatex = (latex) => latex
  .replaceAll(String.raw`\pagestyle{empty}`, '')
  .replaceAll(String.raw`\appendix`, '')
  .replaceAll(String.raw`\begin{table}[H]`, String.raw`\begin{table}[h!]`)
  .replaceAll(String.raw`\begin{figure}[H]`, String.raw`\begin{figure}[h!]`)
  .replaceAll(String.raw`\begin{itemize}[leftmargin=*]`, String.raw`\begin{itemize}`)
  .replaceAll(String.raw`|p{3cm}|p{13.5cm}|`, String.raw`|p{0.18\linewidth}|p{0.72\linewidth}|`)
  .replaceAll(String.raw`\makebox[13.5cm][c]`, String.raw`\makebox[\linewidth][c]`)
  .replaceAll(String.raw`\setlength{\tabcolsep}{6pt}`, String.raw`\setlength{\tabcolsep}{3pt}`)
  .replaceAll(String.raw`\renewcommand{\arraystretch}{2.80}`, String.raw`\renewcommand{\arraystretch}{1.45}`)
  .replaceAll(String.raw`\renewcommand{\arraystretch}{1.9}`, String.raw`\renewcommand{\arraystretch}{1.35}`)
  .replaceAll(String.raw`\begin{aligned}`, String.raw`\begin{array}{rl}`)
  .replaceAll(String.raw`\end{aligned}`, String.raw`\end{array}`);

const cleanAppendixHeadings = (latex) => stripDesktopIncompatibleLatex(latex)
  .replaceAll(
    String.raw`\section*{\fontsize{14pt}{16pt}\selectfont\bfseries Appendix A: Assumptions}`,
    String.raw`\section*{Appendix A: Assumptions}`,
  )
  .replaceAll(
    String.raw`\section*{\fontsize{14pt}{16pt}\selectfont\bfseries Appendix B: Calculation Methodology}`,
    String.raw`\section*{Appendix B: Calculation methodology}`,
  )
  .replaceAll(
    String.raw`\addcontentsline{toc}{section}{Appendix B: Calculation Methodology}`,
    String.raw`\addcontentsline{toc}{section}{Appendix B: Calculation methodology}`,
  )
  .replaceAll(String.raw`{\fontsize{13pt}{15pt}\selectfont\bfseries B.`, String.raw`{\bfseries B.`);

const appendixCounter = (letter) => String.raw`\setcounter{section}{0}\renewcommand{\thesection}{${letter}.\arabic{section}}`;

const appendixAContent = () => {
  const marker = 'Appendix A: Assumptions';
  const start = APPENDIX_A_LATEX.indexOf(marker);
  const sectionStart = APPENDIX_A_LATEX.lastIndexOf(String.raw`\section*`, start);
  const content = sectionStart >= 0 ? APPENDIX_A_LATEX.slice(sectionStart) : APPENDIX_A_LATEX;
  const duplicate = content.indexOf(String.raw`\section*`, String.raw`\section*`.length);
  const firstAppendix = duplicate >= 0 ? content.slice(0, duplicate) : content;
  return cleanAppendixHeadings(firstAppendix);
};

const appendixBContent = () => cleanAppendixHeadings(APPENDIX_B_LATEX)
  .replaceAll(
    String.raw`|p{0.18\linewidth}|p{0.72\linewidth}|`,
    String.raw`|>{\fontsize{9pt}{11pt}\selectfont}p{0.18\linewidth}|>{\fontsize{9pt}{11pt}\selectfont}p{0.72\linewidth}|`,
  )
  .replace(/\\caption\*\{\\textit\{Table B-\d+\s+([^{}]+?)\}\}/g, String.raw`\caption{$1}`);

const appendices = (report) => [
  clearpage(),
  appendixCounter('A'),
  appendixAContent(),
  clearpage(),
  appendixCounter('B'),
  appendixBContent(),
  clearpage(),
  appendixCounter('C'),
  String.raw`\section*{Appendix C: Miscellaneous data}`,
  String.raw`\addcontentsline{toc}{section}{Appendix C: Miscellaneous data}`,
  rowsToLongtable('Calculation Provenance', 'tab:calculation_provenance', ['Field', 'Value'], [
    ['Calculation engine', report.calculation.source],
    ['3psLCCA-core version', report.calculation.coreVersion],
    ['Pyodide version', report.calculation.pyodideVersion],
    ['Calculated at', report.calculation.calculatedAt],
  ]),
].join('\n\n');

const lccaResultsSection = (results, computedData) => [
  clearpage(),
  section('LCCA results'),
  subsection('Life cycle cost results'),
  String.raw`\noindent Table~\ref{tab:lcca_results} presents a comprehensive summary of the life cycle cost analysis results, expressed as present values. The costs are organised by life cycle stage and further broken down by sustainability pillar: Economic, Environmental, and Social.`,
  rowsToLongtable(
    'Life Cycle Cost Analysis Results',
    'tab:lcca_results',
    ['Stage', 'Pillar', 'Metric', 'Value'],
    resultRows(results, computedData),
  ),
].join('\n\n');

export const buildDesktopStyleLatexReport = ({
  report,
  results = {},
  computedData = {},
  selections = {},
} = {}) => {
  if (!report) {
    throw new Error('A report model is required to build desktop-style LaTeX.');
  }

  const parts = [];
  if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_TITLE_PAGE)) parts.push(titlePage(report));
  parts.push(frontMatter());
  if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_INTRODUCTION)) parts.push(introduction());
  parts.push(inputData(report, selections));
  if (isEnabled(selections, SECTION_KEYS.KEY_SHOW_LCCA_RESULTS)) parts.push(lccaResultsSection(results, computedData));
  parts.push(summaryText(results));
  parts.push(appendices(report));

  return [
    String.raw`\documentclass[12pt,a4paper]{article}`,
    ...STATIC_SWIFTLATEX_PACKAGES.map(packageLine),
    String.raw`\usetikzlibrary{calc}`,
    String.raw`\captionsetup{font=small, labelfont=bf, labelsep=period, skip=4pt}`,
    String.raw`\setlength{\oddsidemargin}{0mm}`,
    String.raw`\setlength{\evensidemargin}{0mm}`,
    String.raw`\setlength{\topmargin}{-10mm}`,
    String.raw`\setlength{\textwidth}{160mm}`,
    String.raw`\setlength{\textheight}{245mm}`,
    String.raw`\setlength{\headheight}{14pt}`,
    String.raw`\setlength{\tabcolsep}{2pt}`,
    String.raw`\hbadness=10000`,
    String.raw`\hfuzz=100pt`,
    String.raw`\emergencystretch=3em`,
    String.raw`\linespread{1.05}`,
    String.raw`\setlength{\parskip}{6pt}`,
    String.raw`\setlength{\parindent}{0pt}`,
    String.raw`\fancyhf{}`,
    String.raw`\renewcommand{\headrulewidth}{0.4pt}`,
    String.raw`\renewcommand{\footrulewidth}{0.4pt}`,
    String.raw`\fancyhead[L]{\small\nouppercase{\leftmark}}`,
    String.raw`\fancyhead[R]{\small 3PS LCCA}`,
    String.raw`\fancyfoot[C]{\small Page~\thepage}`,
    String.raw`\AtBeginDocument{\pagestyle{fancy}}`,
    String.raw`\DeclareUnicodeCharacter{20B9}{Rs.}`,
    String.raw`\DeclareUnicodeCharacter{2082}{\textsubscript{2}}`,
    String.raw`\DeclareUnicodeCharacter{2013}{--}`,
    String.raw`\DeclareUnicodeCharacter{2014}{--}`,
    String.raw`\providecommand{\textsubscript}[1]{$_{\mathrm{#1}}$}`,
    String.raw`\DeclareFontSubstitution{TS1}{cmr}{m}{n}`,
    String.raw`\begin{document}`,
    String.raw`\small`,
    ...parts,
    String.raw`\end{document}`,
  ].join('\n\n');
};

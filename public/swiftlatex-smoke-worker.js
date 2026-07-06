/* global importScripts */

const DEFAULT_SWIFTLATEX_BASE = './vendor/swiftlatex/';
const REMOTE_TEXLIVE_ENDPOINT = 'https://texlive2.swiftlatex.com/';

const ONE_PIXEL_PNG = Uint8Array.from(
  atob('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGOQq7gDAAIqAXNmXx0SAAAAAElFTkSuQmCC'),
  (character) => character.charCodeAt(0),
);

const tinyTex = String.raw`
\documentclass[12pt,a4paper]{article}
\usepackage{graphicx}
\begin{document}
\section*{SwiftLaTeX Browser Smoke Test}
This PDF was compiled inside a browser worker using SwiftLaTeX PdfTeX WebAssembly.

\medskip
\noindent Static asset proof image:
\includegraphics[width=0.06\linewidth]{swiftlatex-proof.png}
\end{document}
`;

const compatibilityTex = String.raw`
\documentclass[12pt,a4paper]{article}
\usepackage{booktabs}
\usepackage{array}
\usepackage{longtable}
\usepackage{tabularx}
\usepackage{graphicx}
\usepackage{pdflscape}
\usepackage{adjustbox}
\usepackage{caption}
\usepackage{xcolor}
\usepackage{fancyhdr}
\usepackage[hidelinks,hypertexnames=false]{hyperref}
\usepackage{bookmark}
\usepackage{tikz}
\usepackage{tcolorbox}
\usetikzlibrary{calc}

\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{SwiftLaTeX Compatibility Smoke}
\fancyfoot[C]{Page~\thepage}

\begin{document}
\tableofcontents
\listoftables
\listoffigures
\clearpage

\section{Desktop Package Compatibility}
This document intentionally uses the main packages required by the desktop 3psLCCA report.

\begin{figure}[h]
\centering
\includegraphics[width=0.06\linewidth]{swiftlatex-proof.png}
\caption{In-memory PNG asset written to SwiftLaTeX}
\end{figure}

\subsection{Longtable}
\begin{longtable}{>{\raggedright\arraybackslash}p{0.45\linewidth}>{\raggedleft\arraybackslash}p{0.35\linewidth}}
\caption{Desktop-style longtable smoke test}\label{tab:longtable-smoke}\\
\toprule
Field & Value\\
\midrule
Calculation engine & Browser LaTeX WebAssembly\\
Report family & 3psLCCA desktop-style report\\
\bottomrule
\end{longtable}

\subsection{Boxes and TikZ}
\begin{tcolorbox}[colback=blue!3,colframe=blue!45!black,title=Report note]
If this box and the figure render, SwiftLaTeX handled the desktop-style package subset.
\end{tcolorbox}

\begin{center}
\begin{tikzpicture}
\draw[fill=blue!12,draw=blue!55!black] (0,0) rectangle (5,1);
\node at (2.5,0.5) {SwiftLaTeX POC};
\end{tikzpicture}
\end{center}

\end{document}
`;

const post = (type, payload = {}) => {
  self.postMessage({ type, ...payload });
};

const configureTexliveEndpoint = (engine, endpoint) => {
  if (!endpoint || !engine.latexWorker) return;
  engine.latexWorker.postMessage({ cmd: 'settexliveurl', url: endpoint });
};

self.onmessage = async (event) => {
  if (event.data?.type !== 'compile') return;

  const startedAt = performance.now();
  const swiftlatexBase = event.data.swiftlatexBase || DEFAULT_SWIFTLATEX_BASE;
  const swiftlatexBaseUrl = new URL(swiftlatexBase, self.location.href);
  const texliveMode = event.data.texliveMode || 'local';
  const texliveEndpoint = texliveMode === 'remote'
    ? REMOTE_TEXLIVE_ENDPOINT
    : (event.data.texliveEndpoint || new URL('texlive/', swiftlatexBaseUrl).href);
  const documentKind = event.data.documentKind || 'compatibility';

  try {
    post('status', { message: 'Loading SwiftLaTeX PdfTeX WebAssembly engine...' });
    self.SWIFTLATEX_ENGINE_PATH = new URL('swiftlatexpdftex.js', swiftlatexBaseUrl).href;
    importScripts(new URL('PdfTeXEngine.js', swiftlatexBaseUrl).href);

    const EngineClass = self.PdfTeXEngine || self.exports?.PdfTeXEngine;
    if (!EngineClass) {
      throw new Error('SwiftLaTeX PdfTeXEngine was not exposed by the vendored script.');
    }

    const engine = new EngineClass();
    await engine.loadEngine();
    configureTexliveEndpoint(engine, texliveEndpoint);

    post('status', {
      message: texliveMode === 'remote'
        ? 'Using remote SwiftLaTeX TeXLive endpoint for this manual compatibility run.'
        : 'Using local/static TeXLive endpoint. Missing files prove static package bundling is not solved yet.',
    });

    post('status', { message: 'Compiling SwiftLaTeX format from local/static TeX files...' });
    const formatResult = await engine.compileFormat();
    if (formatResult?.status !== 0 || !formatResult?.pdf) {
      post('error', {
        status: formatResult?.status ?? 1,
        log: formatResult?.log || 'SwiftLaTeX did not return a format-generation log.',
        texliveMode,
        texliveEndpoint,
      });
      return;
    }
    engine.writeMemFSFile('swiftlatexpdftex.fmt', formatResult.pdf);

    engine.writeMemFSFile('swiftlatex-proof.png', ONE_PIXEL_PNG);
    engine.writeMemFSFile(
      'main.tex',
      documentKind === 'tiny' ? tinyTex : compatibilityTex,
    );
    engine.setEngineMainFile('main.tex');

    post('status', { message: 'Compiling LaTeX document...' });
    const result = await engine.compileLaTeX();
    engine.closeWorker();

    const elapsedMs = Math.round(performance.now() - startedAt);
    if (result.status !== 0 || !result.pdf) {
      post('error', {
        status: result.status,
        log: result.log || 'No SwiftLaTeX log was returned.',
        elapsedMs,
        texliveMode,
        texliveEndpoint,
      });
      return;
    }

    post('success', {
      pdf: result.pdf,
      log: result.log || '',
      elapsedMs,
      texliveMode,
      texliveEndpoint,
      documentKind,
    });
  } catch (error) {
    post('error', {
      status: -1,
      message: error?.message || String(error),
      stack: error?.stack || '',
      texliveMode,
      texliveEndpoint,
    });
  }
};

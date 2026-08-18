from __future__ import annotations

import re

from pylatex.utils import escape_latex

from ..SETTINGS import LATEX_FONT_SIZE, REQUIRED_LATEX_PACKAGES
from ..SETTINGS import LATEX_FONT_SIZE, REQUIRED_LATEX_PACKAGES, LATEX_TABLE_COLUMN_BG_ENABLED, LATEX_TABLE_COLUMN_BG_COLORS

from datetime import date


EMDASH = r"\textemdash"
generated_date = date.today().strftime("%d-%m-%Y")

def _generate_package_imports() -> list[str]:
    lines = []
    for pkg, options in REQUIRED_LATEX_PACKAGES.items():
        if options:
            lines.append(rf"\usepackage[{','.join(options)}]{{{pkg}}}")
        else:
            lines.append(rf"\usepackage{{{pkg}}}")
    return lines

V3_PREAMBLE = [
    r"\documentclass[12pt,a4paper]{article}",
    "",
    *(_generate_package_imports()),
    r"\usetikzlibrary{calc}",
    "",
    # ── Captions setup ────────────────────────────────────────────────────────
    r"\captionsetup{font=small, labelfont=bf, labelsep=period, skip=4pt}",
    
    # ── List setup ────────────────────────────────────────────────────────────
    r"\setlist{noitemsep, topsep=4pt, partopsep=0pt}",

    # ── Core layout overrides ─────────────────────────────────────────────────
    r"\setstretch{1.15}",              # comfortable reading spacing
    r"\setlength{\parskip}{6pt}",      # space between paragraphs
    r"\setlength{\parindent}{0pt}",    # no first-line indent (modern style)

    # ── Captions ──────────────────────────────────────────────────────────────
    r"\usepackage{caption}",
    r"\captionsetup{font=small, labelfont=bf, labelsep=period, skip=4pt}",


    # ── Headers / footers ─────────────────────────────────────────────────────
    r"\fancyhf{}",
    r"\providecommand{\ReportHeaderLogo}{}",
    r"\renewcommand{\headrulewidth}{0.4pt}",
    r"\renewcommand{\footrulewidth}{0.4pt}",
    r"\fancyhead[L]{\small\nouppercase{\leftmark}}",
    r"\fancyhead[R]{\IfFileExists{\ReportHeaderLogo}{\includegraphics[height=0.42cm]{\ReportHeaderLogo}}{\small 3PS LCCA}}",
    r"\fancyfoot[C]{\small Page~\thepage~of~\pageref*{LastPage}}",
    r"\AtBeginDocument{\pagestyle{fancy}}",

    # ── Section / ToC styling ─────────────────────────────────────────────────
    r"\titleformat{\section}{\Large\bfseries\color{blue!55!black}}{\thesection}{0.75em}{}",
    r"\titleformat{\subsection}{\large\bfseries\color{blue!55!black}}{\thesubsection}{0.75em}{}",
    r"\titleformat{\subsubsection}{\normalsize\bfseries\color{blue!55!black}}{\thesubsubsection}{0.75em}{}",
    r"\titlespacing*{\section}{0pt}{18pt}{8pt}",
    r"\titlespacing*{\subsection}{0pt}{14pt}{6pt}",
    r"\titlespacing*{\subsubsection}{0pt}{10pt}{4pt}",
    r"\renewcommand{\contentsname}{Table of Contents}",
    r"\renewcommand{\listtablename}{List of Tables}",
    r"\renewcommand{\listfigurename}{List of Figures}",

    # ── Unicode shorthands ────────────────────────────────────────────────────
    r"\DeclareUnicodeCharacter{20B9}{Rs.}",
    r"\DeclareUnicodeCharacter{2082}{\textsubscript{2}}",
    r"\DeclareUnicodeCharacter{2013}{--}",
    r"\DeclareUnicodeCharacter{2014}{--}",

    # ── Global table defaults ─────────────────────────────────────────────────
    r"\setlength{\tabcolsep}{4pt}",
    r"\renewcommand{\arraystretch}{1.18}",
    r"\setlength{\LTleft}{0pt}",
    r"\setlength{\LTright}{0pt}",
    r"\setlength{\LTcapwidth}{\textwidth}",
    r"\BeforeBeginEnvironment{tabular}{\begin{adjustbox}{max width=\linewidth}}",
    r"\AfterEndEnvironment{tabular}{\end{adjustbox}}",
    r"\AtBeginEnvironment{tabular}{\footnotesize}",
    r"\sloppy",
]




def apply_table_column_backgrounds(latex: str) -> str:
    if not LATEX_TABLE_COLUMN_BG_ENABLED or not latex:
        return latex

    def _shade_spec(spec: str) -> str:
        colors = LATEX_TABLE_COLUMN_BG_COLORS
        column_pattern = r"(?P<modifier>>\{[^{}]*\})?(?P<column>[lcr]|p\{[^{}]+\})"
        if "".join(spec.split()) == "lll":
            return spec
        if len(list(re.finditer(column_pattern, spec))) <= 2:
            return spec
        idx = 0

        def repl(match):
            nonlocal idx
            modifier = match.group("modifier") or ""
            column = match.group("column")
            color = colors[idx % len(colors)]
            idx += 1
            marker = r"\columncolor{" + color + r"}"
            if modifier:
                return modifier.replace(r">{", r">{" + marker, 1) + column
            return r">{" + marker + r"}" + column

        return re.sub(column_pattern, repl, spec)

    def _replace_begin_specs(text: str, env: str) -> str:
        pattern = r"\begin{" + env + r"}{"
        pos = 0
        out = []
        while True:
            start = text.find(pattern, pos)
            if start == -1:
                out.append(text[pos:])
                return "".join(out)
            spec_start = start + len(pattern)
            depth = 1
            i = spec_start
            while i < len(text) and depth:
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                i += 1
            if depth:
                out.append(text[pos:])
                return "".join(out)
            spec = text[spec_start:i - 1]
            out.append(text[pos:spec_start])
            out.append(_shade_spec(spec))
            out.append("}")
            pos = i

    return _replace_begin_specs(_replace_begin_specs(latex, "longtable"), "tabular")





def build_report_v3_document(body: str, logo_path: str = "") -> str:
    """Wrap report body in the V3 LaTeX document shell."""
    return "\n".join([
        *V3_PREAMBLE,
        r"\renewcommand{\ReportHeaderLogo}{" + logo_path + r"}",
        r"\begin{document}",
        LATEX_FONT_SIZE,
        body,
        r"\end{document}",
    ])


def title_page(project_name: str, logo_path: str = "") -> str:
    safe_project_name = escape_latex(project_name or "Unnamed Project")
    return "\n".join([
        r"\begin{titlepage}",
        r"\begin{flushright}",
        (
            r"\IfFileExists{" + logo_path + r"}"
            r"{\includegraphics[width=0.38\linewidth]{" + logo_path + r"}}{}"
            if logo_path
            else ""
        ),
        r"\end{flushright}",
        r"\vspace*{2cm}",
        r"\noindent{\color{blue!55!black}\rule{\linewidth}{1.2pt}}",
        r"\vspace{0.8cm}",
        r"\begin{flushright}",
        r"{\Huge\bfseries Software Generated Report\par}",
        r"\vspace{0.45cm}",
        r"{\LARGE Life Cycle Cost Assessment\par}",
        r"\vspace{0.8cm}",
        r"{\Large " + safe_project_name + r"\par}",
        r"\end{flushright}",
        r"\vspace{0.8cm}",
        r"\noindent{\color{blue!55!black}\rule{\linewidth}{0.8pt}}",
        r"\vfill",
        r"\begin{flushright}",
        r"{\small Generated on " + generated_date + r"\par}",
        r"\end{flushright}",
        r"\end{titlepage}",
    ])


def front_matter() -> str:
    """TOC, list of tables, and list of figures."""
    return "\n".join([
        r"\clearpage",
        r"\pagenumbering{roman}",
        r"\tableofcontents",
        r"\clearpage",
        r"\addcontentsline{toc}{section}{List of Tables}",
        r"\listoftables",
        r"\clearpage",
        r"\addcontentsline{toc}{section}{List of Figures}",
        r"\listoffigures",
        r"\clearpage",
        r"\pagenumbering{arabic}",
    ])


def section(title: str) -> str:
    return r"\section{" + escape_latex(title) + r"}"


def subsection(title: str) -> str:
    return r"\subsection{" + escape_latex(title) + r"}"


def subsubsection(title: str) -> str:
    return r"\subsubsection{" + escape_latex(title) + r"}"


def paragraph(text: str) -> str:
    return r"\par\medskip " + escape_latex(text) + r"\par\medskip"


def clearpage() -> str:
    return r"\clearpage"


def appendix_counter(letter: str) -> str:
    section_number = ord(letter.upper()) - ord("A") + 1
    lines = []
    if letter.upper() == "A":
        lines.append(r"\appendix")
    lines.extend([
        r"\setcounter{section}{" + str(section_number) + r"}",
        r"\setcounter{table}{0}",
        r"\setcounter{figure}{0}",
        r"\renewcommand{\thetable}{" + letter.upper() + r"-\arabic{table}}",
        r"\renewcommand{\thefigure}{" + letter.upper() + r"-\arabic{figure}}",
    ])
    return "\n".join(lines)


def format_value(value, decimals: int | None = None) -> str:
    if value in (None, ""):
        return EMDASH
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if decimals is not None:
        return f"{number:,.{decimals}f}"
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}".rstrip("0").rstrip(".")


def simple_table(
    caption: str,
    label: str,
    headers: list[str],
    rows: list[list],
    col_spec: str,
) -> str:
    if not rows:
        rows = [[EMDASH for _ in headers]]

    header = " & ".join(r"\textbf{" + escape_latex(h) + "}" for h in headers) + r" \\"
    body = [
        " & ".join(_cell(c) for c in row) + r" \\"
        for row in rows
    ]

    return "\n".join([
        r"\begin{longtable}{" + col_spec + r"}",
        r"\caption{" + escape_latex(caption) + r"}\label{" + label + r"}\\",
        r"\toprule",
        header,
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        header,
        r"\midrule",
        r"\endhead",
        r"\midrule",
        r"\multicolumn{" + str(len(headers)) + r"}{r}{\footnotesize\textit{continued on next page}} \\",
        r"\endfoot",
        r"\bottomrule",
        r"\endlastfoot",
        *body,
        r"\end{longtable}",
    ])


def wide_block(latex: str, size: str = r"\scriptsize") -> str:
    if not latex:
        return ""
    latex = latex.replace(r"\begin{landscape}", "").replace(r"\end{landscape}", "")
    return "\n".join([
        r"\begingroup",
        size,
        r"\centering",
        r"\setlength{\tabcolsep}{4pt}",
        r"\setlength{\LTleft}{\fill}",
        r"\setlength{\LTright}{\fill}",
        latex,
        r"\normalsize",
        r"\endgroup",
    ])


def _cell(value) -> str:
    if value in (None, ""):
        return EMDASH
    if value == EMDASH:
        return EMDASH
    return escape_latex(str(value))

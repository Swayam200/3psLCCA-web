from __future__ import annotations

import re

from ..lcca_report_builder import KEY_SHOW_APPENDIX_A, KEY_SHOW_APPENDIX_B
from ..appendix_A_content import APPENDIX_A_LATEX
from ..appendix_B_content import APPENDIX_B_LATEX
from ..latex_helpers import appendix_counter


def _strip_v3_incompatible_latex(latex: str) -> str:
    """Keep appendix content usable under both V3 and devmode document wrappers."""
    latex = latex.replace(r"\pagestyle{empty}", "")
    latex = latex.replace(r"\begin{table}[H]", r"\begin{table}[h!]")
    latex = latex.replace(r"\begin{figure}[H]", r"\begin{figure}[h!]")
    latex = re.sub(r"\\textcolor\{red\}\{(\\textit\{[^{}]*\})\}", r"\1", latex)
    latex = latex.replace(r"\begin{aligned}", r"\begin{array}{rl}")
    latex = latex.replace(r"\end{aligned}", r"\end{array}")
    latex = latex.replace(r"\begin{itemize}[leftmargin=*]", r"\begin{itemize}")
    latex = latex.replace(r"|p{3cm}|p{13.5cm}|", r"|p{0.18\linewidth}|p{0.72\linewidth}|")
    latex = latex.replace(r"\makebox[13.5cm][c]", r"\makebox[\linewidth][c]")
    latex = latex.replace(r"\setlength{\tabcolsep}{6pt}", r"\setlength{\tabcolsep}{3pt}")
    latex = latex.replace(r"\renewcommand{\arraystretch}{2.80}", r"\renewcommand{\arraystretch}{1.45}")
    latex = latex.replace(r"\renewcommand{\arraystretch}{1.9}", r"\renewcommand{\arraystretch}{1.35}")
    return latex


def _clean_headings(latex: str) -> str:
    latex = latex.replace(
        r"\section*{\fontsize{14pt}{16pt}\selectfont\bfseries Appendix A: Assumptions}",
        r"\section*{Appendix A: Assumptions}",
    )
    latex = latex.replace(
        r"\section*{\fontsize{14pt}{16pt}\selectfont\bfseries Appendix B: Calculation Methodology}",
        r"\section*{Appendix B: Calculation methodology}",
    )
    latex = latex.replace(
        r"\addcontentsline{toc}{section}{Appendix B: Calculation Methodology}",
        r"\addcontentsline{toc}{section}{Appendix B: Calculation methodology}",
    )
    latex = latex.replace(
        r"{\fontsize{13pt}{15pt}\selectfont\bfseries B.",
        r"{\bfseries B.",
    )
    return latex


def _appendix_a_content() -> str:
    marker = "Appendix A: Assumptions"
    start = APPENDIX_A_LATEX.find(marker)
    if start == -1:
        return ""

    section_start = APPENDIX_A_LATEX.rfind(r"\section*", 0, start)
    if section_start == -1:
        section_start = start

    content = APPENDIX_A_LATEX[section_start:]
    duplicate = content.find(r"\section*", len(r"\section*"))
    if duplicate != -1:
        content = content[:duplicate]

    content = content.replace(r"\appendix", "")
    return _clean_headings(_strip_v3_incompatible_latex(content))




def _appendix_b_content() -> str:
    content = APPENDIX_B_LATEX.replace(r"\appendix", "")
    content = _clean_headings(_strip_v3_incompatible_latex(content))
    content = content.replace(
        r"|p{0.18\linewidth}|p{0.72\linewidth}|",
        r"|>{\fontsize{9pt}{11pt}\selectfont}p{0.18\linewidth}|>{\fontsize{9pt}{11pt}\selectfont}p{0.72\linewidth}|",
    )
    content = re.sub(
        r"\\caption\*\{\\textit\{Table B-\d+\s+([^{}]+?)\}\}",
        r"\\caption{\1}",
        content,
    )
    content = re.sub(
        r"\\begin\{align\*\}(.*?)\\end\{align\*\}",
        lambda match: r"\[\begin{array}{rl}" + match.group(1) + r"\end{array}\]",
        content,
        flags=re.S,
    )
    return content


def appendices_to_latex(config: dict | None = None) -> str:
    config = config or {}
    parts = []
    if config.get(KEY_SHOW_APPENDIX_A, True):
        parts.append(appendix_counter("A"))
        parts.append(_appendix_a_content())
    if config.get(KEY_SHOW_APPENDIX_B, True):
        parts.append(appendix_counter("B"))
        parts.append(_appendix_b_content())
    return "\n\n".join(parts)

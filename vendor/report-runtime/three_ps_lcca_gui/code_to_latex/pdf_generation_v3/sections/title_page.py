from __future__ import annotations

import base64
import errno
import tempfile
from pathlib import Path

from pylatex.utils import escape_latex


def _chunk(controller, name: str) -> dict:
    for method_name in ("get_fresh_chunk", "get_chunk", "fetch_chunk"):
        method = getattr(controller, method_name, None)
        if callable(method):
            try:
                return method(name) or {}
            except Exception:
                pass
    return {}


def _first(data: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def _latex_path(path: str) -> str:
    if not path:
        return ""
    return Path(path).as_posix()


def _image_value_to_path(value: str, name: str) -> str:
    if not value:
        return ""
    # A base64-encoded image is far longer than any real path, so probing it
    # with Path.exists() raises OSError (ENAMETOOLONG). Treat that as "not a
    # path" and fall through to base64 decoding; re-raise anything else.
    try:
        if Path(value).exists():
            return str(Path(value))
    except OSError as exc:
        if exc.errno != errno.ENAMETOOLONG:
            raise
    try:
        raw = base64.b64decode(value, validate=True)
    except Exception:
        return ""
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        suffix = ".png"
    elif raw.startswith(b"\xff\xd8\xff"):
        suffix = ".jpg"
    else:
        return ""
    out_path = Path(tempfile.gettempdir()) / f"3ps_lcca_{name}{suffix}"
    out_path.write_bytes(raw)
    return str(out_path)


def _logo_or_placeholder(path: str, placeholder: str, width: str, height: str) -> str:
    path = _latex_path(path)
    if path:
        return "\n".join([
            r"\IfFileExists{" + path + r"}{%",
            r"  \includegraphics[height=" + height + r",keepaspectratio]{" + path + r"}%",
            r"}{%",
            _placeholder_box(placeholder, width, height),
            r"}%",
        ])
    return _placeholder_box(placeholder, width, height)


def _placeholder_box(text: str, width: str, height: str) -> str:
    return "\n".join([
        r"\begin{tcolorbox}[enhanced,colback=cardbg,colframe=hair,boxrule=0.5pt,arc=1.5mm,width="
        + width + r",height=" + height + r",valign=center,halign=center]",
        r"{\fontsize{11}{13}\selectfont\color{ftxt}" + escape_latex(text) + r"}",
        r"\end{tcolorbox}%",
    ])


def _person_block(title: str, name: str, org: str, addr: str, email: str, phone: str) -> str:
    return "\n".join([
        r"{\bfseries\color{ink}" + escape_latex(title) + r"}\par\vspace{2.5mm}",
        r"\renewcommand{\arraystretch}{1.15}\begin{tabular}{@{}>{\bfseries\color{slate}}p{2.5cm}>{\color{body}}p{4.5cm}@{}}",
        r"Name: & " + escape_latex(name) + r" \\",
        r"Organization: & " + escape_latex(org) + r" \\",
        r"Address: & " + escape_latex(addr) + r" \\",
        r"Email: & " + escape_latex(email) + r" \\",
        r"Phone: & " + escape_latex(phone) + r" \\",
        r"\end{tabular}\par\vspace{1cm}{\color{hair}\rule{0.8\linewidth}{0.5pt}}\par{\footnotesize\color{ftxt}Signature}",
    ])


def title_page_to_latex(controller=None, app_logo_path: str = "") -> str:
    general = _chunk(controller, "general_info")

    project_name = _first(general, "project_name", default="Unnamed Project")
    project_code = _first(general, "project_code")
    project_description = _first(general, "project_description", "remarks")
    agency_logo = _first(general, "agency_logo", "logo_path", "agency_logo_path")

    eval_name = _first(general, "contact_person", "agency_contact_person", "evaluated_by")
    eval_org = _first(general, "agency_name", "evaluating_agency")
    eval_addr = _first(general, "agency_address")
    eval_email = _first(general, "agency_email")
    eval_phone = _first(general, "agency_phone")

    rev_name = _first(general, "reviewed_by", "reviewer_name")
    rev_org = _first(general, "reviewer_organization", "review_agency")
    rev_addr = _first(general, "reviewer_address")
    rev_email = _first(general, "reviewer_email")
    rev_phone = _first(general, "reviewer_phone")

    agency_logo_tex = _logo_or_placeholder(_image_value_to_path(agency_logo, "agency_logo"), "[Agency Logo]", "4cm", "1.5cm")
    app_logo_tex = _logo_or_placeholder(app_logo_path, "[3psLCCA Logo]", "4cm", "1.0cm")

    return "\n".join([
        r"\begin{titlepage}",
        r"\thispagestyle{empty}",
        r"\definecolor{eco}{HTML}{9E9EFF}\definecolor{env}{HTML}{8AD400}\definecolor{soc}{HTML}{FF5A2A}",
        r"\definecolor{ink}{HTML}{1E2630}\definecolor{slate}{HTML}{45505E}\definecolor{body}{HTML}{2B2B2B}",
        r"\definecolor{hair}{HTML}{D9DDE3}\definecolor{ftxt}{HTML}{8A8AA0}\definecolor{cardbg}{HTML}{F5F6F8}",
        r"\newtcolorbox{infocard}{enhanced,colback=cardbg,colframe=hair,boxrule=0.5pt,arc=2.6mm,boxsep=0pt,left=6mm,right=6mm,top=3mm,bottom=3mm}",
        r"\newcommand{\tribar}[1]{\noindent\makebox[\textwidth]{\textcolor{eco}{\rule{0.3333\textwidth}{#1}}\textcolor{env}{\rule{0.3333\textwidth}{#1}}\textcolor{soc}{\rule{0.3334\textwidth}{#1}}}}",
        r"\newcommand{\SecHead}[1]{{\large\bfseries\color{ink}#1}}",
        r"\begin{tikzpicture}[remember picture,overlay]",
        r"  \fill[eco] (current page.north west) rectangle ($(current page.north west)!0.3333!(current page.south west)+(0.6cm,0)$);",
        r"  \fill[env] ($(current page.north west)!0.3333!(current page.south west)$) rectangle ($(current page.north west)!0.6667!(current page.south west)+(0.6cm,0)$);",
        r"  \fill[soc] ($(current page.north west)!0.6667!(current page.south west)$) rectangle ($(current page.south west)+(0.6cm,0)$);",
        r"\end{tikzpicture}",
        r"\vspace*{0.45cm}",
        r"\noindent\begin{minipage}[c]{0.48\textwidth}\raggedright",
        agency_logo_tex,
        r"\end{minipage}\hfill",
        r"\begin{minipage}[c]{0.48\textwidth}\raggedleft",
        app_logo_tex,
        r"\end{minipage}",
        r"\vspace{0.45cm}",
        r"\noindent{\fontsize{24}{28}\selectfont\bfseries\color{ink}Bridge Life Cycle Cost Analysis Report\par}",
        r"\vspace{2mm}",
        r"\vspace{3mm}",
        r"\tribar{1.6pt}",
        r"\vspace{2mm}",
        r"\vspace{0.3cm}",
        r"\begin{infocard}",
        r"\SecHead{Project information}\par\vspace{2mm}",
        r"\renewcommand{\arraystretch}{1.3}",
        r"\noindent\begin{tabular}{@{}>{\bfseries\color{slate}}p{3.6cm}>{\color{body}}p{\dimexpr\linewidth-4.0cm\relax}@{}}",
        r"Project name: & " + escape_latex(project_name) + r" \\",
        r"Project code: & " + escape_latex(project_code) + r" \\",
        r"Project description: & " + escape_latex(project_description) + r" \\",
        r"Prepared using: & 3psLCCA (\href{https://osdag.iitb.ac.in/3pslcca}{osdag.iitb.ac.in/3pslcca}) \\",
        r"\end{tabular}",
        r"\end{infocard}",
        r"\vfill",
        r"\noindent\begin{minipage}[t]{0.47\textwidth}",
        _person_block("Evaluated by", eval_name, eval_org, eval_addr, eval_email, eval_phone),
        r"\end{minipage}\hfill",
        r"\begin{minipage}[t]{0.47\textwidth}",
        _person_block("Reviewed by", rev_name, rev_org, rev_addr, rev_email, rev_phone),
        r"\end{minipage}",
        r"\vfill",
        r"\noindent{\color{hair}\rule{\textwidth}{0.6pt}}\\[3mm]",
        r"\noindent\begin{minipage}[t]{0.5\textwidth}",
        r"{\bfseries\color{slate}3psLCCA}\\",
        r"{\bfseries\color{slate}Osdag, IIT Bombay}\\",
        r"\href{https://osdag.iitb.ac.in/3pslcca}{osdag.iitb.ac.in/3pslcca}",
        r"\end{minipage}\hfill",
        r"\begin{minipage}[t]{0.46\textwidth}",
        r"{\footnotesize\color{ftxt}Generated using 3psLCCA. The software is provided without any warranty, express or implied. The life cycle cost analysis (LCCA) results depend on user-provided inputs. The evaluating agency is solely responsible for the accuracy of the input data and for any use of the results.\par}",
        r"\end{minipage}",
        r"\end{titlepage}",
    ])

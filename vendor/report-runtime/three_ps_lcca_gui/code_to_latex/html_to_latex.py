import re
from bs4 import BeautifulSoup
from pylatex.utils import escape_latex


def html_to_latex(html_text: str) -> str:
    """
    Robustly converts HTML rich text (from RemarksEditor) to a plain LaTeX-safe string.
    Strips all tags, handles entities, and escapes LaTeX special characters.
    """
    if not html_text:
        return ""

    try:
        # Use BeautifulSoup to get clean text from HTML
        soup = BeautifulSoup(html_text, "html.parser")
        # separator=" " ensures words don't get joined when tags are stripped
        text = soup.get_text(separator=" ").strip()
    except Exception:
        # Fallback to crude regex-like stripping if BS4 fails
        text = re.sub(r"<[^>]+>", "", html_text).strip()

    if not text:
        return ""

    return escape_latex(text)


def format_remarks_latex(data: dict, key: str = "remarks", label: str = "Notes") -> str:
    """
    Extracts remarks from a data dict and returns a formatted LaTeX paragraph.
    Returns an empty string if remarks are missing or empty.
    """
    remarks_html = data.get(key, "")
    clean_text = html_to_latex(remarks_html)
    
    if not clean_text:
        return ""

    return rf"\par\medskip\noindent \textbf{{{label}:}} {clean_text}\par\medskip"

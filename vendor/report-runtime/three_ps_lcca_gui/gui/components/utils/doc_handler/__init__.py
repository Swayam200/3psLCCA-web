r"""
gui/components/utils/doc_handler/__init__.py

Usage:
    from ..utils.doc_handler import open_doc
    open_doc(["Bridge_data", "Wind_Speed"])

    from ..utils.doc_handler import open_glossary
    open_glossary()
"""

from pathlib import Path

DOCS_DIR = Path(__file__).parent / "docs"


def open_glossary(slug_parts: list[str] | None = None, parent=None) -> None:
    """Open the glossary browser via pywebview."""
    from .webview_handler import open_glossary as _open_glossary
    _open_glossary(slug_parts, parent=parent)


def close_glossary() -> None:
    """Terminate the glossary subprocess if running."""
    from .webview_handler import close_glossary as _close_glossary
    _close_glossary()


def open_doc(slug_parts: list[str], parent=None) -> None:
    if not slug_parts:
        return
    open_glossary(slug_parts)

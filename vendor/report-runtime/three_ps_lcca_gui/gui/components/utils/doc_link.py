"""
gui/components/utils/doc_link.py

Utilities for inline documentation links inside QLabel rich text.

Usage
-----
    from ..utils.doc_link import doc_inline, doc_label

    # 1. Inline HTML fragment - embed anywhere in a rich-text string
    text = (
        f"The discount rate {doc_inline(['financial', 'discount-rate'])}, "
        f"inflation rate {doc_inline(['financial', 'inflation-rate'])} are different "
        f"and a summary is given {doc_inline(['financial', 'summary'], 'here')}."
    )

    # 2. Ready-made QLabel - linkActivated already wired to open_doc
    label = doc_label(text)
    layout.addWidget(label)
"""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QLabel

from .doc_handler import open_doc
from three_ps_lcca_gui.gui.themes import get_token, theme_manager


def doc_inline(slug_parts: list[str], text: str = "ⓘ") -> str:
    """
    Return an HTML anchor for inline use inside a QLabel rich-text string.

    Parameters
    ----------
    slug_parts : list[str]
        Doc path segments, e.g. ``["financial", "discount-rate"]``.
    text : str
        Link label. Defaults to ``"ⓘ"``.

    Returns
    -------
    str
        HTML ``<a href="...">text</a>`` fragment.
    """
    href = "/".join(slug_parts)
    color = get_token("primary")
    return (
        f'<a href="{href}" style="color:{color};text-decoration:none;font-weight:bold;">'
        f"{text}</a>"
    )


class _DocLabel(QLabel):
    """QLabel that re-renders its doc-link HTML whenever the theme changes."""

    def __init__(self, html: str, word_wrap: bool = True):
        super().__init__()
        self._html = html
        self.setTextFormat(Qt.RichText)
        self.setWordWrap(word_wrap)
        self.setOpenExternalLinks(False)
        self.linkActivated.connect(lambda href: open_doc(href.split("/"), self.window()))
        theme_manager().theme_changed.connect(self._refresh)
        self._refresh()

    @Slot()
    def _refresh(self):
        self.setText(re.sub(
            r'(<a [^>]*style="[^"]*color:)[^;]*(;)',
            lambda m: m.group(1) + get_token("primary") + m.group(2),
            f'<p style="margin:0;padding:0;">{self._html}</p>',
        ))


def doc_label(html: str, word_wrap: bool = True) -> QLabel:
    """
    Create a QLabel with rich text and all doc links pre-wired to open_doc.

    Parameters
    ----------
    html : str
        Rich-text string, typically built with :func:`doc_inline` fragments.
    word_wrap : bool
        Whether the label wraps long lines. Default True.

    Returns
    -------
    QLabel
        Ready to add to any layout.
    """
    return _DocLabel(html, word_wrap)

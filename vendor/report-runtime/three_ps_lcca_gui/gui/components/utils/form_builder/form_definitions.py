"""
Dataclasses for declarative form field definitions.

Usage
-----
    from gui.utils.form_definitions import Section, FieldDef

    FIELDS = [
        Section("Project Information"),
        FieldDef("project_name", "Project Name", "Official name...",
                 "text", required=True, doc_slug="project-name"),

        Section("Project Settings"),
        FieldDef("currency", "Currency", "Currency used...",
                 "combo", options=CURRENCIES, required=True, doc_slug="currency"),

        FieldDef("agency_logo", "Agency Logo", "Upload agency logo...",
                 "upload_img", options="default", doc_slug="agency-logo"),
    ]

Field types
-----------
    "text"       - QLineEdit (single line)
    "textarea"   - QTextEdit (multi-line)
    "int"        - QSpinBox;       options = (min, max)
    "float"      - QDoubleSpinBox; options = (min, max, decimals)
    "combo"      - QComboBox;      options = [str, ...]
    "upload_img" - image picker;   options = preset string or dict
                   (see gui.utils.image_utils.resolve_img_settings)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ValidationStatus(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"


@dataclass
class Section:
    """A visual section header with a horizontal divider. Not a data field."""

    title: str


@dataclass
class FieldDef:
    """
    Declaration of a single form input field.

    Parameters
    ----------
    key : str
        Attribute name used for widget registration (``self.field(key, widget)``).
    title : str
        Human-readable label shown above the input.
    explanation : str
        Helper text shown below the title. Rendered as rich text with an
        inline ⓘ docs link when ``doc_slug`` is provided.
    field_type : str
        One of: "text", "textarea", "int", "float", "combo", "upload_img".
    options : Any
        Type-specific configuration:
            text / textarea  - None (unused)
            int              - (min: int, max: int)
            float            - (min: float, max: float, decimals: int)
            combo            - list[str]
            upload_img       - "default" | "no_compression" | dict
    unit : str
        Optional unit suffix appended to spinbox widgets, e.g. ``"(m)"``.
        Empty string if not applicable.
    required : bool
        Whether the field must be non-empty/non-zero before form submission.
    doc_slug : list[str]
        Path segments identifying the HTML doc page, e.g.
        ``["financial", "discount-rate"]`` → ``site/financial/discount-rate.html``.
        Empty list disables the link.
    """

    key: str
    title: str
    explanation: str
    field_type: str
    options: Any = None
    unit: str = ""
    required: bool = False
    doc_slug: list[str] = field(default_factory=list)
    warn: tuple | None = None  # (low, high) or (low, high, msg) or (low, high, low_msg, high_msg)
    default: Any = None  # explicit initial value; if None, the widget's lower bound is used
    blocked: bool = False  # permanently read-only regardless of project lock state
    placeholder_text: str = ""  # hint shown when the field is empty (text / textarea only)
    combo_placeholder: str | None = None  # None → "-- select --"  |  "" → no placeholder  |  "text" → that text



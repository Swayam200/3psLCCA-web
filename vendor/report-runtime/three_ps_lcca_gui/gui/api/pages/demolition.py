"""
gui/api/pages/demolition.py

Registers the "demolition_data" chunk with the API.
"""

from three_ps_lcca_gui.gui.components.demolition.main import (
    DEMOLITION_FIELDS,
    DEMOLITION_WARN_RULES,
    Demolition,
)

from ..registry import register_chunk

register_chunk(
    "demolition_data",
    page_name="Demolition",
    widget_cls=Demolition,
    field_defs=DEMOLITION_FIELDS,
    warn_rules=DEMOLITION_WARN_RULES,
)

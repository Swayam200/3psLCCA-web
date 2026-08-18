"""
gui/api/pages/bridge_data.py

Registers the "bridge_data" chunk with the API. This is the whole extent of
what a page needs to do to become API-reachable - see the module docstring in
gui/api/pages/__init__.py for the steps to add another page.
"""

from three_ps_lcca_gui.gui.components.bridge_data.main import (
    BRIDGE_FIELDS,
    BRIDGE_WARN_RULES,
    BridgeData,
)

from ..registry import register_chunk

register_chunk(
    "bridge_data",
    page_name="Bridge Data",
    widget_cls=BridgeData,
    field_defs=BRIDGE_FIELDS,
    warn_rules=BRIDGE_WARN_RULES,
)

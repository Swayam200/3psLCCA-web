"""
gui/api/pages/maintenance.py

Registers the "maintenance_data" chunk with the API. Maintenance declares its
warn ranges inline on each FieldDef (warn=...) rather than in a module-level
dict - register_chunk() picks those up automatically, so no warn_rules here.
"""

from three_ps_lcca_gui.gui.components.maintenance.main import (
    MAINTENANCE_FIELDS,
    Maintenance,
)

from ..registry import register_chunk

register_chunk(
    "maintenance_data",
    page_name="Maintenance and Repair",
    widget_cls=Maintenance,
    field_defs=MAINTENANCE_FIELDS,
)

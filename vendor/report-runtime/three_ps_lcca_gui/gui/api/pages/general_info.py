"""
gui/api/pages/general_info.py

Registers the "general_info" chunk with the API. Note: the component lives
under gui/components/global_info/, but the chunk name the engine actually
stores/reads it under (and the name this page is addressed by via the API)
is "general_info" - see GeneralInfo.__init__ and GeneralInfo.get_data().
"""

from three_ps_lcca_gui.gui.components.global_info.main import (
    GENERAL_FIELDS,
    GeneralInfo,
)

from ..registry import register_chunk


def _sor_database_options(data: dict) -> list[str]:
    """sor_database's real options aren't a fixed list - the GUI computes
    them at runtime from the material catalog, filtered by the project's
    own country (see GeneralInfo._populate_sor_combo, which calls this
    exact same _list_sor_options()). The FieldDef's own `options=[]` is
    just a static placeholder; without this hook, GET .../general_info
    would always report an empty options list here regardless of what the
    GUI actually offers. Returns db_key values (what's actually stored/
    validated for this field), not the display label."""
    from three_ps_lcca_gui.gui.components.structure.widgets.material_dialog import _list_sor_options
    country = data.get("project_country", "")
    return [opt["db_key"] for opt in _list_sor_options(country)]


register_chunk(
    "general_info",
    page_name="General Information",
    widget_cls=GeneralInfo,
    field_defs=GENERAL_FIELDS,
    dynamic_options={"sor_database": _sor_database_options},
)

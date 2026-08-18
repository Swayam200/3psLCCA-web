from pylatex import Table, Tabular, MultiColumn, NoEscape
from pylatex.utils import bold, escape_latex
from ..gui.components.utils.form_builder.form_definitions import Section, FieldDef
from .html_to_latex import format_remarks_latex


def latex_layout(name: str) -> str:
    from .SETTINGS import LATEX_TABLE_LAYOUTS
    return LATEX_TABLE_LAYOUTS[name]

def fields_to_latex(fields: list, data: dict, caption: str, label: str, unit_overrides: dict = None) -> str:
    """Build a pylatex table from a list of Section/FieldDef entries and a data dict.

    Columns: Title | Value and Unit
    Args:
        fields:         FIELDS list (mix of Section and FieldDef)
        data:           chunk dict {key: value}
        caption:        table caption string
        label:          LaTeX label string, e.g. "tab:bridge_data"
        unit_overrides: optional {field_key: unit_string} to replace FieldDef.unit at render time
    """
    tabular = Tabular(NoEscape(latex_layout("field_table")))
    tabular.append(NoEscape(r"\toprule"))

    first_section = True
    for entry in fields:
        if isinstance(entry, Section):
            if not first_section:
                tabular.append(NoEscape(r"\midrule"))
            first_section = False
            tabular.append(NoEscape(MultiColumn(2, align="l", data=bold(entry.title)).dumps() + r" \\"))
            tabular.append(NoEscape(r"\midrule"))
        elif isinstance(entry, FieldDef):
            raw = data.get(entry.key, "")
            if raw in ("", None):
                value = NoEscape(r"\textemdash")
            elif isinstance(raw, NoEscape):
                value = raw
            elif isinstance(raw, (int, float)):
                value = str(raw)
            else:
                value = str(raw)
            unit = (unit_overrides or {}).get(entry.key, entry.unit) or ""
            if unit:
                unit = unit if "\\" in unit else escape_latex(unit)
                value = NoEscape(f"{escape_latex(str(value))} {unit}")
            tabular.add_row(entry.title, value)

    tabular.append(NoEscape(r"\bottomrule"))

    table = Table(position="h!")
    table.append(NoEscape(r"\centering"))
    table.add_caption(caption)
    table.append(NoEscape(rf"\label{{{label}}}"))
    table.append(tabular)

    out = table.dumps()
    remarks = format_remarks_latex(data)
    if remarks:
        out += "\n\n" + remarks
    return out



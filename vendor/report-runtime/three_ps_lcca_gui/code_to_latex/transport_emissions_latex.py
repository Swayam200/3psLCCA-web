import math
import pandas as pd
from ..gui.components.utils.common_requested_data import get_chunk, get_transport_data
from ..gui.components.utils.definitions import STRUCTURE_CHUNKS
from .SETTINGS import DECIMAL_PLACES_FOR_LATEX
from .html_to_latex import format_remarks_latex
from .common_code import latex_layout

_FMT    = f"{{:,.{DECIMAL_PLACES_FOR_LATEX}f}}"
_EMDASH = r"\textemdash"


def _summary_table_to_latex(entries: list) -> str:
    """One-row-per-vehicle overview table."""
    rows = []
    for table_no, (entry, total_emission) in enumerate(entries, start=1):
        v = entry.get("vehicle", {})
        r = entry.get("route", {})
        capacity     = float(v.get("capacity",      0) or 0)
        gross_weight = float(v.get("gross_weight",  0) or 0)
        ef           = float(v.get("emission_factor", 0) or 0)
        distance     = float(r.get("distance_km",   0) or 0)
        origin       = r.get("origin", "") or ""
        vehicle_name = v.get("name", "").strip()
        rows.append({
            "Delivery":             f"Delivery~{table_no}",
            "Vehicle":              vehicle_name or r"\makebox[\linewidth][c]{\textemdash}",
            "From-To":              origin,
            "Distance (km)":        distance,
            "Capacity (t)":         capacity,
            "Gross Wt (t)":         gross_weight,
            "Emission Factor":      ef,
            "Total Emissions (kgCO₂e)": total_emission,
        })

    if not rows:
        return ""

    df = pd.DataFrame(rows)
    numeric_cols = ["Distance (km)", "Capacity (t)", "Gross Wt (t)", "Emission Factor",
                    "Total Emissions (kgCO₂e)"]
    return ((
        df.style.hide(axis="index")
        .format(_FMT, subset=numeric_cols, na_rep=_EMDASH)
        .to_latex(
            caption="Transport Emissions — Summary by Vehicle",
            label="tab:transport_emissions_summary",
            hrules=True,
            column_format=latex_layout("transport_summary"),
            environment="longtable",
        )
    ) or "").replace(
        "Delivery & Vehicle & From-To & Distance (km) & Capacity (t) & Gross Wt (t) & Emission Factor & Total Emissions (kgCO₂e)",
        r"\textbf{Delivery} & \textbf{Vehicle} & \textbf{From-To} & \textbf{Distance (km)} & \textbf{Capacity (t)} & \textbf{Gross Wt (t)} & \textbf{Emission Factor} & \textbf{Total Emissions (kgCO₂e)}",
    )


def _build_material_index() -> dict:
    index = {}
    for chunk_id, category in STRUCTURE_CHUNKS:
        for component, items in get_chunk(chunk_id).items():
            for item in items:
                mat_id = item.get("id")
                if mat_id:
                    index[mat_id] = {"item": item, "category": category, "component": component}
    return index


def _material_entry_values(mat_entry):
    if isinstance(mat_entry, dict):
        return mat_entry.get("uuid"), float(mat_entry.get("kg_factor", 1.0) or 0)
    return mat_entry, 1.0


def _vehicle_table_to_latex(entry: dict, mat_index: dict, table_no: int) -> str:
    vehicle  = entry.get("vehicle", {})
    route    = entry.get("route", {})

    capacity     = float(vehicle.get("capacity",      0) or 0)
    gross_weight = float(vehicle.get("gross_weight",  0) or 0)
    empty_weight = float(vehicle.get("empty_weight",  max(0.0, gross_weight - capacity)) or 0)
    distance     = float(route.get("distance_km",     0) or 0)
    ef           = float(vehicle.get("emission_factor", 0) or 0)

    rows = []
    total_emission = 0.0

    for mat_entry in entry.get("materials", []):
        mat_uuid, kg_factor = _material_entry_values(mat_entry)

        if mat_uuid not in mat_index:
            rows.append({"Material": "Unknown", "Category": "",
                         "kg Conversion Factor": None,
                         "Quantity (kg)": None, "Trips": None,
                         "Emissions (kgCO₂e)": 0.0})
            continue

        record = mat_index[mat_uuid]
        item   = record["item"]

        if item.get("state", {}).get("in_trash", False):
            v = item.get("values", {})
            rows.append({"Material": v.get("material_name", ""), "Category": record["category"],
                         "kg Conversion Factor": None, "Quantity (kg)": None, "Trips": None,
                         "Emissions (kgCO₂e)": 0.0})
            continue

        v        = item.get("values", {})
        unit     = v.get("unit", "")
        quantity = float(v.get("quantity", 0) or 0)
        qty_kg   = quantity * kg_factor
        qty_t    = qty_kg / 1000.0
        trips    = math.ceil(qty_t / capacity) if capacity > 0 else 0
        emission = (gross_weight + empty_weight) * trips * distance * ef
        total_emission += emission

        rows.append({
            "Material":              v.get("material_name", ""),
            "Category":              record["category"],
            "kg Conversion Factor":  kg_factor,
            "Quantity (kg)":         qty_kg,
            "Trips":                 float(trips),
            "Emissions (kgCO₂e)":  emission,
        })

    df = pd.DataFrame(rows)
    vehicle_name = vehicle.get("name", "").strip()
    origin    = route.get("origin", "").strip()
    route_str = origin if origin else f"{distance:.{DECIMAL_PLACES_FOR_LATEX}f}\\,km"
    name_part = f": {vehicle_name}" if vehicle_name else ""
    caption = f"Delivery {table_no}{name_part} — From {route_str}"

    return ((
        df.style.hide(axis="index")
        .format(_FMT, subset=["kg Conversion Factor", "Quantity (kg)", "Trips", "Emissions (kgCO₂e)"],
                na_rep=_EMDASH)
        .to_latex(
            caption=caption,
            label=f"tab:transport_emissions_{table_no}",
            hrules=True,
            column_format=latex_layout("transport_emissions"),
            environment="longtable",
        )
    ) or "").replace(
        "Material & Category & kg Conversion Factor & Quantity (kg) & Trips & Emissions (kgCO₂e)",
        r"\textbf{Material} & \textbf{Category} & \textbf{(kg) Conversion Factor} & \textbf{Quantity (kg)} & \textbf{Trips} & \textbf{Emissions (kgCO₂e)}",
    )


def transport_emissions_to_latex(controller=None) -> str:
    data      = get_transport_data()
    mat_index = _build_material_index()

    active_entries = []   # (entry, total_emission)
    detail_tables  = []
    table_no       = 1

    for entry in data.get("vehicles", []):
        if entry.get("state", {}).get("in_trash", False):
            continue
        tex = _vehicle_table_to_latex(entry, mat_index, table_no)
        # compute total_emission for summary (re-use what _vehicle_table_to_latex already did)
        vehicle      = entry.get("vehicle", {})
        route        = entry.get("route", {})
        capacity     = float(vehicle.get("capacity",     0) or 0)
        gross_weight = float(vehicle.get("gross_weight", 0) or 0)
        empty_weight = float(vehicle.get("empty_weight", max(0.0, gross_weight - capacity)) or 0)
        distance     = float(route.get("distance_km",    0) or 0)
        ef           = float(vehicle.get("emission_factor", 0) or 0)
        total = 0.0
        for mat_entry in entry.get("materials", []):
            mat_uuid, kg_factor = _material_entry_values(mat_entry)
            rec = mat_index.get(mat_uuid)
            if not rec or rec["item"].get("state", {}).get("in_trash", False):
                continue
            v       = rec["item"].get("values", {})
            qty_kg  = float(v.get("quantity", 0) or 0) * kg_factor
            trips   = math.ceil(qty_kg / 1000.0 / capacity) if capacity > 0 else 0
            total  += (gross_weight + empty_weight) * trips * distance * ef

        active_entries.append((entry, total))
        if tex:
            detail_tables.append(tex)
        table_no += 1

    parts = []
    summary = _summary_table_to_latex(active_entries)
    if summary:
        parts.append(summary)
    parts.extend(detail_tables)

    out = "\n\n".join(parts)
    remarks = format_remarks_latex(data)
    if remarks:
        out += "\n\n" + remarks
    return out

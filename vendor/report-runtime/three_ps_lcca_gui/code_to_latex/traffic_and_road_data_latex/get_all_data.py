from ...gui.components.utils.common_requested_data import get_traffic_and_road_data
from .wpi_tables_latex import _get_wpi_base, _get_wpi_selected, _get_wpi_ratio, _wpi_combined_table
from .vehicle_data_latex import _vehicle_data
from .diversion_emissions_latex import _diversion_emissions
from .all_fields_latex import _traffic_fields, _global_traffic_fields, _peak_hour_distribution


def _wpi_tables(data: dict) -> str:
    snapshot = data.get("wpi", {}).get("data_snapshot", {})
    table = _wpi_combined_table(
        base     = snapshot.get("base",     {}),
        selected = snapshot.get("selected", {}),
        ratio    = snapshot.get("ratio",    {}),
    )
    return r"\begin{landscape}" + "\n\n" + table + "\n\n" + r"\end{landscape}"


# ── Individual devmode entries (each fetches once for its own use) ─────────────

def global_traffic_fields_to_latex(controller=None) -> str:
    return _global_traffic_fields(get_traffic_and_road_data())


def traffic_fields_to_latex(controller=None) -> str:
    return _traffic_fields(get_traffic_and_road_data())


def peak_hour_distribution_to_latex(controller=None) -> str:
    return _peak_hour_distribution(get_traffic_and_road_data())


def vehicle_data_to_latex(controller=None) -> str:
    return _vehicle_data(get_traffic_and_road_data())


def diversion_emissions_to_latex(controller=None) -> str:
    return _diversion_emissions(get_traffic_and_road_data())


def wpi_base_to_latex(controller=None) -> str:
    snapshot = get_traffic_and_road_data().get("wpi", {}).get("data_snapshot", {})
    return r"\begin{landscape}" + "\n\n" + _get_wpi_base(snapshot.get("base", {})) + "\n\n" + r"\end{landscape}"


def wpi_selected_to_latex(controller=None) -> str:
    snapshot = get_traffic_and_road_data().get("wpi", {}).get("data_snapshot", {})
    return r"\begin{landscape}" + "\n\n" + _get_wpi_selected(snapshot.get("selected", {})) + "\n\n" + r"\end{landscape}"


def wpi_ratio_to_latex(controller=None) -> str:
    snapshot = get_traffic_and_road_data().get("wpi", {}).get("data_snapshot", {})
    return r"\begin{landscape}" + "\n\n" + _get_wpi_ratio(snapshot.get("ratio", {})) + "\n\n" + r"\end{landscape}"


def wpi_tables_to_latex(controller=None) -> str:
    return _wpi_tables(get_traffic_and_road_data())


# ── Full page: fetch once, pass to every section ───────────────────────────────

def traffic_and_road_data_to_latex(controller=None) -> str:
    data = get_traffic_and_road_data()
    return "\n\n".join([
        _traffic_fields(data),
        _vehicle_data(data),
        _diversion_emissions(data),
        _peak_hour_distribution(data),
        _wpi_tables(data),
    ])

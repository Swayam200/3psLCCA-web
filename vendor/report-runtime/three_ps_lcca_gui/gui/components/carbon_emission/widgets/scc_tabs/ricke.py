from pathlib import Path

import pandas as pd

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QWidget,
)

from three_ps_lcca_gui.gui.themes import get_token
from three_ps_lcca_gui.gui._CONFIG import DEV_MODE
from three_ps_lcca_gui.gui.theme import (
    FS_LG, FS_MD, FS_BASE, FS_SM,
    FW_SEMIBOLD, FW_NORMAL,
)
from ....base_widget import ScrollableForm
from ....utils.form_builder.form_definitions import FieldDef, Section
from ....utils.form_builder.form_builder import build_form, _PLACEHOLDER
from ....utils.display_format import DECIMAL_PLACES
from ....utils.validation_helpers import freeze_form, validate_form, clear_field_styles, confirm_clear_all, _apply_border_style, _clear_border_style
from ....utils.common_requested_data import get_currency, get_project_iso3

# ── DB helpers (mirrors cscc_explorer.py) ─────────────────────────────────────

_PKL_PATH = Path(__file__).parent.parent.parent / "cscc-database-2018-master" / "cscc_db.pkl"

_CLOSEST_RCP = {"SSP1": "rcp60", "SSP2": "rcp60", "SSP3": "rcp85", "SSP4": "rcp60", "SSP5": "rcp85"}

_SSP_LABEL_MAP = {
    "SSP1 (Sustainability)":           "SSP1",
    "SSP2 (Middle of the Road)":       "SSP2",
    "SSP3 (Regional Rivalry)":         "SSP3",
    "SSP4 (Inequality)":               "SSP4",
    "SSP5 (Fossil-fueled Development)": "SSP5",
}

_RCP_LABEL_MAP = {
    "Closest RCP (Default)":        None,
    "RCP4.5 (≈ +2.5°C in 2100)":   "rcp45",
    "RCP6.0 (≈ +3°C in 2100)":     "rcp60",
    "RCP8.5 (≈ +4.5°C in 2100)":   "rcp85",
}

_DMG_FUNC_LABEL_MAP = {
    "BHM SR (Short Run)":               "bhm_sr",
    "BHM RP SR (Rich/Poor Short Run)":  "bhm_richpoor_sr",
    "BHM LR (Long Run)":                "bhm_lr",
    "BHM RP LR (Rich/Poor Long Run)":   "bhm_richpoor_lr",
}

_DMG_PARAMS_LABEL_MAP = {
    "Bootstrap (Full Uncertainty)":  "bootstrap",
    "Estimates (Central Params)":    "estimates",
}

_CLIMATE_LABEL_MAP = {
    "Expected (Central Projections)": "expected",
    "Uncertain (Bootstrapped)":       "uncertain",
}

_DISC_MAP = {
    "Growth-adjusted (prtp=2%, η=1.5)": {"prtp": "2",  "eta": "1p5", "dr": "NA"},
    "Growth-adjusted (prtp=1%, η=1.5)": {"prtp": "1",  "eta": "1p5", "dr": "NA"},
    "Growth-adjusted (prtp=2%, η=0.7)": {"prtp": "2",  "eta": "0p7", "dr": "NA"},
    "Growth-adjusted (prtp=1%, η=0.7)": {"prtp": "1",  "eta": "0p7", "dr": "NA"},
    "Fixed 3%":                          {"prtp": "NA", "eta": "NA",  "dr": "3"},
    "Fixed 5%":                          {"prtp": "NA", "eta": "NA",  "dr": "5"},
}

_PERCENTILE_MAP = {
    "16.7% (Optimistic)":  0,
    "50.0% (Central)":     1,
    "83.3% (Pessimistic)": 2,
}


_db = None


def _get_db():
    global _db
    if _db is None:
        _db = pd.read_pickle(_PKL_PATH)
    return _db


def _lookup(df, iso3, run, dmgfuncpar, climate, ssp, rcp, disc):
    """Returns (values, reason) where values is (lo, med, hi) or None.
    reason: "ok" | "na" | "missing"
    """
    key = (iso3, run, dmgfuncpar, climate, ssp, rcp, disc["prtp"], disc["eta"], disc["dr"])
    try:
        row = df.loc[key]
        lo, med, hi = row["16.7%"], row["50%"], row["83.3%"]
        if pd.isna(lo) or pd.isna(med) or pd.isna(hi):
            return None, "na"
        return (float(lo), float(med), float(hi)), "ok"
    except KeyError:
        return None, "missing"

_SSP_OPTIONS = [
    "SSP1 (Sustainability)",
    "SSP2 (Middle of the Road)",
    "SSP3 (Regional Rivalry)",
    "SSP4 (Inequality)",
    "SSP5 (Fossil-fueled Development)",
]

_RCP_OVERRIDE_OPTIONS = [
    "Closest RCP (Default)",
    "RCP4.5 (≈ +2.5°C in 2100)",
    "RCP6.0 (≈ +3°C in 2100)",
    "RCP8.5 (≈ +4.5°C in 2100)",
]

_DMG_FUNC_OPTIONS = [
    "BHM SR (Short Run)",
    "BHM RP SR (Rich/Poor Short Run)",
    "BHM LR (Long Run)",
    "BHM RP LR (Rich/Poor Long Run)",
]

_DMG_PARAM_OPTIONS = [
    "Bootstrap (Full Uncertainty)",
    "Estimates (Central Params)",
]

_CLIMATE_MODEL_OPTIONS = [
    "Expected (Central Projections)",
    "Uncertain (Bootstrapped)",
]

_DISCOUNTING_OPTIONS = [
    "Growth-adjusted (prtp=2%, η=1.5)",
    "Growth-adjusted (prtp=1%, η=1.5)",
    "Growth-adjusted (prtp=2%, η=0.7)",
    "Growth-adjusted (prtp=1%, η=0.7)",
    "Fixed 3%",
    "Fixed 5%",
]

_PERCENTILE_OPTIONS = [
    "16.7% (Optimistic)",
    "50.0% (Central)",
    "83.3% (Pessimistic)",
]

RICKE_FIELDS: list[FieldDef | Section] = [
    Section("Socioeconomic & Climate Scenarios"),
    FieldDef(
        "iso3",
        "Country (ISO3)",
        "The country for which to calculate the social cost. 'WLD' represents the global aggregate.",
        "combo",
        options=["WLD"],
        required=True,
    ),
    FieldDef(
        "ssp",
        "Socioeconomic Pathway (SSP)",
        "Assumptions on future population, GDP, and energy use.",
        "combo",
        options=_SSP_OPTIONS,
        required=True,
    ),
    FieldDef(
        "rcp",
        "Climate Trajectory (RCP)",
        "Representative Concentration Pathway. Choose 'Closest RCP' to use the paper's default pairing.",
        "combo",
        options=_RCP_OVERRIDE_OPTIONS,
        required=True,
    ),
    Section("Damage Function & Model Parameters"),
    FieldDef(
        "dmg_func",
        "Damage Function",
        "The empirical model used to relate temperature change to economic damage.",
        "combo",
        options=_DMG_FUNC_OPTIONS,
        required=True,
    ),
    FieldDef(
        "dmg_params",
        "Damage Parameters",
        "Whether to use bootstrapped uncertainty or central parameter estimates.",
        "combo",
        options=_DMG_PARAM_OPTIONS,
        required=True,
    ),
    FieldDef(
        "climate_uncertainty",
        "Climate Uncertainty",
        "Whether to use expected climate projections or bootstrapped uncertainty.",
        "combo",
        options=_CLIMATE_MODEL_OPTIONS,
        required=True,
    ),
    Section("Discounting & Valuation"),
    FieldDef(
        "discounting",
        "Discounting Approach",
        "The method for calculating the present value of future damages (Pure Rate of Time Preference and Elasticity of Marginal Utility).",
        "combo",
        options=_DISCOUNTING_OPTIONS,
        required=True,
    ),
    FieldDef(
        "percentile",
        "Percentile",
        "The statistical percentile of the SCC distribution to use.",
        "combo",
        options=_PERCENTILE_OPTIONS,
        required=True,
    ),
    Section("Currency Adjustment"),
    FieldDef(
        "usd_to_local_rate",
        "USD Conversion Rate",
        "Conversion rate for international scientific model outputs (base is USD 2015).",
        "float",
        options=(1e-6, 1e6, 4),
        unit="(Currency/USD)",
        warn=(
            0.0001,
            None,
            "USD to Local Currency Conversion Rate is 0 - the Ricke et al. social cost of carbon will result in 0 in the local currency; enter the current USD-to-local exchange rate",
        ),
    ),
    Section("Inflation Adjustment (CPI)"),
    FieldDef(
        "cpi_ratio",
        "CPI Ratio (Reference-Year CPI / 2018 CPI)",
        "The Ricke et al. paper was published in 2018. Apply a CPI ratio (current year CPI ÷ 2018 CPI) to adjust the output for inflation. Set to 1.0 to use the original 2018 values.",
        "float",
        options=(0.0, 100.0, DECIMAL_PLACES),
        default=1.0,
        warn=(
            0.0001,
            None,
            "CPI Ratio is 0 - no inflation adjustment will be applied to the SCC value",
        ),
    ),
]


class RickeWidget(ScrollableForm):
    def __init__(self, controller=None):
        super().__init__(controller=controller, chunk_name=None)
        build_form(self, RICKE_FIELDS)
        self._update_currency_suffix()

        # ── result labels (inside scroll, after last field) ───────────────────
        self._lbl_scc = QLabel("-")
        self._lbl_range = QLabel("")
        self._lbl_params = QLabel("")
        self._lbl_status = QLabel("Fill all fields above to compute.")

        for lbl in (self._lbl_scc, self._lbl_range, self._lbl_params, self._lbl_status):
            lbl.setWordWrap(True)

        self._lbl_scc.setStyleSheet(
            f"color: {get_token('text')}; font-size: {FS_LG}pt; font-weight: {FW_SEMIBOLD};"
        )
        self._lbl_range.setStyleSheet(
            f"color: {get_token('text_secondary')}; font-size: {FS_MD}pt; font-weight: {FW_NORMAL};"
        )
        self._lbl_params.setStyleSheet(
            f"color: {get_token('text_secondary')}; font-size: {FS_SM}pt; font-weight: {FW_NORMAL};"
        )
        self._lbl_status.setStyleSheet(
            f"color: {get_token('text_secondary')}; font-size: {FS_BASE}pt; font-weight: {FW_NORMAL};"
        )

        for lbl in (self._lbl_scc, self._lbl_range, self._lbl_params, self._lbl_status):
            self.form.addRow(lbl)

        self._lbl_explorer = QLabel(
            '<a href="https://country-level-scc.github.io/explorer/">Country-level SCC Explorer</a>'
        )
        self._lbl_explorer.setOpenExternalLinks(True)
        self._lbl_explorer.setStyleSheet(
            f"color: {get_token('primary')}; font-size: {FS_SM}pt;"
        )
        self.form.addRow(self._lbl_explorer)

        # ── clear button (inside form, same pattern as demolition/traffic_data) ─
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 10, 0, 10)
        self._btn_clear = QPushButton("Clear All")
        self._btn_clear.setMinimumHeight(35)
        self._btn_clear.clicked.connect(self._clear_all)
        btn_layout.addWidget(self._btn_clear)
        self.form.addRow(btn_row)

        self._populate_iso3()
        self._connect_combo_logging()

    def _update_currency_suffix(self):
        currency = get_currency()
        if currency == "Currency":
            print("[RickeWidget] project currency not found - usd_to_local_rate suffix not updated")
        widget = self._field_map.get("usd_to_local_rate")
        if isinstance(widget, QDoubleSpinBox):
            widget.setSuffix(f" {currency}/USD")

    def showEvent(self, event):
        super().showEvent(event)
        self._print_ricke_cost()

    def refresh_from_engine(self):
        self._update_currency_suffix()
        self._apply_country_lock()

    def _populate_iso3(self):
        try:
            df = _get_db()
            iso3_list = sorted(df.index.get_level_values("ISO3").unique())
            combo = self._field_map["iso3"]
            combo.clear()
            combo.addItem("-- select --")
            combo.addItems(iso3_list)
        except Exception as e:
            print(f"[RickeWidget] failed to load ISO3 list: {e}")
        self._apply_country_lock()

    def _apply_country_lock(self):
        """Set iso3 to project country if it exists in the DB and lock it; else default to WLD."""
        combo = self._field_map.get("iso3")
        if combo is None:
            return
        iso3_code = get_project_iso3()
        idx = combo.findText(iso3_code) if iso3_code else -1
        if idx >= 0:
            combo.setCurrentIndex(idx)
            combo.setEnabled(False)
        else:
            combo.setEnabled(True)
            if combo.currentText() == "-- select --":
                wld_idx = combo.findText("WLD")
                if wld_idx >= 0:
                    combo.setCurrentIndex(wld_idx)

    def _connect_combo_logging(self):
        for widget in self._field_map.values():
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(lambda _: self._print_ricke_cost())
            elif isinstance(widget, QDoubleSpinBox):
                widget.valueChanged.connect(lambda _: self._print_ricke_cost())

    def _print_ricke_cost(self):
        fm = self._field_map

        iso3      = fm["iso3"].currentText()
        ssp_label = fm["ssp"].currentText()
        rcp_label = fm["rcp"].currentText()
        dmg_label = fm["dmg_func"].currentText()
        par_label = fm["dmg_params"].currentText()
        cli_label = fm["climate_uncertainty"].currentText()
        dis_label = fm["discounting"].currentText()
        pct_label = fm["percentile"].currentText()

        # ── guard: all required fields must be filled ─────────────────────────
        required = {
            "Country":             ("iso3",              iso3),
            "SSP":                 ("ssp",               ssp_label),
            "RCP":                 ("rcp",               rcp_label),
            "Damage Function":     ("dmg_func",          dmg_label),
            "Damage Parameters":   ("dmg_params",        par_label),
            "Climate Uncertainty": ("climate_uncertainty", cli_label),
            "Discounting":         ("discounting",       dis_label),
            "Percentile":          ("percentile",        pct_label),
        }
        unfilled_names = []
        for label, (key, val) in required.items():
            widget = fm[key]
            if val == _PLACEHOLDER:
                _apply_border_style(widget, get_token("danger"))
                unfilled_names.append(label)
            else:
                _clear_border_style(widget)

        if unfilled_names:
            self._lbl_scc.setText("-")
            self._lbl_scc.setStyleSheet(f"color: {get_token('text')}; font-size: {FS_LG}pt; font-weight: {FW_SEMIBOLD};")
            self._lbl_range.setText("")
            self._lbl_params.setText("")
            self._lbl_status.setText(f"Waiting for: {', '.join(unfilled_names)}")
            self._lbl_status.setStyleSheet(f"color: {get_token('text_secondary')}; font-size: {FS_BASE}pt; font-weight: {FW_NORMAL};")
            print(f"[RickeWidget] waiting for: {', '.join(unfilled_names)}")
            return

        # ── exact lookups - no assumptions ────────────────────────────────────
        ssp = _SSP_LABEL_MAP.get(ssp_label)
        rcp_raw = _RCP_LABEL_MAP.get(rcp_label)
        rcp = rcp_raw if rcp_raw is not None else _CLOSEST_RCP[ssp]
        run = _DMG_FUNC_LABEL_MAP.get(dmg_label)
        dmgfuncpar = _DMG_PARAMS_LABEL_MAP.get(par_label)
        climate = _CLIMATE_LABEL_MAP.get(cli_label)
        disc = _DISC_MAP.get(dis_label)
        pct_idx = _PERCENTILE_MAP.get(pct_label)

        missing = [k for k, v in {
            "ssp": ssp, "run": run, "dmgfuncpar": dmgfuncpar,
            "climate": climate, "disc": disc, "pct_idx": pct_idx,
        }.items() if v is None]
        if missing:
            self._lbl_status.setText(f"Unmapped values: {', '.join(missing)}")
            print(f"[RickeWidget] unmapped keys: {', '.join(missing)}")
            return

        # ── DB lookup ─────────────────────────────────────────────────────────
        try:
            df = _get_db()
        except Exception as e:
            self._lbl_status.setText(f"DB error: {e}")
            print(f"[RickeWidget] DB load error: {e}")
            return

        result, reason = _lookup(df, iso3, run, dmgfuncpar, climate, ssp, rcp, disc)

        rcp_display = rcp_label if rcp_raw is not None else f"{rcp_label} → {rcp}"
        summary = (
            f"Country: {iso3}   ·   SSP: {ssp_label}   ·   RCP: {rcp_display}\n"
            f"Damage Function: {dmg_label}   ·   Parameters: {par_label}   ·   Climate: {cli_label}\n"
            f"Discounting: {dis_label}   ·   Percentile: {pct_label}"
        )

        if reason in ("na", "missing"):
            msg = (
                "No data available for this combination in the DB - please change one or more selections above."
                if reason == "na" else
                "This combination was not found in the DB - please change one or more selections above."
            )
            self._lbl_scc.setText("No Result")
            self._lbl_scc.setStyleSheet(f"color: {get_token('danger')}; font-size: {FS_LG}pt; font-weight: {FW_SEMIBOLD};")
            self._lbl_range.setText("")
            self._lbl_params.setText(summary)
            self._lbl_params.setStyleSheet(f"color: {get_token('text_secondary')}; font-size: {FS_SM}pt; font-weight: {FW_NORMAL};")
            self._lbl_status.setText(msg)
            self._lbl_status.setStyleSheet(f"color: {get_token('danger')}; font-size: {FS_BASE}pt; font-weight: {FW_NORMAL};")
            if DEV_MODE:
                print(f"[RickeWidget] {msg}")
        else:
            lo, med, hi = result
            displayed = result[pct_idx]
            cpi_ratio    = self._field_map["cpi_ratio"].value()        if "cpi_ratio"        in self._field_map else 1.0
            usd_to_local = self._field_map["usd_to_local_rate"].value() if "usd_to_local_rate" in self._field_map else 1.0
            after_cpi    = displayed * cpi_ratio
            final        = after_cpi * usd_to_local
            adj_lo, adj_hi = lo * cpi_ratio * usd_to_local, hi * cpi_ratio * usd_to_local
            cpi_applied  = abs(cpi_ratio - 1.0) > 1e-6
            currency     = get_currency()

            if cpi_applied:
                scc_text = f"{final:,.{DECIMAL_PLACES}f} {currency} / tCO₂   (CPI-adjusted from {displayed:,.{DECIMAL_PLACES}f} in 2018 USD)"
                ci_text  = (
                    f"66.7% Confidence Interval:  {adj_lo:,.{DECIMAL_PLACES}f}  –  {adj_hi:,.{DECIMAL_PLACES}f} {currency} / tCO₂  (adjusted)\n"
                    f"                             {lo:,.{DECIMAL_PLACES}f}  –  {hi:,.{DECIMAL_PLACES}f} USD / tCO₂  (2018 USD)"
                )
            else:
                scc_text = f"{final:,.{DECIMAL_PLACES}f} {currency} / tCO₂   (2018 USD)"
                ci_text  = f"66.7% Confidence Interval:  {lo:,.{DECIMAL_PLACES}f}  –  {hi:,.{DECIMAL_PLACES}f} {currency} / tCO₂"

            self._lbl_scc.setText(scc_text)
            self._lbl_scc.setStyleSheet(f"color: {get_token('success')}; font-size: {FS_LG}pt; font-weight: {FW_SEMIBOLD};")
            self._lbl_range.setText(ci_text)
            self._lbl_range.setStyleSheet(f"color: {get_token('text_secondary')}; font-size: {FS_MD}pt; font-weight: {FW_NORMAL};")
            self._lbl_params.setText(summary)
            self._lbl_params.setStyleSheet(f"color: {get_token('text_secondary')}; font-size: {FS_SM}pt; font-weight: {FW_NORMAL};")

            breakdown = (
                f"① Raw (2018 USD):           {displayed:,.{DECIMAL_PLACES}f} USD/tCO₂\n"
                f"② After CPI (× {cpi_ratio}):     {after_cpi:,.{DECIMAL_PLACES}f} USD/tCO₂\n"
                f"③ Final (× {usd_to_local} {currency}/USD):  {final:,.{DECIMAL_PLACES}f} {currency}/tCO₂"
            )
            self._lbl_status.setText(breakdown)
            self._lbl_status.setStyleSheet(f"color: {get_token('text_secondary')}; font-size: {FS_SM}pt; font-weight: {FW_NORMAL};")

            if DEV_MODE:
                print(f"[RickeWidget] raw (2018 USD):        {displayed:,.{DECIMAL_PLACES}f} USD/tCO₂  CI=[{lo:,.{DECIMAL_PLACES}f}–{hi:,.{DECIMAL_PLACES}f}]")
                print(f"[RickeWidget] after CPI (ratio={cpi_ratio}): {after_cpi:,.{DECIMAL_PLACES}f} USD/tCO₂")
                print(f"[RickeWidget] final ({currency}, rate={usd_to_local}): {final:,.{DECIMAL_PLACES}f} {currency}/tCO₂  CI=[{adj_lo:,.{DECIMAL_PLACES}f}–{adj_hi:,.{DECIMAL_PLACES}f}]")

    def _clear_all(self):
        if not confirm_clear_all(self):
            return
        for widget in self._field_map.values():
            if isinstance(widget, QComboBox):
                widget.setCurrentIndex(0)
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(widget.minimum())
            elif isinstance(widget, QSpinBox):
                widget.setValue(widget.minimum())
            elif isinstance(widget, (QLineEdit, QTextEdit)):
                widget.clear()
            elif isinstance(widget, QCheckBox):
                widget.setChecked(False)

    def freeze(self, frozen: bool = True):
        freeze_form(RICKE_FIELDS, self, frozen)
        if not frozen:
            self._apply_country_lock()
        self._btn_clear.setEnabled(not frozen)

    def validate(self):
        result = validate_form(RICKE_FIELDS, self)
        if result["errors"]:
            return result

        # all required fields filled - also validate the DB combination
        fm = self._field_map
        ssp = _SSP_LABEL_MAP.get(fm["ssp"].currentText())
        rcp_raw = _RCP_LABEL_MAP.get(fm["rcp"].currentText())
        rcp = rcp_raw if rcp_raw is not None else _CLOSEST_RCP.get(ssp, "rcp60")
        run = _DMG_FUNC_LABEL_MAP.get(fm["dmg_func"].currentText())
        dmgfuncpar = _DMG_PARAMS_LABEL_MAP.get(fm["dmg_params"].currentText())
        climate = _CLIMATE_LABEL_MAP.get(fm["climate_uncertainty"].currentText())
        disc = _DISC_MAP.get(fm["discounting"].currentText())
        iso3 = fm["iso3"].currentText()

        if all(v is not None for v in (ssp, run, dmgfuncpar, climate, disc)):
            try:
                _, reason = _lookup(_get_db(), iso3, run, dmgfuncpar, climate, ssp, rcp, disc)
                if reason in ("na", "missing"):
                    result["errors"].append(
                        "Selected combination has no data in the DB - change this combination."
                    )
            except Exception:
                pass

        return result

    def clear_validation(self):
        clear_field_styles(RICKE_FIELDS, self)

    def get_cost(self) -> float | None:
        fm = self._field_map
        ssp_label = fm["ssp"].currentText()
        rcp_label = fm["rcp"].currentText()
        dmg_label = fm["dmg_func"].currentText()
        par_label = fm["dmg_params"].currentText()
        cli_label = fm["climate_uncertainty"].currentText()
        dis_label = fm["discounting"].currentText()
        pct_label = fm["percentile"].currentText()
        iso3      = fm["iso3"].currentText()

        if any(v == _PLACEHOLDER for v in (iso3, ssp_label, rcp_label, dmg_label, par_label, cli_label, dis_label, pct_label)):
            return None

        ssp        = _SSP_LABEL_MAP.get(ssp_label)
        rcp_raw    = _RCP_LABEL_MAP.get(rcp_label)
        rcp        = rcp_raw if rcp_raw is not None else _CLOSEST_RCP.get(ssp, "rcp60")
        run        = _DMG_FUNC_LABEL_MAP.get(dmg_label)
        dmgfuncpar = _DMG_PARAMS_LABEL_MAP.get(par_label)
        climate    = _CLIMATE_LABEL_MAP.get(cli_label)
        disc       = _DISC_MAP.get(dis_label)
        pct_idx    = _PERCENTILE_MAP.get(pct_label)

        if any(v is None for v in (ssp, run, dmgfuncpar, climate, disc, pct_idx)):
            return None

        try:
            result, reason = _lookup(_get_db(), iso3, run, dmgfuncpar, climate, ssp, rcp, disc)
        except Exception:
            return None

        if reason != "ok":
            return None

        cpi_ratio        = fm["cpi_ratio"].value()        if "cpi_ratio"        in fm else 1.0
        usd_to_local     = fm["usd_to_local_rate"].value() if "usd_to_local_rate" in fm else 1.0
        # DB values are USD/tCO₂; system expects currency/kgCO₂e → divide by 1000
        return result[pct_idx] * cpi_ratio * usd_to_local / 1000

    def get_ricke_data(self) -> dict:
        return self.get_data_dict()

    def get_result_data(self, selected_mode: str) -> dict:
        cost = self.get_cost()
        currency = get_currency()
        return {
            "selected_mode": selected_mode,
            "cost_of_carbon_local": cost if cost is not None else 0.0,
            "currency": currency,
            "unit": f"{currency}/kgCO₂e",
        }

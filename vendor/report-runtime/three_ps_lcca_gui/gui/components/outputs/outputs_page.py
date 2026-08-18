"""
gui/components/outputs/outputs_page.py
"""

import datetime
import json
import logging
import traceback as _tb_mod

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QSize, QThread, QTimer, Signal

from three_ps_lcca_gui.gui.themes import get_token, theme_manager
try:
    from three_ps_lcca_gui.gui._CONFIG import COMPARISON_MODE
except ImportError:
    COMPARISON_MODE = True
from three_ps_lcca_gui.gui.styles import font as _f, btn_primary, btn_ghost
from three_ps_lcca_gui.gui.theme import (
    SP1,
    SP2,
    SP3,
    SP4,
    SP5,
    SP6,
    RADIUS_LG,
    RADIUS_MD,
    FS_XS,
    FS_SM,
    FS_BASE,
    FS_MD,
    FS_LG,
    FS_SUBHEAD,
    FS_XL,
    FS_DISP,
    FW_NORMAL,
    FW_MEDIUM,
    FW_SEMIBOLD,
    FW_BOLD,
    BTN_MD,
    BTN_LG,
    FONT_FAMILY,
)
from three_ps_lcca_gui.gui.components.base_widget import ScrollableForm
from three_ps_lcca_gui.gui.components.utils.form_builder.form_definitions import (
    FieldDef,
    ValidationStatus,
)
from three_ps_lcca_gui.gui.components.utils.form_builder.form_builder import build_form
from three_ps_lcca_gui.gui.components.utils.common_requested_data import get_currency
from three_ps_lcca_gui.gui.components.utils.validation_helpers import (
    clear_field_styles,
    freeze_form,
    validate_form,
)
from three_ps_lcca_gui.gui.components.utils.display_format import fmt_currency
from .lcc_plot import LCCBreakdownTable, LCCDetailsTable
from .plots_helper.Pie import LCCPieWidget
from .plots_helper.AggregateChart import AggregateChartWidget
from .helper_functions.lifecycle_summary import compute_all_summaries
from .data_preparer import DataPreparer
from .report_section_dialog import ReportSectionDialog
from .calc_logic import _LCCAWorker

CHUNK = "outputs_data"
CHUNK_COMPARISON = "comparison_cache"

OUTPUTS_FIELDS = []

OUTPUTS_WARN_RULES = {}

_log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(
        f"background-color: {get_token('surface_pressed')}; "
        f"margin-top: {SP5}px; margin-bottom: {SP5}px; border: none;"
    )
    return line


def _section_heading(title: str) -> QLabel:
    lbl = QLabel(title)
    lbl.setWordWrap(True)
    lbl.setContentsMargins(0, SP6, 0, SP1)
    lbl.setFont(_f(FS_SUBHEAD, FW_BOLD))
    lbl.setStyleSheet(f"color: {get_token('text')};")
    return lbl


def _section_description(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setFont(_f(FS_MD))
    lbl.setStyleSheet(
        f"color: {get_token('text_secondary')}; margin-bottom: {SP4}px;"
    )
    return lbl


def _make_issue_card(page_name: str, issues: list, severity: str, navigate_cb) -> QFrame:
    """severity: 'error' or 'warning'"""
    border_color = get_token("danger" if severity == "error" else "warning")

    card = QFrame()
    card.setObjectName("issueCard")
    card.setStyleSheet(
        f"#issueCard {{"
        f"  border: 1px solid {get_token('surface_mid')};"
        f"  border-left: 4px solid {border_color};"
        f"  border-radius: {RADIUS_LG}px;"
        f"  background-color: {get_token('surface')};"
        f"}}"
    )
    layout = QVBoxLayout(card)
    layout.setContentsMargins(SP3, SP3, SP3, SP3)
    layout.setSpacing(SP3)

    # header: page name only
    name_lbl = QLabel(page_name.upper())
    name_lbl.setFont(_f(FS_SM, FW_MEDIUM))
    name_lbl.setStyleSheet(
        f"color: {get_token('text_secondary')}; letter-spacing: 1px; background: transparent;"
    )
    layout.addWidget(name_lbl)

    # issue rows
    for issue in issues:
        msg = issue if isinstance(issue, str) else issue.get("msg", str(issue))

        row = QHBoxLayout()
        row.setSpacing(SP1)

        dot_wrapper = QWidget()
        dot_wrapper.setFixedWidth(10)
        dot_wrapper.setStyleSheet("background: transparent;")
        dw_v = QVBoxLayout(dot_wrapper)
        dw_v.setContentsMargins(0, 0, 0, 0)
        dw_v.setSpacing(0)
        dw_v.addSpacing(6)
        dot = QFrame()
        dot.setFixedSize(6, 6)
        dot.setStyleSheet(
            f"background-color: {border_color}; border-radius: 3px;"
        )
        dw_v.addWidget(dot)
        dw_v.addStretch()
        row.addWidget(dot_wrapper, 0, Qt.AlignTop)

        txt_lbl = QLabel(msg)
        txt_lbl.setFont(_f(FS_BASE))
        txt_lbl.setStyleSheet(f"color: {get_token('text')}; background: transparent;")
        txt_lbl.setWordWrap(True)
        row.addWidget(txt_lbl, 1)

        layout.addLayout(row)

    # footer: button right-aligned below all issues
    footer = QWidget()
    footer.setStyleSheet("background: transparent;")
    f_lay = QHBoxLayout(footer)
    f_lay.setContentsMargins(0, 0, 0, SP2)
    f_lay.addStretch()

    go_btn = QPushButton("Fix Issues →" if severity == "error" else "Fix Warnings →")
    go_btn.setFixedHeight(BTN_MD)
    go_btn.setFixedWidth(140)
    go_btn.setFont(_f(FS_SM, FW_SEMIBOLD))
    if severity == "error":
        go_btn.setStyleSheet(btn_primary())
    else:
        go_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid {get_token('warning')}; border-radius: {RADIUS_MD}px;"
            f"  padding: 0 16px; background: transparent; color: {get_token('warning')};"
            f"  font-weight: {get_token('weight-semibold')}; }}"
            f"QPushButton:hover {{ background: transparent; color: {get_token('warning')}; border-width: 1.5px; }}"
        )
    go_btn.setCursor(Qt.PointingHandCursor)
    go_btn.clicked.connect(lambda checked=False, p=page_name: navigate_cb(p))
    f_lay.addWidget(go_btn)

    layout.addWidget(footer)

    return card


# ──────────────────────────────────────────────────────────────
# Summary cards
# ──────────────────────────────────────────────────────────────


class ResponsiveTotalCard(QFrame):
    def __init__(self, total_value: float, results: dict, currency: str,
                 analysis_period: int = 0, year_of_construction: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("kpiCard")
        self.setStyleSheet(
            f"#kpiCard {{"
            f"  background-color: {get_token('surface')};"
            f"  border: 1px solid {get_token('surface_mid')};"
            f"  border-top: 3px solid {get_token('primary')};"
            f"  border-radius: {RADIUS_LG}px;"
            f"}}"
        )
        self.setMinimumHeight(110)
        
        self.main_layout = QGridLayout(self)
        self.main_layout.setContentsMargins(SP5, SP4, SP5, SP4)
        self.main_layout.setSpacing(SP4)

        # LEFT SIDE: Total
        self.left_widget = QWidget()
        self.left_widget.setStyleSheet("background: transparent; border: none;")
        left_v = QVBoxLayout(self.left_widget)
        left_v.setContentsMargins(0, 0, 0, 0)
        left_v.setSpacing(0)
        
        title_lbl = QLabel("Total Life Cycle Cost")
        title_lbl.setFont(_f(FS_SM, FW_MEDIUM))
        title_lbl.setStyleSheet(f"color: {get_token('text_secondary')}; letter-spacing: 1px; border: none; background: transparent;")
        left_v.addWidget(title_lbl)
        left_v.addSpacing(SP2)
        
        val_str = fmt_currency(total_value, currency, decimals=0, style="short")
        val_lbl = QLabel(val_str)
        val_lbl.setFont(_f(FS_DISP, FW_BOLD))
        val_lbl.setStyleSheet(f"color: {get_token('primary')}; border: none; background: transparent;")
        left_v.addWidget(val_lbl)
        
        curr_lbl = QLabel(currency)
        curr_lbl.setFont(_f(FS_XS, FW_NORMAL))
        curr_lbl.setStyleSheet(f"color: {get_token('text_disabled')}; border: none; letter-spacing: 0.5px; background: transparent;")
        left_v.addWidget(curr_lbl)
        left_v.addStretch()

        # RIGHT SIDE: About this analysis
        _ap_str = f"{analysis_period} years" if analysis_period else "-"
        _yoc_str = str(year_of_construction) if year_of_construction else "-"
        _LOREM = (
            f"Total life cycle cost (across the three pillars) evaluated over an "
            f"analysis period of {_ap_str} at the assessment year {_yoc_str}."
        )
        
        self.right_widget = QWidget()
        self.right_widget.setStyleSheet("background: transparent; border: none;")
        right_v = QVBoxLayout(self.right_widget)
        right_v.setContentsMargins(0, 0, 0, 0)
        right_v.setSpacing(SP2)
        
        lorem_title = QLabel("About This Analysis")
        lorem_title.setFont(_f(FS_SM, FW_MEDIUM))
        lorem_title.setStyleSheet(f"color: {get_token('text_secondary')}; letter-spacing: 1px; border: none; background: transparent;")
        right_v.addWidget(lorem_title)
        
        lorem_lbl = QLabel(_LOREM)
        lorem_lbl.setWordWrap(True)
        lorem_lbl.setAlignment(Qt.AlignJustify)
        lorem_lbl.setFont(_f(FS_BASE))
        lorem_lbl.setStyleSheet(f"color: {get_token('text')}; border: none; background: transparent;")
        right_v.addWidget(lorem_lbl)
        right_v.addStretch()

        self.divider = QFrame()
        self.divider.setStyleSheet(f"background-color: {get_token('surface_mid')}; border: none;")
        
        self.is_narrow = None
        self._setup_layout(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        narrow = self.width() < 600
        if narrow != self.is_narrow:
            self.is_narrow = narrow
            self._setup_layout(narrow)

    def _setup_layout(self, narrow: bool):
        self.main_layout.removeWidget(self.left_widget)
        self.main_layout.removeWidget(self.divider)
        self.main_layout.removeWidget(self.right_widget)
        
        if narrow:
            self.divider.setFrameShape(QFrame.HLine)
            self.divider.setMinimumSize(0, 1)
            self.divider.setMaximumSize(16777215, 1)
            
            self.main_layout.addWidget(self.left_widget, 0, 0)
            self.main_layout.addWidget(self.divider, 1, 0)
            self.main_layout.addWidget(self.right_widget, 2, 0)
            self.main_layout.setColumnStretch(0, 1)
            self.main_layout.setColumnStretch(1, 0)
            self.main_layout.setColumnStretch(2, 0)
        else:
            self.divider.setFrameShape(QFrame.VLine)
            self.divider.setMinimumSize(1, 0)
            self.divider.setMaximumSize(1, 16777215)
            
            self.main_layout.addWidget(self.left_widget, 0, 0)
            self.main_layout.addWidget(self.divider, 0, 1)
            self.main_layout.addWidget(self.right_widget, 0, 2)
            self.main_layout.setColumnStretch(0, 0)
            self.main_layout.setColumnStretch(1, 0)
            self.main_layout.setColumnStretch(2, 1)


class LCCSummaryCards(QWidget):
    """
    Three-row KPI layout:
      Row 1 - Grand Total (full width)
      Row 2 - Economic / Environmental / Social  (pillar totals)
      Row 3 - Initial / Use / End-of-Life        (stage totals)
    """

    def __init__(self, results: dict, currency: str,
                 analysis_period: int = 0, year_of_construction: int = 0, parent=None):
        super().__init__(parent)
        self._results = results
        self._currency = currency
        self._analysis_period = analysis_period
        self._year_of_construction = year_of_construction
        self._setup_ui()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

    def _setup_ui(self):
        summary  = compute_all_summaries(self._results)
        stagewise = summary.get("stagewise", {})
        pt        = summary.get("pillar_totals", {})

        grand_total = sum(stagewise.values())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, SP3, 0, SP5)
        outer.setSpacing(SP3)

        # ── Row 1: Grand Total + description ─────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(SP3)
        row1.addWidget(ResponsiveTotalCard(
            grand_total, self._results, self._currency,
            analysis_period=self._analysis_period,
            year_of_construction=self._year_of_construction,
        ))
        outer.addLayout(row1)

        # ── Row 2: Pillar totals ──────────────────────────────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(SP3)
        for title, key, token in [
            ("Economic",      "eco",    "eco"),
            ("Environmental", "env",    "env"),
            ("Social",        "social", "soc"),
        ]:
            row2.addWidget(self._card(title, pt.get(key, 0), get_token(token)))
        outer.addLayout(row2)

        # ── Row 3: Stage totals ───────────────────────────────────────────
        row3 = QHBoxLayout()
        row3.setSpacing(SP3)
        for title, key, token in [
            ("Initial",     "initial",     "init"),
            ("Use",         "use",         "use"),
            ("End-of-Life", "end_of_life", "end"),
        ]:
            row3.addWidget(self._card(title, stagewise.get(key, 0), get_token(token)))
        outer.addLayout(row3)

    def _card(self, title: str, value: float, accent: str, large: bool = False) -> QFrame:
        card = QFrame()
        card.setObjectName("kpiCard")
        card.setStyleSheet(
            f"#kpiCard {{"
            f"  background-color: {get_token('surface')};"
            f"  border: 1px solid {get_token('surface_mid')};"
            f"  border-top: 3px solid {accent};"
            f"  border-radius: {RADIUS_LG}px;"
            f"}}"
        )

        v = QVBoxLayout(card)
        v.setContentsMargins(SP5, SP4, SP5, SP4)
        v.setSpacing(0)

        title_lbl = QLabel(title)
        title_lbl.setFont(_f(FS_SM, FW_MEDIUM))
        title_lbl.setStyleSheet(
            f"color: {get_token('text_secondary')}; letter-spacing: 1px; border: none;"
        )
        v.addWidget(title_lbl)
        v.addSpacing(SP2)

        val_str = fmt_currency(value, self._currency, decimals=0, style="short")
        val_lbl = QLabel(val_str)
        val_lbl.setFont(_f(FS_DISP if large else FS_XL, FW_BOLD))
        val_lbl.setStyleSheet(f"color: {accent}; border: none;")
        v.addWidget(val_lbl)

        curr_lbl = QLabel(self._currency)
        curr_lbl.setFont(_f(FS_XS, FW_NORMAL))
        curr_lbl.setStyleSheet(
            f"color: {get_token('text_disabled')}; border: none; letter-spacing: 0.5px;"
        )
        v.addWidget(curr_lbl)

        card.setMinimumHeight(110 if large else 90)
        return card


# ──────────────────────────────────────────────────────────────
# Report intro
# ──────────────────────────────────────────────────────────────


class LCCIntroWidget(QWidget):
    """One-paragraph context block shown at the top of every results report."""

    def __init__(self, results: dict, analysis_period: int, currency: str, parent=None):
        super().__init__(parent)
        self._build(results, analysis_period, currency)

    def _build(self, results: dict, analysis_period: int, currency: str):
        stages_present = []
        if results.get("initial_stage"):
            stages_present.append("Initial Construction")
        if results.get("use_stage"):
            stages_present.append("Use & Maintenance")
        if results.get("reconstruction"):
            stages_present.append("Reconstruction")
        if results.get("end_of_life"):
            stages_present.append("End-of-Life")
        stage_str = " → ".join(stages_present)

        ap_str = f"{analysis_period}-year" if analysis_period else "full"
        body = (
            f"This report presents a <b>{ap_str}</b> life-cycle cost analysis "
            f"in <b>{currency}</b>, covering: {stage_str}."
        )

        frame = QFrame(self)
        frame.setObjectName("introFrame")
        frame.setStyleSheet(
            f"#introFrame {{"
            f"  background-color: {get_token('surface')};"
            f"  border-left: 3px solid {get_token('primary')};"
            f"  border-top: 1px solid {get_token('surface_mid')};"
            f"  border-right: 1px solid {get_token('surface_mid')};"
            f"  border-bottom: 1px solid {get_token('surface_mid')};"
            f"  border-radius: {RADIUS_LG}px;"
            f"}}"
        )
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(SP5, SP4, SP5, SP4)
        fl.setSpacing(SP2)

        title = QLabel("About This Report")
        title.setFont(_f(FS_LG, FW_BOLD))
        title.setStyleSheet(f"color: {get_token('text')}; border: none;")
        fl.addWidget(title)

        lbl = QLabel(body)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.RichText)
        lbl.setFont(_f(FS_BASE))
        lbl.setStyleSheet(f"color: {get_token('text_secondary')}; border: none;")
        fl.addWidget(lbl)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)


# ──────────────────────────────────────────────────────────────
# Key findings / smart insights
# ──────────────────────────────────────────────────────────────


class LCCInsightsWidget(QWidget):
    """Auto-generated key findings computed directly from LCCA results."""

    _TOKEN_COLORS = {
        "primary": "primary",
        "warning": "warning",
        "danger": "danger",
        "success": "success",
        "text": "text_secondary",
    }

    def __init__(self, results: dict, currency: str, parent=None):
        super().__init__(parent)
        self._currency = currency
        self._build(results)

    def _build(self, results: dict):
        findings = self._compute(results)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName("insightsCard")
        card.setStyleSheet(
            f"#insightsCard {{"
            f"  background-color: {get_token('surface')};"
            f"  border: 1px solid {get_token('surface_mid')};"
            f"  border-radius: {RADIUS_LG}px;"
            f"}}"
        )
        card_v = QVBoxLayout(card)
        card_v.setContentsMargins(SP4, SP3, SP4, SP3)
        card_v.setSpacing(0)

        for i, (icon, color_token, html) in enumerate(findings):
            bullet_color = get_token(self._TOKEN_COLORS.get(color_token, "text_secondary"))

            if i > 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.HLine)
                sep.setFixedHeight(1)
                sep.setStyleSheet(
                    f"background-color: {get_token('surface_mid')}; border: none;"
                )
                card_v.addWidget(sep)

            row_frame = QFrame()
            row_frame.setStyleSheet("QFrame { background: transparent; border: none; }")
            row_h = QHBoxLayout(row_frame)
            row_h.setContentsMargins(0, SP3, 0, SP3)
            row_h.setSpacing(SP3)

            dot_wrapper = QWidget()
            dot_wrapper.setFixedWidth(10)
            dot_wrapper.setStyleSheet("background: transparent;")
            dw_v = QVBoxLayout(dot_wrapper)
            dw_v.setContentsMargins(0, 0, 0, 0)
            dw_v.setSpacing(0)
            dw_v.addSpacing(5)
            dot = QFrame()
            dot.setFixedSize(8, 8)
            dot.setStyleSheet(
                f"background-color: {bullet_color}; border-radius: 4px; border: none;"
            )
            dw_v.addWidget(dot)
            dw_v.addStretch()
            row_h.addWidget(dot_wrapper)

            lbl = QLabel(html)
            lbl.setWordWrap(True)
            lbl.setTextFormat(Qt.RichText)
            lbl.setFont(_f(FS_BASE))
            lbl.setStyleSheet(f"color: {get_token('text')}; background: transparent;")
            row_h.addWidget(lbl, 1)

            card_v.addWidget(row_frame)

        outer.addWidget(card)

    def _compute(self, r: dict) -> list:
        """Return list of (icon, color_token, html_text) tuples."""
        c = self._currency
        findings = []

        def _get(stage, pillar, key, default=0.0):
            return r.get(stage, {}).get(pillar, {}).get(key, default)

        def _stage_total(stage):
            return sum(
                sum(v.values()) if isinstance(v, dict) else 0
                for v in r.get(stage, {}).values()
                if isinstance(v, dict)
            )

        def _pillar_total(stage, pillar):
            return sum(r.get(stage, {}).get(pillar, {}).values())

        all_stages = ["initial_stage", "use_stage", "reconstruction", "end_of_life"]
        stage_totals_raw = {s: _stage_total(s) for s in all_stages}
        grand = sum(stage_totals_raw.values()) or 1.0

        eco_total = sum(_pillar_total(s, "economic") for s in all_stages)
        env_total = sum(_pillar_total(s, "environmental") for s in all_stages)
        soc_total = sum(_pillar_total(s, "social") for s in all_stages)

        stage_labels = {
            "initial_stage": "Initial Construction",
            "use_stage": "Use & Maintenance",
            "reconstruction": "Reconstruction",
            "end_of_life": "End-of-Life",
        }
        dominant = max(stage_totals_raw, key=stage_totals_raw.get)
        dom_pct = stage_totals_raw[dominant] / grand * 100
        dom_val = fmt_currency(stage_totals_raw[dominant], c, decimals=0, style="both")
        findings.append((
            "●", "primary",
            f"<b>{stage_labels[dominant]}</b> is the largest cost stage at "
            f"<b>{dom_pct:.0f}%</b> of total life cycle cost - {c} {dom_val}.",
        ))

        soc_pct = soc_total / grand * 100
        eco_pct = eco_total / grand * 100
        findings.append((
            "●", "warning",
            f"Road users carry <b>{soc_pct:.0f}%</b> of the total life cycle cost through traffic delays "
            f"and detours. This 'Social Cost' is often hidden from traditional budgets, which "
            f"primarily focus on the owner's direct spending (currently <b>{eco_pct:.0f}%</b>).",
        ))

        construction = _get("initial_stage", "economic", "initial_construction_cost")
        ruc_init = _get("initial_stage", "social", "initial_road_user_cost")
        if construction > 0 and ruc_init > 0:
            ratio = ruc_init / construction
            findings.append((
                "●", "danger",
                f"Building this bridge costs road users <b>{c} {fmt_currency(ruc_init, c, decimals=0, style='both')}</b> "
                f"in delays-that is <b>{ratio:.1f}× the construction contract value</b> "
                f"{c} {fmt_currency(construction, c, decimals=0, style='both')}. Faster construction directly reduces this social burden.",
            ))

        bej = _get("use_stage", "economic", "replacement_costs_for_bearing_and_expansion_joint")
        use_eco = _pillar_total("use_stage", "economic") or 1.0
        if bej > 0:
            bej_pct = bej / use_eco * 100
            findings.append((
                "●", "text",
                f"Bearing & expansion joint replacements account for <b>{bej_pct:.0f}%</b> of all "
                f"maintenance expenditure - {c} {fmt_currency(bej, c, decimals=0, style='both')}. "
                f"This is the single largest recurring maintenance cost item.",
            ))

        recon_soc = _pillar_total("reconstruction", "social")
        eol_soc = _pillar_total("end_of_life", "social")
        if recon_soc > 0 and eol_soc > 0:
            rd_ratio = recon_soc / eol_soc
            findings.append((
                "●", "warning",
                f"Mid-life reconstruction disrupts road users <b>{rd_ratio:.1f}× more</b> than "
                f"final end-of-life demolition - {c} {fmt_currency(recon_soc, c, decimals=0, style='both')} vs "
                f"{c} {fmt_currency(eol_soc, c, decimals=0, style='both')}. Minimising reconstruction frequency "
                f"has an outsized social benefit.",
            ))

        env_pct = env_total / grand * 100
        mat_c = _get("initial_stage", "environmental", "initial_material_carbon_emission_cost")
        veh_c = _get("initial_stage", "environmental", "initial_vehicular_emission_cost")
        carbon_note = ""
        if mat_c > 0 and veh_c > 0:
            mc_ratio = mat_c / veh_c
            carbon_note = (
                f" The environmental impact of construction materials is "
                f"<b>{mc_ratio:.0f}× higher</b> than the impact of vehicle detours during construction."
            )
        findings.append((
            "●", "success",
            f"Environmental (carbon) costs represent <b>{env_pct:.1f}%</b> of the total project "
            f"impact. While smaller than economic costs, they represent the project's direct "
            f"contribution to climate change.{carbon_note}",
        ))

        scrap_recon = _get("reconstruction", "economic", "total_scrap_value")
        scrap_eol = _get("end_of_life", "economic", "total_scrap_value")
        if scrap_recon == 0 and scrap_eol == 0:
            findings.append((
                "●", "text",
                "No residual or scrap value is recovered at reconstruction or end-of-life. "
                "Designing for material recovery (steel, aggregate) could offset demolition costs.",
            ))

        loan_init = _get("initial_stage", "economic", "time_cost_of_loan")
        if loan_init > 0 and construction > 0:
            loan_pct = loan_init / construction * 100
            findings.append((
                "●", "text",
                f"Financing cost over the loan period is <b>{loan_pct:.1f}%</b> of construction value "
                f"{c} {fmt_currency(loan_init, c, decimals=0, style='both')} - a relatively small component of total cost.",
            ))

        return findings


# ──────────────────────────────────────────────────────────────
# Main outputs page
# ──────────────────────────────────────────────────────────────


class OutputsPage(ScrollableForm):
    navigate_requested = Signal(str)
    calculation_completed = Signal()
    validate_requested = Signal()
    compare_requested = Signal(str)

    CALC_TIMEOUT_MS = 30_000

    def __init__(self, controller=None):
        super().__init__(controller=controller, chunk_name=CHUNK)
        self._pages = {}
        self._has_results = False
        self._calc_thread = None
        self._calc_worker = None
        self._timeout_timer = None
        self._elapsed_timer = None
        self._elapsed_secs = 0
        self._currency = ""
        self._current_status = "idle"
        self._status_args: dict = {}
        self._build_ui()
        theme_manager().theme_changed.connect(self._refresh_styles)

    # ── Layout construction ───────────────────────────────────

    def _build_ui(self):
        f = self.form

        self._header = QLabel("Results")
        self._header.setFont(_f(FS_DISP, FW_BOLD))
        self._header.setStyleSheet(
            f"color: {get_token('text')}; margin-bottom: {SP2}px;"
        )
        f.addRow(self._header)

        self.required_keys = build_form(self, OUTPUTS_FIELDS)

        self._btn_row = QWidget()
        btn_layout = QHBoxLayout(self._btn_row)
        btn_layout.setContentsMargins(0, SP3, 0, SP5)

        self.btn_calculate = QPushButton("Validate inputs")
        self.btn_calculate.setFixedHeight(BTN_LG)
        self.btn_calculate.setFixedWidth(180)
        self.btn_calculate.setFont(_f(FS_MD, FW_MEDIUM))
        self.btn_calculate.setStyleSheet(btn_primary())
        self.btn_calculate.clicked.connect(self.validate_requested.emit)
        btn_layout.addWidget(self.btn_calculate)
        btn_layout.addStretch()
        f.addRow(self._btn_row)

        self._status_widget = QWidget()
        self._status_layout = QVBoxLayout(self._status_widget)
        self._status_layout.setContentsMargins(0, 0, 0, 0)
        self._status_layout.setSpacing(SP4)
        f.addRow(self._status_widget)

        self._show_idle()

    # ── Theme refresh ─────────────────────────────────────────

    def _refresh_styles(self):
        self._header.setFont(_f(FS_DISP, FW_BOLD))
        self._header.setStyleSheet(
            f"color: {get_token('text')}; margin-bottom: {SP2}px;"
        )
        self.btn_calculate.setStyleSheet(btn_primary())
        s = self._current_status
        if s == "idle":
            self._show_idle()
        elif s == "issues":
            self.show_results(
                self._status_args["errors"], self._status_args["warnings"]
            )
        elif s == "success":
            self.show_success()
        elif s == "calc_error":
            self._show_calculation_error(
                self._status_args["error"], self._status_args.get("tb", "")
            )
        elif s == "calc_success" and hasattr(self, "_last_results"):
            self._show_calculation_success(self._last_results)

    # ── Status area helpers ───────────────────────────────────

    def _clear_status(self):
        while self._status_layout.count():
            item = self._status_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _set_inputs_visible(self, visible: bool):
        f = self.form
        for row in range(1, f.rowCount() - 1):
            for role in (
                QFormLayout.FieldRole,
                QFormLayout.SpanningRole,
                QFormLayout.LabelRole,
            ):
                item = f.itemAt(row, role)
                if item and item.widget():
                    item.widget().setVisible(visible)

    def _inline_banner(self, text: str, token: str) -> QWidget:
        """Status banner with a coloured left strip."""
        outer = QWidget()
        h = QHBoxLayout(outer)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        strip = QFrame()
        strip.setFixedWidth(3)
        strip.setStyleSheet(f"background-color: {get_token(token)}; border-radius: 2px;")
        h.addWidget(strip)

        inner = QFrame()
        inner.setStyleSheet("QFrame { background: transparent; border: none; }")
        v = QVBoxLayout(inner)
        v.setContentsMargins(SP3, SP2, SP3, SP2)
        lbl = QLabel(text)
        lbl.setFont(_f(FS_BASE, FW_MEDIUM))
        lbl.setStyleSheet(f"color: {get_token(token)}; background: transparent;")
        v.addWidget(lbl)
        h.addWidget(inner, 1)

        return outer

    # ── State: idle ───────────────────────────────────────────

    def _show_idle(self):
        self._current_status = "idle"
        self._clear_status()
        self._set_inputs_visible(True)

        card = QFrame()
        card.setObjectName("idleCard")
        card.setStyleSheet(
            f"#idleCard {{"
            f"  background-color: {get_token('surface')};"
            f"  border-left: 3px solid {get_token('primary')};"
            f"  border-top: 1px solid {get_token('surface_mid')};"
            f"  border-right: 1px solid {get_token('surface_mid')};"
            f"  border-bottom: 1px solid {get_token('surface_mid')};"
            f"  border-radius: {RADIUS_LG}px;"
            f"}}"
        )
        card_v = QVBoxLayout(card)
        card_v.setContentsMargins(SP4, SP3, SP4, SP3)

        hint = QLabel(
            "Press Validate to check all input pages before running the "
            "life-cycle cost calculation."
        )
        hint.setFont(_f(FS_BASE))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {get_token('text_secondary')}; background: transparent;")
        card_v.addWidget(hint)

        self._status_layout.addWidget(card)

    # ── State: calculating ────────────────────────────────────

    def _show_calculating(self):
        self._current_status = "calculating"
        self._clear_status()
        self.btn_calculate.setEnabled(False)

        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(SP4, SP4, SP4, SP4)
        v.setSpacing(SP3)

        h_row = QWidget()
        h = QHBoxLayout(h_row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(SP2)

        status_lbl = QLabel("Running life-cycle cost analysis…")
        status_lbl.setFont(_f(FS_MD, FW_MEDIUM))
        h.addWidget(status_lbl)
        h.addStretch()

        self._elapsed_label = QLabel("0 s")
        self._elapsed_label.setFont(_f(FS_SM))
        self._elapsed_label.setStyleSheet(
            f"color: {get_token('text_secondary')}; background: transparent;"
        )
        h.addWidget(self._elapsed_label)
        v.addWidget(h_row)

        activity_bar = QProgressBar()
        activity_bar.setRange(0, 0)
        activity_bar.setTextVisible(False)
        activity_bar.setFixedHeight(6)
        v.addWidget(activity_bar)

        self._status_layout.addWidget(container)

        self._elapsed_secs = 0
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        self._elapsed_timer.start()

        self._timeout_timer = QTimer(self)
        self._timeout_timer.setSingleShot(True)
        self._timeout_timer.setInterval(self.CALC_TIMEOUT_MS)
        self._timeout_timer.timeout.connect(self._on_calc_timeout)
        self._timeout_timer.start()

    def _tick_elapsed(self):
        self._elapsed_secs += 1
        if hasattr(self, "_elapsed_label"):
            self._elapsed_label.setText(f"{self._elapsed_secs} s")

    def _stop_timers(self):
        if self._timeout_timer:
            self._timeout_timer.stop()
            self._timeout_timer.deleteLater()
            self._timeout_timer = None
        if self._elapsed_timer:
            self._elapsed_timer.stop()
            self._elapsed_timer.deleteLater()
            self._elapsed_timer = None

    def _on_calc_timeout(self):
        self._stop_timers()
        if self._calc_worker:
            self._calc_worker.cancel()
        self.btn_calculate.setEnabled(True)
        self._show_calculation_error(
            TimeoutError("Analysis timed out after 30 seconds."), ""
        )

    # ── State: validation issues ──────────────────────────────

    def show_results(self, all_errors: dict, all_warnings: dict):
        self._current_status = "issues"
        self._status_args = {"errors": all_errors, "warnings": all_warnings}
        self._clear_status()
        self._set_inputs_visible(True)
        self._save_state("issues", {"errors": all_errors, "warnings": all_warnings})

        if all_errors:
            self._status_layout.addWidget(
                self._inline_banner("Insufficient or Incorrect information; Fix the errors below", "danger")
            )
            for page, issues in all_errors.items():
                self._status_layout.addWidget(
                    _make_issue_card(page, issues, "error", self.navigate_requested.emit)
                )

        if all_warnings:
            self._status_layout.addWidget(
                self._inline_banner("Warnings - Review before proceeding", "warning")
            )
            for page, issues in all_warnings.items():
                self._status_layout.addWidget(
                    _make_issue_card(page, issues, "warning", self.navigate_requested.emit)
                )

        if not all_errors:
            run_btn = QPushButton("Run the Life Cycle Cost (LCC) analysis")
            run_btn.setFixedHeight(BTN_LG)
            run_btn.setStyleSheet(btn_primary())
            run_btn.clicked.connect(self._on_proceed)
            self._status_layout.addWidget(run_btn)

        self._status_layout.addStretch()

    # ── State: validation passed ──────────────────────────────

    def show_success(self):
        self._current_status = "success"
        self._clear_status()
        self._set_inputs_visible(True)
        self._save_state("success", {})
        self._status_layout.addWidget(
            self._inline_banner(
                "All checks passed - calculation will start automatically", "success"
            )
        )
        self._status_layout.addStretch()

    # ── State: calculation error ──────────────────────────────

    @staticmethod
    def _extract_relevant_frame(tb: str) -> str:
        """Return the last traceback frame that belongs to project code (not site-packages)."""
        if not tb:
            return ""
        frames = []
        lines = tb.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("File ") and i + 1 < len(lines):
                if "site-packages" not in line and "lib\\python" not in line.lower():
                    frames.append(f"{stripped}\n    {lines[i + 1].strip()}")
        return frames[-1] if frames else ""

    def _show_calculation_error(self, error: Exception, tb: str = ""):
        self._current_status = "calc_error"
        self._status_args = {"error": error, "tb": tb}
        self._save_state("calc_error", {"error": str(error)})
        self.btn_calculate.setEnabled(True)
        self._set_inputs_visible(True)
        self._clear_status()

        card = QFrame()
        card.setObjectName("calcErrorCard")
        card.setStyleSheet(
            f"#calcErrorCard {{"
            f"  background-color: {get_token('surface')};"
            f"  border: 1px solid {get_token('surface_mid')};"
            f"  border-left: 4px solid {get_token('danger')};"
            f"  border-radius: {RADIUS_LG}px;"
            f"}}"
        )
        v = QVBoxLayout(card)
        v.setContentsMargins(SP4, SP4, SP4, SP4)
        v.setSpacing(SP2)

        title_lbl = QLabel(f"Analysis Failed: {type(error).__name__}")
        title_lbl.setFont(_f(FS_MD, FW_SEMIBOLD))
        title_lbl.setStyleSheet(
            f"color: {get_token('danger')}; background: transparent;"
        )
        v.addWidget(title_lbl)

        full_msg = str(error).strip() or "An unknown error occurred."
        msg_lbl = QLabel(full_msg)
        msg_lbl.setFont(_f(FS_BASE))
        msg_lbl.setWordWrap(True)
        msg_lbl.setStyleSheet(
            f"color: {get_token('text_secondary')}; background: transparent;"
        )
        v.addWidget(msg_lbl)

        relevant_frame = self._extract_relevant_frame(tb)
        if relevant_frame:
            frame_box = QFrame()
            frame_box.setStyleSheet(
                f"QFrame {{ background-color: {get_token('surface_pressed')};"
                f"  border: 1px solid {get_token('surface_mid')};"
                f"  border-radius: {RADIUS_MD}px; }}"
            )
            fb_v = QVBoxLayout(frame_box)
            fb_v.setContentsMargins(SP3, SP2, SP3, SP2)

            origin_lbl = QLabel("Origin")
            origin_lbl.setFont(_f(FS_XS, FW_MEDIUM))
            origin_lbl.setStyleSheet(
                f"color: {get_token('text_disabled')}; letter-spacing: 1px; background: transparent; border: none;"
            )
            fb_v.addWidget(origin_lbl)

            frame_lbl = QLabel(relevant_frame)
            frame_lbl.setFont(QFont("Courier New", FS_XS))
            frame_lbl.setWordWrap(True)
            frame_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            frame_lbl.setStyleSheet(
                f"color: {get_token('danger')}; background: transparent; border: none;"
            )
            fb_v.addWidget(frame_lbl)
            v.addWidget(frame_box)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(SP3)
        btn_row.setContentsMargins(0, SP2, 0, 0)

        retry_btn = QPushButton("Retry")
        retry_btn.setFixedHeight(BTN_MD)
        retry_btn.setFont(_f(FS_BASE, FW_MEDIUM))
        retry_btn.setStyleSheet(btn_primary())
        retry_btn.clicked.connect(self.validate_requested.emit)
        btn_row.addWidget(retry_btn)

        dl_btn = QPushButton("Download Error Log")
        dl_btn.setFixedHeight(BTN_MD)
        dl_btn.setFont(_f(FS_BASE, FW_MEDIUM))
        dl_btn.setStyleSheet(
            f"QPushButton {{ border: 1px solid {get_token('danger')}; border-radius: {RADIUS_MD}px;"
            f"  padding: 0 16px; background: transparent; color: {get_token('danger')};"
            f"  font-weight: {get_token('weight-semibold')}; }}"
            f"QPushButton:hover {{ border-width: 1.5px; }}"
        )
        dl_btn.clicked.connect(lambda: self._download_error_log(error, tb))
        btn_row.addWidget(dl_btn)

        btn_row.addStretch()
        v.addLayout(btn_row)

        self._status_layout.addWidget(card)
        self._status_layout.addStretch()

    def _download_error_log(self, error: Exception, tb: str):
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"lcca_error_{ts}.txt"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Error Log", default_name, "Text Files (*.txt);;All Files (*)"
        )
        if not path:
            return

        lines = [
            f"3psLCCA Error Log",
            f"Generated : {datetime.datetime.now().isoformat()}",
            f"{'='*60}",
            f"",
            f"Error Type : {type(error).__name__}",
            f"Error      : {error}",
            f"",
            f"{'='*60}",
            f"Traceback",
            f"{'='*60}",
            tb or _tb_mod.format_exc() or "(no traceback available)",
            f"",
            f"{'='*60}",
            f"Input Data Snapshot",
            f"{'='*60}",
        ]

        all_data = getattr(self, "_last_all_data", None)
        if all_data:
            try:
                lines.append(json.dumps(all_data, indent=2, default=str))
            except Exception as e:
                lines.append(f"(could not serialise input data: {e})")
        else:
            lines.append("(no input data captured — error occurred before calculation started)")

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            _log.error("Failed to write error log: %s", e)

    # ── State: calculation success ────────────────────────────

    def _show_calculation_success(self, results):
        self._current_status = "calc_success"
        self.btn_calculate.setEnabled(True)
        self._set_inputs_visible(False)
        self._last_results = results
        self._clear_status()

        # Toolbar for results (PDF + Comparison)
        toolbar_row = QWidget()
        tl_h = QHBoxLayout(toolbar_row)
        tl_h.setContentsMargins(0, 0, 0, SP3)
        tl_h.setSpacing(SP3)

        pdf_btn = QPushButton("Generate PDF Report")
        pdf_btn.setFixedHeight(BTN_MD)
        pdf_btn.setFont(_f(FS_BASE, FW_MEDIUM))
        pdf_btn.setStyleSheet(btn_primary())
        pdf_btn.clicked.connect(self._generate_pdf_report)
        tl_h.addWidget(pdf_btn)

        # prov_btn = QPushButton("Generate Report V2")
        # prov_btn.setFixedHeight(BTN_MD)
        # prov_btn.setFont(_f(FS_BASE, FW_MEDIUM))
        # prov_btn.setStyleSheet(btn_primary())
        # prov_btn.clicked.connect(self._generate_provenance_report)
        # tl_h.addWidget(prov_btn)

        if COMPARISON_MODE:
            comp_btn = QPushButton("Add to Comparison ↗")
            comp_btn.setFixedHeight(BTN_MD)
            comp_btn.setFont(_f(FS_BASE, FW_MEDIUM))
            comp_btn.setStyleSheet(btn_ghost())
            comp_btn.setToolTip("Close project and add to the comparison workspace")
            comp_btn.clicked.connect(self._on_compare_clicked)
            tl_h.addWidget(comp_btn)

        tl_h.addStretch()
        self._status_layout.addWidget(toolbar_row)

        _bd = getattr(self, "_last_all_data", {}).get("bridge_data", {})
        _ap = int(_bd.get("analysis_period", 0))
        _yoc = int(_bd.get("year_of_construction", 0))

        sections = [
            lambda r: _section_heading("Summary"),
            lambda r: LCCSummaryCards(r, currency=self._currency,
                                      analysis_period=_ap, year_of_construction=_yoc),
            lambda r: _divider(),
            lambda r: _section_heading("Distribution of LCC"),
            lambda r: _section_description(
                "These charts illustrate the distribution of the total life cycle cost. The Sustainability Matrix disaggregates costs across the Economic, Environmental, and Social Pillars. The aggregation chart compares the relative weight of three life cycle phases: Initial Construction, the combined Use/Maintenance/Reconstruction stage, and the final End-of-Life phase."
            ),
            lambda r: LCCPieWidget(r, currency=self._currency),
            lambda r: AggregateChartWidget(r, currency=self._currency),
            lambda r: _divider(),
            lambda r: _section_heading("Consolidated stage summary"),
            lambda r: _section_description(
                "A consolidated presentation of costs across the three pillars (economic, social, and environmental) for each life cycle stage. This table facilitates the identification of phases that bear the most substantial burden."
            ),
            lambda r: LCCDetailsTable(r, currency=self._currency),
            lambda r: _divider(),
            # lambda r: _section_heading("Itemized detail"),
            # lambda r: _section_description(
            #     "An itemised schedule of each individual cost component. All values are discounted to the year of assessment, thus representing the present sum of money required to meet future expenditures."
            # ),
            lambda r: LCCBreakdownTable(r, currency=self._currency),
        ]
        QTimer.singleShot(0, lambda: self._build_result_widgets(results, sections))

    def _build_result_widgets(self, results, sections):
        insert_pos = 1  # pdf_row is at 0; insert result sections after it
        for factory in sections:
            try:
                widget = factory(results)
                if widget:
                    self._status_layout.insertWidget(insert_pos, widget)
                    insert_pos += 1
            except Exception as e:
                err = QLabel(f"Render error: {e}")
                err.setFont(_f(FS_BASE, italic=True))
                err.setStyleSheet(f"color: {get_token('text_secondary')};")
                self._status_layout.insertWidget(insert_pos, err)
                insert_pos += 1

        scroll = self.layout.itemAt(0).widget()
        if scroll and hasattr(scroll, "verticalScrollBar"):
            scroll.verticalScrollBar().setValue(0)

    # ── Page wiring ───────────────────────────────────────────

    def register_pages(self, widget_map: dict):
        self._pages = {
            n: p
            for n, p in widget_map.items()
            if n != "Results" and hasattr(p, "validate")
        }

    # ── Validation & calculation ──────────────────────────────

    def run_validation(self):
        all_errors = {}
        all_warnings = {}

        for name, page in self._pages.items():
            res = page.validate()
            if isinstance(res, dict):
                if res.get("errors"):
                    all_errors[name] = res["errors"]
                if res.get("warnings"):
                    all_warnings[name] = res["warnings"]
            else:
                status, issues = res
                if status == ValidationStatus.ERROR:
                    all_errors[name] = issues
                elif status == ValidationStatus.WARNING:
                    all_warnings[name] = issues

        if all_errors or all_warnings:
            self.show_results(all_errors, all_warnings)
        else:
            self.show_success()
            self.run_calculation()

    def run_calculation(self, save_cache: bool = True):
        self._save_cache_on_finish = save_cache
        all_data = {}
        for name, page in self._pages.items():
            if hasattr(page, "get_data"):
                res = page.get_data()
                all_data[res["chunk"]] = res["data"]

        # ── DEBUG: dump all_data to JSON file ──────────────────
        # import json, os, datetime as _dt
        # _dump_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "debug_dumps")
        # os.makedirs(_dump_dir, exist_ok=True)
        # _ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        # _dump_path = os.path.join(_dump_dir, f"all_data_{_ts}.json")
        # try:
        #     with open(_dump_path, "w", encoding="utf-8") as _fp:
        #         json.dump(all_data, _fp, indent=2, default=str)
        #     _log.info("DEBUG: all_data dumped to %s", _dump_path)
        # except Exception as _e:
        #     _log.warning("DEBUG: failed to dump all_data: %s", _e)
        # ── END DEBUG ──────────────────────────────────────────

        self._last_all_data = all_data
        self._currency = get_currency()
        self._show_calculating()

        self._calc_thread = QThread(self)
        ap = int(all_data.get("bridge_data", {}).get("analysis_period", 0))
        self._calc_worker = _LCCAWorker(all_data, ap)
        self._calc_worker.moveToThread(self._calc_thread)

        self._calc_thread.started.connect(self._calc_worker.run)
        self._calc_worker.finished.connect(self._on_calc_finished)
        self._calc_worker.errored.connect(self._on_calc_errored)
        self._calc_worker.finished.connect(self._calc_thread.quit)
        self._calc_worker.errored.connect(self._calc_thread.quit)
        self._calc_thread.finished.connect(self._calc_thread.deleteLater)

        QTimer.singleShot(0, self._calc_thread.start)

    def _on_calc_finished(self, results, all_data, lcc_breakdown):
        self._stop_timers()
        self._has_results = True
        self._last_all_data = all_data
        self._last_lcc_breakdown = lcc_breakdown
        
        if COMPARISON_MODE and getattr(self, "_save_cache_on_finish", True):
            self._write_comparison_cache(results, all_data, lcc_breakdown)
            
        self._show_calculation_success(results)
        self.calculation_completed.emit()

    def _on_calc_errored(self, exc, tb):
        self._stop_timers()
        self._show_calculation_error(exc, tb)

    # ── Toolbar / public API ──────────────────────────────────

    def reset_for_edit(self):
        self._has_results = False
        self._show_idle()
        self._save_state("idle", {})
        if COMPARISON_MODE:
            self._destroy_comparison_cache()

    def freeze(self, frozen: bool):
        self.btn_calculate.setEnabled(not frozen)
        freeze_form(OUTPUTS_FIELDS, self, frozen)

    def clear_validation(self):
        clear_field_styles(OUTPUTS_FIELDS, self)

    def validate(self):
        return validate_form(OUTPUTS_FIELDS, self, warn_rules=OUTPUTS_WARN_RULES)

    def get_export_data(self) -> dict | None:
        """Return all computed data for export, or None if no results exist yet."""
        if not self._has_results:
            return None
        return {
            "all_data": getattr(self, "_last_all_data", {}),
            "results": getattr(self, "_last_results", {}),
            "lcc_breakdown": getattr(self, "_last_lcc_breakdown", {}),
            "analysis_period": int(getattr(self, "_last_all_data", {}).get("bridge_data", {}).get("analysis_period", 0)),
            "currency": self._currency,
        }

    def _build_export_dict(self) -> dict:
        d = DataPreparer.build_export_dict(
            getattr(self, "_last_all_data", {}),
            getattr(self, "_last_lcc_breakdown", {}),
            getattr(self, "_last_results", {}),
        )
        if self.controller:
            d["project_name"] = (
                self.controller.active_display_name or self.controller.active_project_id
            )
        return d
    
    def _generate_pdf_report(self):
        dlg = ReportSectionDialog(
            export_dict=self._build_export_dict(),
            mode="lcca_v3",
            controller=self.controller,
            parent=self,
        )
        dlg.exec()

    # def _generate_pdf_report(self):
    #     dlg = ReportSectionDialog(export_dict=self._build_export_dict(), mode="provenance", parent=self)
    #     dlg.exec()

    # def _generate_provenance_report(self):
    #     """Triggers the modular V2 report generation using the tree-based dialog."""
    #     dlg = ReportSectionDialog(export_dict=self._build_export_dict(), mode="provenance", parent=self)
    #     dlg.exec()

    def _on_proceed(self):
        self.run_calculation()

    def _on_compare_clicked(self):
        if self.controller and self.controller.active_project_id:
            self.compare_requested.emit(self.controller.active_project_id)

    def _write_comparison_cache(self, results: dict, all_data: dict, lcc_breakdown: dict):
        if self.controller:
            self.controller.save_chunk_data(CHUNK_COMPARISON, {
                "is_valid": True,
                "analysis_period": int(all_data.get("bridge_data", {}).get("analysis_period", 0)),
                "currency": self._currency,
                "all_data": all_data,
                "lcc_breakdown": lcc_breakdown,
                "results": results,
            })
            if self.controller.engine:
                self.controller.engine.force_sync()
                self.controller.engine.write_user_meta("fit_for_comparison", True)

    def _destroy_comparison_cache(self):
        if self.controller and self.controller.engine:
            self.controller.engine.delete_chunk(CHUNK_COMPARISON)
            self.controller.engine.write_user_meta("fit_for_comparison", False)

    def _save_state(self, status: str, data: dict):
        if self.controller and self.controller.engine:
            self.controller.engine.stage_update(
                chunk_name=self.chunk_name, data={"status": status, "data": data}
            )

    def on_refresh(self):
        if self.controller and self.controller.engine:
            state = self.controller.engine.fetch_chunk(CHUNK) or {}
            s = state.get("status", "idle")
            d = state.get("data", {})
            if s == "issues":
                self.show_results(d.get("errors", {}), d.get("warnings", {}))
            elif s == "success":
                self.show_success()
            else:
                self._show_idle()

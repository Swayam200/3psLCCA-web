# ===========================================================================
# ASSUMPTIONS
# ===========================================================================
# 1. TRIPS ARE PER-MATERIAL, WITH OPTIONAL POOLING
#    By default, trips are calculated per unique material name - the same
#    material used across multiple processes is pooled into one shipment.
#    Example (pooled, default): Vehicle capacity = 100 kg
#             Steel (foundation) = 60 kg  ┐ pooled → 120 kg → 2 trips
#             Steel (columns)    = 60 kg  ┘
#             Timber             = 10 kg              → 1 trip
#             Total = 3 trips
#
#    With "Pool same materials" OFF, every row is treated independently:
#    Example (not pooled):
#             Steel (foundation) = 60 kg → 1 trip
#             Steel (columns)    = 60 kg → 1 trip
#             Timber             = 10 kg → 1 trip
#             Total = 3 trips  (same here, but differs when pooled > capacity)
#
#    The user can toggle this with the "Pool same materials" checkbox.
#
# 2. RETURN TRIP EMISSION
#    Every loaded trip incurs one empty return trip.
#    Emission = Σ_material[ trips_i * (gross * dist * ef)          ← loaded
#                         + trips_i * (empty_weight * dist * ef) ] ← return
#    where empty_weight = gross_weight − payload_capacity.
#
# 3. TRIPS DISPLAY
#    Trips count is purely informational - no colour warning is applied.
#    The number simply reflects how many vehicle loads are needed given
#    the selected materials, capacity, and pooling mode.
#
# 4. CHECKBOX GUARD
#    A material row's checkbox is DISABLED (greyed out, not just skipped) when
#    kg_factor == 0, preventing selection of rows with no kg/unit data.
#    For editable rows (non-mass units), the checkbox is re-enabled the moment
#    the user types a valid value into the kg/unit field, and disabled again
#    (and auto-unchecked) if the field is cleared. This is enforced both at
#    row-creation time (_populate_materials) and live via _on_factor_changed.
#
# 5. EMISSION FACTOR DEFAULT
#    The EF shown on the vehicle class card is the suggested default.
#    It is replaced immediately if the user expands Advanced and edits the
#    EF field.  Switching vehicle class resets EF to the class default.
#
# 6. CUSTOM VEHICLE DETECTION
#    A vehicle is "custom" when the user overrides capacity or emission factor
#    from the selected class defaults. gross_weight is excluded - it always
#    derives from capacity + tare, so it changing is a consequence not an
#    independent override.
#    Detection (_is_custom_vehicle) compares live spinbox values against
#    _CLASSES[selected_cls] defaults at call time - no extra flag needed.
#    Effects:
#      - Summary panel shows "HDV Large ★" with a tooltip when custom.
#      - Saved dict includes is_custom: True/False so callers can label/filter.
# ===========================================================================

import math
import uuid
import datetime
from three_ps_lcca_gui.gui.themes import get_token

from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QFrame,
    QMessageBox,
    QCheckBox,
    QAbstractItemView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QDoubleValidator

from ...utils.table_widgets import (
    TableLineEdit,
    mark_editable_column,
    TooltipTableMixin,
)
from ...utils.definitions import STRUCTURE_CHUNKS, UNIT_DIMENSION, UNIT_DISPLAY
from ...utils.display_format import fmt, fmt_comma, DECIMAL_PLACES
from ...utils.doc_link import doc_inline, doc_label


class _TransportTable(TooltipTableMixin, QTableWidget):
    """QTableWidget with tooltip + word-wrap for transport material rows."""


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f


# ---------------------------------------------------------------------------
# Single-page Transport Dialog
# ---------------------------------------------------------------------------


class TransportDialog(QDialog):
    """
    Single-page dialog for adding / editing a transport delivery entry.

    Layout
    ──────
    Config    : 3-column panel for Route, Vehicle, and Parameters
    ── divider ──
    Main area : left = material picker  |  right = live delivery summary
    Footer    : Save / Cancel
    """

    def __init__(self, controller, assigned_uuids: set, data: dict = None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.assigned_uuids = assigned_uuids
        self.is_edit = data is not None
        self.existing_data = data or {}

        self._rows_metadata = []
        self._hide_assigned = False
        self._pool_materials = True

        self.setWindowTitle("Edit Delivery" if self.is_edit else "Add Delivery")
        self.setMinimumSize(1020, 700)
        self.setWindowFlags(
            Qt.Window
            | Qt.WindowTitleHint
            | Qt.WindowSystemMenuHint
            | Qt.WindowCloseButtonHint
            | Qt.WindowMaximizeButtonHint
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 12)
        outer.setSpacing(10)

        self._build_config_panel(outer)
        outer.addWidget(_divider())
        self._build_main_area(outer)
        self._build_footer(outer)

        self._populate_materials()

        if self.is_edit:
            self._load_existing()
        else:
            # Defaults for new entry
            self.capacity_in.setValue(0.0)
            self.gross_in.setValue(0.0)
            self.ef_in.setValue(0.0)

        # FINAL STABILIZATION PASS
        mark_editable_column(self.mat_table, 4)
        self.mat_table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self._update_summary()

    # ── Configuration panel ───────────────────────────────────────────

    def _build_config_panel(self, layout):
        container = QFrame()
        container.setObjectName("config_panel")
        container.setStyleSheet(f"""
            QFrame#config_panel {{
                background-color: {get_token('base')};
                border-radius: 8px;
                border: 1px solid {get_token('border-subtle')};
            }}
            QLabel {{ background: transparent; }}
        """)

        outer = QHBoxLayout(container)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(16)

        def _section_frame(title):
            f = QWidget()
            f.setStyleSheet("background: transparent;")
            vl = QVBoxLayout(f)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(8)
            hdr = QLabel(title)
            hdr.setStyleSheet(
                f"font-size: 10px; font-weight: bold;"
                f" color: {get_token('primary')}; letter-spacing: 1px;"
            )
            vl.addWidget(hdr)
            g = QGridLayout()
            g.setSpacing(10)
            vl.addLayout(g)
            return f, g

        def _field(label, widget, required=True):
            w = QWidget()
            w.setStyleSheet("background: transparent;")
            vl = QVBoxLayout(w)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(4)
            lbl_text = (
                f'{label} <span style="color: {get_token("danger")};">*</span>'
                if required else label
            )
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet("font-size: 11px; color: gray; font-weight: bold;")
            vl.addWidget(lbl)
            vl.addWidget(widget)
            return w

        # ── Route ─────────────────────────────────────────────────────
        route_frame, rg = _section_frame("ROUTE")

        self.source_in = QLineEdit()
        self.source_in.setPlaceholderText("e.g. Mumbai Batching Plant")
        self.source_in.setMinimumHeight(34)
        self.source_in.textChanged.connect(self._update_summary)
        rg.addWidget(_field("FROM - TO", self.source_in, required=False), 0, 0)

        self.dist_in = QDoubleSpinBox()
        self.dist_in.setRange(0, 100_000)
        self.dist_in.setDecimals(2)
        self.dist_in.setMinimumHeight(34)
        self.dist_in.valueChanged.connect(self._update_summary)
        rg.addWidget(_field("ONE-WAY DISTANCE (km)", self.dist_in), 1, 0)

        outer.addWidget(route_frame, 2)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        outer.addWidget(sep)

        # ── Vehicle ───────────────────────────────────────────────────
        vehicle_frame, vg = _section_frame("VEHICLE")

        self.vehicle_name_in = QLineEdit()
        self.vehicle_name_in.setPlaceholderText("e.g. HDV Large")
        self.vehicle_name_in.setMinimumHeight(34)
        self.vehicle_name_in.textChanged.connect(self._update_summary)
        vg.addWidget(_field("VEHICLE TYPE", self.vehicle_name_in, required=False), 0, 0)

        self.capacity_in = QDoubleSpinBox()
        self.capacity_in.setRange(0, 1000)
        self.capacity_in.setDecimals(2)
        self.capacity_in.setMinimumHeight(34)
        self.capacity_in.valueChanged.connect(self._update_summary)
        vg.addWidget(_field("PAYLOAD CAPACITY (t)", self.capacity_in), 0, 1)

        self.gross_in = QDoubleSpinBox()
        self.gross_in.setRange(0, 2000)
        self.gross_in.setDecimals(2)
        self.gross_in.setMinimumHeight(34)
        self.gross_in.valueChanged.connect(self._update_summary)
        vg.addWidget(_field("GROSS WEIGHT - LOADED (t)", self.gross_in), 1, 0)

        self.ef_in = QDoubleSpinBox()
        self.ef_in.setRange(0, 10)
        self.ef_in.setDecimals(4)
        self.ef_in.setMinimumHeight(34)
        self.ef_in.valueChanged.connect(self._update_summary)
        vg.addWidget(_field("EMISSION FACTOR (kgCO₂e / t·km)", self.ef_in), 1, 1)

        ref_lbl = doc_label(
            f'Reference vehicle classes &amp; definitions &nbsp;'
            f'{doc_inline(["Carbon_emissions_data", "Transport_vehicle_reference"])}',
            word_wrap=False,
        )
        ref_lbl.setStyleSheet("font-size: 11px; color: gray; background: transparent;")
        vehicle_frame.layout().addWidget(ref_lbl)

        outer.addWidget(vehicle_frame, 3)

        layout.addWidget(container)

    # ── Main area: material picker ────────────────────────────────────

    def _build_main_area(self, layout):
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)

        mat_hdr = QHBoxLayout()
        mat_title = QLabel("Materials")
        mat_title.setStyleSheet(f"font-weight: {get_token('weight-bold')};")
        mat_hdr.addWidget(mat_title)
        mat_hdr.addStretch()
        self.pool_materials_chk = QCheckBox("Pool same materials")
        self.pool_materials_chk.setChecked(True)
        self.pool_materials_chk.setToolTip(
            "When checked, the same material used across multiple processes\n"
            "is combined into one shipment before calculating trips.\n"
            "Uncheck to treat each row independently."
        )
        self.pool_materials_chk.toggled.connect(self._on_pool_toggled)
        mat_hdr.addWidget(self.pool_materials_chk)
        self.hide_assigned_chk = QCheckBox("Hide assigned")
        self.hide_assigned_chk.toggled.connect(self._on_hide_assigned)
        mat_hdr.addWidget(self.hide_assigned_chk)
        ll.addLayout(mat_hdr)

        search_row = QHBoxLayout()
        search_row.setSpacing(6)
        self.search_in = QLineEdit()
        self.search_in.setPlaceholderText("🔍  Search materials...")
        self.search_in.setMinimumHeight(32)
        self.search_in.textChanged.connect(self._on_search)
        search_row.addWidget(self.search_in)

        self.select_all_btn = QPushButton("Select with Quantity")
        self.select_all_btn.setFixedHeight(32)
        self.select_all_btn.setMinimumWidth(110)
        self.select_all_btn.setCursor(Qt.PointingHandCursor)
        self.select_all_btn.setToolTip(
            "Selects all visible unassigned materials that have a non-zero quantity and a known kg/unit factor.\n"
            "Rows with no quantity or no kg conversion are skipped."
        )
        self.select_all_btn.clicked.connect(self._select_all_valid)
        search_row.addWidget(self.select_all_btn, alignment=Qt.AlignmentFlag.AlignTop)
        ll.addLayout(search_row)

        self.mat_table = _TransportTable()
        self.mat_table.setColumnCount(6)
        self.mat_table.setHorizontalHeaderLabels(
            ["", "Material", "Category", "Unit", "kg / unit", "Quantity (kg)"]
        )
        self.mat_table.verticalHeader().setVisible(False)
        self.mat_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.mat_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.mat_table.setAlternatingRowColors(True)
        self.mat_table.setShowGrid(False)
        self.mat_table.verticalHeader().setDefaultSectionSize(34)
        
        self.mat_table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)

        ll.addWidget(self.mat_table)

        # Safe header configuration for Windows
        h = self.mat_table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        h.setSectionResizeMode(0, QHeaderView.Fixed)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.Interactive)
        h.setSectionResizeMode(3, QHeaderView.Interactive)
        h.setSectionResizeMode(4, QHeaderView.Fixed)
        h.setSectionResizeMode(5, QHeaderView.Interactive)
        self.mat_table.setColumnWidth(0, 36)
        self.mat_table.setColumnWidth(4, 120)

        self.mat_count_lbl = QLabel("")
        self.mat_count_lbl.setStyleSheet("color: gray; font-size: 11px;")
        ll.addWidget(self.mat_count_lbl)
        layout.addWidget(left, 1)

    # ── Footer ────────────────────────────────────────────────────────

    def _build_footer(self, layout):
        layout.addWidget(_divider())
        row = QHBoxLayout()
        row.setSpacing(8)

        def _chip(header):
            chip = QFrame()
            chip.setObjectName("footer_chip")
            chip.setStyleSheet(f"""
                QFrame#footer_chip {{
                    border-radius: 6px;
                    border: 1px solid {get_token('border-subtle')};
                }}
                QLabel {{ background: transparent; }}
            """)
            cl = QVBoxLayout(chip)
            cl.setContentsMargins(12, 5, 12, 5)
            cl.setSpacing(1)
            hdr = QLabel(header)
            hdr.setStyleSheet("font-size: 9px; color: gray; font-weight: bold; letter-spacing: 1px;")
            val = QLabel("-")
            val.setStyleSheet("font-size: 14px; font-weight: bold;")
            cl.addWidget(hdr)
            cl.addWidget(val)
            return chip, val

        trips_chip, self._footer_trips = _chip("TRIPS")
        row.addWidget(trips_chip)

        em_chip, self._footer_emission = _chip("TOTAL EMISSION")
        self._footer_emission.setStyleSheet(
            f"font-size: 14px; font-weight: bold; color: {get_token('primary')};"
        )
        row.addWidget(em_chip)

        row.addStretch()

        cancel = QPushButton("Cancel")
        cancel.setMinimumHeight(36)
        cancel.setFixedWidth(100)
        cancel.clicked.connect(self.reject)

        self.save_btn = QPushButton("Save Delivery")
        self.save_btn.setMinimumHeight(36)
        self.save_btn.setFixedWidth(140)
        self.save_btn.clicked.connect(self._on_save)

        row.addWidget(cancel)
        row.addWidget(self.save_btn)
        layout.addLayout(row)

    # ── Summary updates ───────────────────────────────────────────────

    def _update_summary(self):
        cap = self.capacity_in.value()
        gross = self.gross_in.value()
        empty = max(0.0, gross - cap)
        dist = self.dist_in.value()
        ef = self.ef_in.value()
        vname = self.vehicle_name_in.text().strip()

        total_kg = 0.0
        selected_count = 0
        selected_rows = []

        cap_kg = cap * 1000.0

        for row in range(self.mat_table.rowCount()):
            chk_w = self.mat_table.cellWidget(row, 0)
            if not chk_w:
                continue
            chk = chk_w.findChild(QCheckBox)
            if not (chk and chk.isChecked()):
                continue
            meta = self._rows_metadata[row]
            qty_kg = self.mat_table.item(row, 5).data(Qt.UserRole) or 0.0
            total_kg += qty_kg
            selected_count += 1
            selected_rows.append(
                {"material_name": meta["material_name"], "qty_kg": qty_kg}
            )

        trips = self._compute_trips(selected_rows, cap_kg)
        loaded = gross * trips * dist * ef
        ret = empty * trips * dist * ef
        emission = loaded + ret

        self._footer_trips.setText(str(trips) if trips > 0 else "-")
        self._footer_emission.setText(
            f"{fmt_comma(emission)} kgCO₂e" if emission > 0 else "-"
        )


    def _compute_trips(self, selected_rows: list[dict], cap_kg: float) -> int:
        if cap_kg <= 0:
            return 0
        if self._pool_materials:
            grouped: dict[str, float] = {}
            for r in selected_rows:
                grouped[r["material_name"]] = grouped.get(r["material_name"], 0.0) + r["qty_kg"]
            buckets = grouped.values()
        else:
            buckets = (r["qty_kg"] for r in selected_rows)
        return sum(math.ceil(kg / cap_kg) for kg in buckets if kg > 0)

    # ── Material table ────────────────────────────────────────────────

    def _resolve_kg_factor(self, v: dict, mat_uuid: str, is_mass: bool, saved_kg: dict) -> tuple[float, bool]:
        if mat_uuid in saved_kg:
            return saved_kg[mat_uuid], False
        if is_mass and v.get("unit_to_si") is not None:
            return float(v["unit_to_si"]), False
        if v.get("transport_kg_factor"):
            return float(v["transport_kg_factor"]), False
        cu = (v.get("carbon_unit") or "").split("/", 1)
        if v.get("conversion_factor") and len(cu) == 2 and \
           cu[0].lower().replace("₂", "2") in ("kgco2e", "kgco2") and \
           cu[1].lower() == "kg":
            return float(v["conversion_factor"]), True
        return 0.0, False

    def _insert_material_row(self, row, mat_uuid, v, category, unit, qty, kg_factor, qty_kg, is_mass, is_assigned, kg_from_carbon, saved_kg):
        _grey = QColor(get_token("text_secondary"))
        _ro = Qt.ItemIsEnabled
        name_val = v.get("material_name", "")

        # Col 0 - checkbox
        if is_assigned:
            self.mat_table.setItem(row, 0, QTableWidgetItem())
        else:
            chk_w = QWidget()
            cl = QHBoxLayout(chk_w)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setAlignment(Qt.AlignCenter)
            chk = QCheckBox()
            can_select = kg_factor > 0
            chk.setEnabled(can_select)
            chk.setChecked(can_select and mat_uuid in saved_kg)
            chk.stateChanged.connect(self._update_summary)
            chk.stateChanged.connect(lambda _: self._refresh_select_all_label())
            cl.addWidget(chk)
            self.mat_table.setItem(row, 0, QTableWidgetItem())
            self.mat_table.setCellWidget(row, 0, chk_w)

        # Col 1 - material name
        ni = QTableWidgetItem(name_val)
        if is_assigned:
            ni.setForeground(_grey)
            ni.setFlags(_ro)
        else:
            f = ni.font()
            f.setBold(True)
            ni.setFont(f)
        self.mat_table.setItem(row, 1, ni)

        # Col 2 - category
        ci = QTableWidgetItem(category)
        if is_assigned: ci.setForeground(_grey); ci.setFlags(_ro)
        self.mat_table.setItem(row, 2, ci)

        # Col 3 - unit
        ui = QTableWidgetItem(UNIT_DISPLAY.get(unit.lower(), unit) if unit else "-")
        ui.setTextAlignment(Qt.AlignCenter)
        ui.setFlags(_ro)
        if is_assigned: ui.setForeground(_grey)
        self.mat_table.setItem(row, 3, ui)

        # Col 4 - kg / unit
        if is_assigned:
            ai = QTableWidgetItem("-")
            ai.setTextAlignment(Qt.AlignCenter)
            ai.setForeground(_grey)
            ai.setFlags(_ro)
            self.mat_table.setItem(row, 4, ai)
        elif is_mass:
            fi = QTableWidgetItem(fmt(kg_factor) if kg_factor > 0 else "")
            fi.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            fi.setData(Qt.UserRole, kg_factor)
            fi.setFlags(_ro)
            self.mat_table.setItem(row, 4, fi)
        else:
            prefill = saved_kg.get(mat_uuid, kg_factor)
            edit = TableLineEdit("" if prefill <= 0 else fmt(prefill))
            edit.setPlaceholderText("kg per unit")
            edit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            edit.setValidator(QDoubleValidator(0, 1e9, 4))
            edit.textChanged.connect(lambda t, r=row, q=qty: self._on_factor_changed(t, r, q))
            sort_item = QTableWidgetItem()
            sort_item.setData(Qt.UserRole, prefill)
            self.mat_table.setItem(row, 4, sort_item)
            self.mat_table.setCellWidget(row, 4, edit)

        # Col 5 - qty in kg
        qi = QTableWidgetItem(f"{qty_kg:,.0f}" if qty_kg > 0 else "-")
        qi.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        qi.setData(Qt.UserRole, qty_kg)
        qi.setFlags(_ro)
        if is_assigned: qi.setForeground(_grey)
        self.mat_table.setItem(row, 5, qi)

        if qty == 0 and not is_assigned:
            for col in (1, 2, 3, 5):
                it = self.mat_table.item(row, col)
                if it:
                    it.setForeground(_grey)
                    f = it.font(); f.setItalic(True); it.setFont(f)

        return name_val

    def _populate_materials(self):
        self.mat_table.setRowCount(0)
        self._rows_metadata = []
        saved_kg = {m["uuid"]: m["kg_factor"] for m in self.existing_data.get("materials", [])} if self.is_edit else {}

        for chunk_id, category in STRUCTURE_CHUNKS:
            chunk_data = self.controller.engine.fetch_chunk(chunk_id) or {}
            for _comp, items in chunk_data.items():
                for item in items:
                    if item.get("state", {}).get("in_trash", False): continue
                    mat_uuid = item.get("id", "")
                    v = item.get("values", {})
                    unit = v.get("unit", "")
                    qty = float(v.get("quantity", 0) or 0)
                    is_mass = UNIT_DIMENSION.get(unit.lower()) == "Mass"
                    is_assigned = mat_uuid in self.assigned_uuids
                    kg_factor, kg_from_carbon = self._resolve_kg_factor(v, mat_uuid, is_mass, saved_kg)
                    qty_kg = qty * kg_factor
                    row = self.mat_table.rowCount()
                    self.mat_table.insertRow(row)
                    name_val = self._insert_material_row(row, mat_uuid, v, category, unit, qty, kg_factor, qty_kg, is_mass, is_assigned, kg_from_carbon, saved_kg)
                    self._rows_metadata.append({"uuid": mat_uuid, "material_name": name_val, "category": category, "unit": unit, "qty": qty, "kg_factor": kg_factor, "qty_kg": qty_kg, "is_assigned": is_assigned})

        self.mat_table.setSortingEnabled(False)
        self._refresh_mat_count()

    def _on_factor_changed(self, text, row, qty):
        try: val = float(text or 0)
        except ValueError: return
        qty_kg = qty * val
        self._rows_metadata[row]["kg_factor"] = val
        self._rows_metadata[row]["qty_kg"] = qty_kg
        item = self.mat_table.item(row, 5)
        if item: item.setText(f"{qty_kg:,.0f}" if qty_kg > 0 else "-"); item.setData(Qt.UserRole, qty_kg)
        sort = self.mat_table.item(row, 4)
        if sort: sort.setData(Qt.UserRole, val)
        chk_w = self.mat_table.cellWidget(row, 0)
        if chk_w:
            chk = chk_w.findChild(QCheckBox)
            if chk:
                has_factor = val > 0
                chk.setEnabled(has_factor)
                if not has_factor: chk.setChecked(False)
        self._update_summary()

    def _on_search(self, text):
        text = text.lower().strip()
        for row in range(self.mat_table.rowCount()):
            meta = self._rows_metadata[row]
            match = text in meta["material_name"].lower() or text in meta["category"].lower()
            hidden = not match
            if not hidden and self._hide_assigned and meta["is_assigned"]: hidden = True
            self.mat_table.setRowHidden(row, hidden)
        self._refresh_mat_count()

    def _on_hide_assigned(self, checked):
        self._hide_assigned = checked
        self._on_search(self.search_in.text())

    def _select_all_valid(self):
        checkboxes = []
        for row in range(self.mat_table.rowCount()):
            if self.mat_table.isRowHidden(row): continue
            chk_w = self.mat_table.cellWidget(row, 0)
            if chk_w:
                chk = chk_w.findChild(QCheckBox)
                if chk and chk.isEnabled(): checkboxes.append(chk)
        if not checkboxes: return
        target = not all(c.isChecked() for c in checkboxes)
        for chk in checkboxes: chk.blockSignals(True); chk.setChecked(target); chk.blockSignals(False)
        self._update_summary()
        self.select_all_btn.setText("Deselect All" if target else "Select with Quantity")

    def _refresh_mat_count(self):
        visible = sum(1 for r in range(self.mat_table.rowCount()) if not self.mat_table.isRowHidden(r))
        self.mat_count_lbl.setText(f"Showing {visible} of {self.mat_table.rowCount()} materials")
        self._refresh_select_all_label()

    def _refresh_select_all_label(self):
        enabled_checkboxes = [chk for row in range(self.mat_table.rowCount()) if not self.mat_table.isRowHidden(row) for chk_w in [self.mat_table.cellWidget(row, 0)] if chk_w for chk in [chk_w.findChild(QCheckBox)] if chk and chk.isEnabled()]
        if not enabled_checkboxes: return
        all_checked = all(c.isChecked() for c in enabled_checkboxes)
        self.select_all_btn.setText("Deselect All" if all_checked else "Select with Quantity")

    def _on_pool_toggled(self, checked):
        self._pool_materials = checked
        self._update_summary()

    # ── Validation & save ─────────────────────────────────────────────

    def _highlight_error(self, widget):
        widget.setStyleSheet(f"border: 1.5px solid {get_token('danger')};")
        widget.setFocus()
        if isinstance(widget, QDoubleSpinBox):
            widget.valueChanged.connect(
                lambda: self._clear_highlight(widget),
                Qt.ConnectionType.SingleShotConnection,
            )
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(
                lambda: self._clear_highlight(widget),
                Qt.ConnectionType.SingleShotConnection,
            )

    def _clear_highlight(self, widget):
        widget.setStyleSheet("")

    def _on_save(self):
        dist = self.dist_in.value()
        cap = self.capacity_in.value()
        gross = self.gross_in.value()
        ef = self.ef_in.value()

        if dist <= 0:
            QMessageBox.critical(self, "Error", "One-way distance must be greater than 0 km.")
            self._highlight_error(self.dist_in)
            return
        if cap <= 0:
            QMessageBox.critical(self, "Error", "Payload capacity must be greater than 0 t.")
            self._highlight_error(self.capacity_in)
            return
        if ef <= 0:
            QMessageBox.critical(self, "Error", "Emission factor must be greater than 0 kgCO₂e / t·km.")
            self._highlight_error(self.ef_in)
            return
        if gross <= 0:
            QMessageBox.critical(self, "Error", "Gross weight (loaded) must be greater than 0 t.")
            self._highlight_error(self.gross_in)
            return
        if gross < cap:
            QMessageBox.critical(self, "Error", "Gross weight (loaded) must be ≥ payload capacity.")
            self._highlight_error(self.gross_in)
            return
        selected = self._get_selected()
        if not selected:
            QMessageBox.critical(self, "Error", "Select at least one material.")
            return
        total_cargo_kg = sum(m["kg_factor"] * m["qty"] for m in selected)
        if total_cargo_kg <= 0:
            QMessageBox.critical(
                self, "Error",
                "All selected materials have zero quantity.\n"
                "At least one material must have a non-zero quantity to calculate trips and emissions."
            )
            return
        self.accept()

    def _get_selected(self) -> list:
        result = []
        for row in range(self.mat_table.rowCount()):
            chk_w = self.mat_table.cellWidget(row, 0)
            if not chk_w: continue
            chk = chk_w.findChild(QCheckBox)
            if not (chk and chk.isChecked()): continue
            meta = self._rows_metadata[row]
            edit = self.mat_table.cellWidget(row, 4)
            kg_factor = float(edit.text() or 0) if isinstance(edit, QLineEdit) else (self.mat_table.item(row, 4).data(Qt.UserRole) or 0.0)
            result.append({"uuid": meta["uuid"], "kg_factor": kg_factor, "qty": meta["qty"], "material_name": meta["material_name"]})
        return result

    # ── Load existing entry ───────────────────────────────────────────

    def _load_existing(self):
        d = self.existing_data
        v = d.get("vehicle", {})
        r = d.get("route", {})

        self.source_in.setText(r.get("origin", ""))
        self.dist_in.blockSignals(True)
        self.dist_in.setValue(r.get("distance_km", 0))
        self.dist_in.blockSignals(False)

        self.vehicle_name_in.setText(v.get("vehicle_class", v.get("name", "")))

        for w in (self.capacity_in, self.gross_in, self.ef_in):
            w.blockSignals(True)
        self.capacity_in.setValue(v.get("capacity", 20.0))
        self.gross_in.setValue(v.get("gross_weight", 32.0))
        self.ef_in.setValue(v.get("emission_factor", 0.5))
        for w in (self.capacity_in, self.gross_in, self.ef_in):
            w.blockSignals(False)

        self._update_summary()

    def get_vehicle_entry(self) -> dict:
        materials = self._get_selected()
        cap = self.capacity_in.value()
        gross = self.gross_in.value()
        empty = max(0.0, gross - cap)
        dist = self.dist_in.value()
        ef = self.ef_in.value()
        vname = self.vehicle_name_in.text().strip()

        cap_kg = cap * 1000.0
        total_kg = sum(m["kg_factor"] * m["qty"] for m in materials)
        total_t = total_kg / 1000.0

        selected_rows = [{"material_name": m["material_name"], "qty_kg": m["kg_factor"] * m["qty"]} for m in materials]
        trips = self._compute_trips(selected_rows, cap_kg)
        loaded = gross * trips * dist * ef
        ret = empty * trips * dist * ef
        emission = loaded + ret

        return {
            "id": self.existing_data.get("id", str(uuid.uuid4())),
            "vehicle": {
                "name": vname,
                "capacity": cap,
                "gross_weight": gross,
                "empty_weight": empty,
                "emission_factor": ef,
                "vehicle_class": vname,
                "is_custom": True,
            },
            "route": {
                "origin": self.source_in.text().strip(),
                "destination": "Site",
                "distance_km": dist,
            },
            "materials": [{"uuid": m["uuid"], "kg_factor": m["kg_factor"]} for m in materials],
            "summary": {
                "total_cargo_kg": total_kg,
                "total_cargo_t": total_t,
                "trips": trips,
                "distance_km": dist,
                "emission_factor": ef,
                "total_emissions_kgco2e": emission,
            },
            "meta": {
                "created_at": self.existing_data.get("meta", {}).get("created_at", datetime.datetime.now().isoformat()),
                "updated_at": datetime.datetime.now().isoformat(),
            },
            "state": self.existing_data.get("state", {}),
        }

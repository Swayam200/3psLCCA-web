import math
import datetime
import time
from three_ps_lcca_gui.gui.themes import get_token

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QFrame,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QScrollArea,
    QSizePolicy,
    QMessageBox,
)
from PySide6.QtCore import Qt, QSize, QTimer

from .transport_dialog import TransportDialog
from PySide6.QtGui import QColor
from ...utils.definitions import STRUCTURE_CHUNKS, UNIT_DIMENSION
from ...utils.table_widgets import TooltipTableMixin, WordWrapHeaderView
from ...utils.display_format import fmt, fmt_comma
from ...utils.icons import make_icon, make_icon_btn
from ...utils.validation_helpers import freeze_widgets


class _TransportEmissionsTable(TooltipTableMixin, QTableWidget):
    """Transport table with a WordWrapHeaderView installed at construction time.

    Installing it here (instead of relying on the global _TableHeaderWordWrapFilter)
    means the header is always visible: the filter skips tables that already use
    WordWrapHeaderView, so no deferred swap occurs and no hidden-header race exists.
    """

    # Material, Category, kg Factor, Quantity (kg), Trips, Emission, Warnings
    _COL_RATIOS = [0.20, 0.12, 0.09, 0.11, 0.07, 0.16, 0.25]
    _COL_MINS   = [80,   60,   55,   70,   45,   100,  80]

    def __init__(self, parent=None):
        super().__init__(parent)
        hdr = WordWrapHeaderView(Qt.Horizontal, parent=self)
        self.setHorizontalHeader(hdr)
        hdr.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.viewport().width()
        for col, (ratio, min_w) in enumerate(zip(self._COL_RATIOS, self._COL_MINS)):
            self.setColumnWidth(col, max(min_w, int(w * ratio)))

    def _content_height(self) -> int:
        hh = self.horizontalHeader()
        h = (hh.height() or hh.sizeHint().height()) + 2 * self.frameWidth()
        for r in range(self.rowCount()):
            h += self.rowHeight(r)
        return h

    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), self._content_height())

    def minimumSizeHint(self) -> QSize:
        return QSize(super().minimumSizeHint().width(), self._content_height())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setFrameShadow(QFrame.Sunken)
    return f


def _vline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.VLine)
    f.setFrameShadow(QFrame.Sunken)
    return f


def _section_label(text: str) -> QLabel:
    lbl = QLabel(f"<b>{text}</b>")
    lbl.setStyleSheet("font-size: 13px;")
    return lbl


# ---------------------------------------------------------------------------
# Material lookup - scan all structure chunks by UUID
# ---------------------------------------------------------------------------


def _build_material_index(engine) -> dict:
    """
    Returns dict: {uuid: (item, category, chunk_id, comp_name)}
    Scans all structure chunks once per refresh.
    """
    index = {}
    for chunk_id, category in STRUCTURE_CHUNKS:
        data = engine.fetch_chunk(chunk_id) or {}
        for comp_name, items in data.items():
            for item in items:
                mat_id = item.get("id")
                if mat_id:
                    index[mat_id] = (item, category, chunk_id, comp_name)
    return index


# ---------------------------------------------------------------------------
# Emission calculation
# ---------------------------------------------------------------------------


def calc_vehicle_emission(entry: dict, mat_index: dict) -> tuple:
    """
    Returns (total_emission, material_results, warnings)

    material_results: list of dicts with per-material breakdown
    warnings:         list of warning strings
    """
    v = entry.get("vehicle", {})
    r = entry.get("route", {})
    uuids = entry.get("materials", [])

    cap = float(v.get("capacity", 0) or 0)
    gross_wt = float(v.get("gross_weight", 0) or 0)
    empty_wt = float(v.get("empty_weight", max(0.0, gross_wt - cap)) or 0)
    dist = float(r.get("distance_km", 0) or 0)
    ef = float(v.get("emission_factor", 0) or 0)

    total_emission = 0.0
    material_results = []
    warnings = []

    if cap <= 0:
        warnings.append("Payload capacity is zero - check vehicle data.")
        return 0.0, [], warnings

    if dist <= 0:
        warnings.append("Distance is zero - no emission calculated.")

    if ef <= 0:
        warnings.append("Emission factor is zero - no emission calculated.")

    for mat_entry in uuids:
        # materials is now [{uuid, kg_factor}]
        mat_uuid = mat_entry.get("uuid") if isinstance(mat_entry, dict) else mat_entry
        kg_factor = (
            mat_entry.get("kg_factor", 1.0) if isinstance(mat_entry, dict) else 1.0
        )

        if mat_uuid not in mat_index:
            material_results.append(
                {
                    "uuid": mat_uuid,
                    "name": "Unknown",
                    "status": "removed",
                    "emission": 0.0,
                    "warning": "⚠ Material removed from structure",
                }
            )
            warnings.append(f"Material {mat_uuid[:8]}... was removed from structure.")
            continue

        item, category, chunk_id, comp_name = mat_index[mat_uuid]

        if item.get("state", {}).get("in_trash", False):
            material_results.append(
                {
                    "uuid": mat_uuid,
                    "name": item.get("values", {}).get("material_name", ""),
                    "category": category,
                    "status": "trashed",
                    "emission": 0.0,
                }
            )
            continue

        val = item.get("values", {})
        qty = float(val.get("quantity") or 0)
        unit = val.get("unit", "")
        name = val.get("material_name", "")

        # Use kg_factor from transport entry (not structure conv factor)
        qty_kg = qty * kg_factor
        qty_t = qty_kg / 1000.0
        trips = math.ceil(qty_t / cap) if cap > 0 else 0

        # Loaded trip: gross_weight × dist × trips × EF
        # Empty return: empty_weight × dist × trips × EF
        emission = (gross_wt + empty_wt) * trips * dist * ef

        warns = []
        if qty <= 0:
            warns.append("⚠ Zero quantity")
        if qty_kg <= 0 and qty > 0:
            warns.append("⚠ Zero kg - check factor")
        if trips > 1000:
            warns.append(f"⚠ {trips} trips - unusually high")
        is_mass = UNIT_DIMENSION.get(unit.lower()) == "Mass"
        if not is_mass and abs(kg_factor - 1.0) < 1e-6:
            warns.append(f"⚠ 1:1 factor for {unit} - verify conversion")

        warn = " | ".join(warns)
        if trips > 1000:
            warnings.append(f"'{name}': {trips} trips - unusually high, check data.")

        material_results.append(
            {
                "uuid": mat_uuid,
                "name": name,
                "category": category,
                "unit": unit,
                "qty": qty,
                "kg_factor": kg_factor,
                "qty_kg": qty_kg,
                "trips": trips,
                "emission": emission,
                "status": "ok",
                "warning": warn,  # ← this
            }
        )

        total_emission += emission

    return total_emission, material_results, warnings


# ---------------------------------------------------------------------------
# Vehicle Card Widget
# ---------------------------------------------------------------------------


class VehicleCard(QGroupBox):
    """
    Displays one vehicle entry with:
    - Header: name, route, total emission
    - Material breakdown table
    - Warnings
    - Edit / Trash buttons
    """

    def __init__(
        self,
        entry: dict,
        mat_results: list,
        warnings: list,
        total_emission: float,
        on_edit,
        on_trash,
        frozen: bool = False,
        parent=None,
    ):
        v = entry.get("vehicle", {})
        r = entry.get("route", {})
        from_loc   = r.get("origin", "").strip()
        route_part = f"{from_loc}  |  " if from_loc else ""
        title = (
            f"{v.get('name', 'Delivery')}  -  "
            f"{route_part}"
            f"{fmt(r.get('distance_km', 0))} km  |  "
            f"{fmt_comma(total_emission)} kgCO₂e"
        )
        super().__init__(title, parent)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Vehicle specs row
        specs_row = QHBoxLayout()
        gross = v.get('gross_weight', 0)
        cap = v.get('capacity', 0)
        empty = v.get('empty_weight', max(0.0, gross - cap))
        specs = [
            f"Capacity: {fmt(cap)}t",
            f"Gross Wt (loaded): {fmt(gross)}t",
            f"Empty Wt: {fmt(empty)}t",
            f"EF: {fmt(v.get('emission_factor', 0))} kgCO₂e/t-km",
        ]
        for spec in specs:
            lbl = QLabel(spec)
            lbl.setStyleSheet("font-size: 11px;")
            specs_row.addWidget(lbl)
            specs_row.addWidget(_vline())
        specs_row.addStretch()
        layout.addLayout(specs_row)

        # Warnings
        for warn in warnings:
            warn_lbl = QLabel(f"! {warn}")
            warn_lbl.setWordWrap(True)
            warn_lbl.setStyleSheet("font-size: 11px;")
            layout.addWidget(warn_lbl)

        # Materials table
        if mat_results:
            table = self._build_table(mat_results)
            layout.addWidget(table)

        # Buttons
        btn_row = QHBoxLayout()
        edit_btn = make_icon_btn("edit", "Edit Delivery", size=32, hover_color="241, 196, 15")
        trash_btn = make_icon_btn("trash", "Remove", size=32, icon_color=get_token("danger"), hover_color="192, 57, 43")
        edit_btn.clicked.connect(on_edit)
        trash_btn.clicked.connect(on_trash)
        freeze_widgets(frozen, edit_btn, trash_btn)
        btn_row.addStretch()
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(trash_btn)
        layout.addLayout(btn_row)

    def _build_table(self, mat_results: list) -> QTableWidget:
        table = _TransportEmissionsTable()
        table.setColumnCount(7)
        _L = Qt.AlignLeft  | Qt.AlignVCenter
        _R = Qt.AlignRight | Qt.AlignVCenter
        for col, (label, align) in enumerate([
            ("Material",          _L),
            ("Category",          _L),
            ("kg Factor",         _R),
            ("Quantity (kg)",      _R),
            ("Trips",             _R),
            ("Emission (kgCO₂e)", _R),
            ("Warnings",          _L),
        ]):
            item = QTableWidgetItem(label)
            item.setTextAlignment(align)
            table.setHorizontalHeaderItem(col, item)
        h = table.horizontalHeader()
        h.setStretchLastSection(False)
        h.setSectionResizeMode(QHeaderView.Interactive)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(32)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        for mat in mat_results:
            row = table.rowCount()
            table.insertRow(row)
            status = mat.get("status", "ok")

            if status == "ok":
                table.setItem(row, 0, self._item(mat.get("name", "")))
                table.setItem(row, 1, self._item(mat.get("category", "")))
                table.setItem(row, 2, self._item(fmt(mat.get("kg_factor", 1)), Qt.AlignRight | Qt.AlignVCenter))
                table.setItem(
                    row,
                    3,
                    self._item(
                        f"{mat.get('qty_kg', 0):,.0f}", Qt.AlignRight | Qt.AlignVCenter
                    ),
                )
                table.setItem(
                    row,
                    4,
                    self._item(
                        str(mat.get("trips", 0)), Qt.AlignRight | Qt.AlignVCenter
                    ),
                )
                table.setItem(
                    row,
                    5,
                    self._item(
                        fmt_comma(mat.get('emission', 0)),
                        Qt.AlignRight | Qt.AlignVCenter,
                    ),
                )

                warn = mat.get("warning", "")
                warn_item = self._item(warn if warn else "", Qt.AlignCenter)
                if warn:
                    # Truncate display text, full detail in tooltip
                    parts = warn.split(" | ")
                    display = parts[0] + (" ..." if len(parts) > 1 else "")
                    warn_item = self._item(display, Qt.AlignCenter)
                    # warn_item.setForeground(QColor("#874d00"))
                    # warn_item.setBackground(QColor("#fffbe6"))
                    # Bullet list in tooltip
                    tooltip = "\n".join(f"• {p}" for p in parts)
                    warn_item.setToolTip(tooltip)
                table.setItem(row, 6, warn_item)

            else:
                table.setItem(row, 0, self._item(mat.get("name", "")))
                table.setItem(row, 1, self._item(mat.get("category", "")))
                for c in range(2, 6):
                    table.setItem(row, c, self._item("-", Qt.AlignCenter))
                label = "In Trash" if status == "trashed" else "Removed"
                warn_item = self._item(f"✕ {label}", Qt.AlignCenter)
                warn_item.setForeground(QColor(get_token("")))
                warn_item.setBackground(QColor(get_token("warning")))
                table.setItem(row, 6, warn_item)
        return table

    def _item(self, text="", align=None) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        it.setFlags(Qt.ItemIsEnabled)
        if align:
            it.setTextAlignment(align)
        return it


# ---------------------------------------------------------------------------
# TransportEmissions - main widget
# ---------------------------------------------------------------------------


class TransportEmissions(QWidget):
    def __init__(self, controller=None):
        super().__init__()
        self.controller = controller
        self.setObjectName("TransportEmissions")

        self._frozen = False
        self._loaded = False
        if controller and hasattr(controller, "project_loaded"):
            controller.project_loaded.connect(self._on_project_reloaded)
        if controller and hasattr(controller, "chunk_updated"):
            _WATCHED = {"str_foundation", "str_sub_structure", "str_super_structure", "str_misc", "transport_data"}
            controller.chunk_updated.connect(
                lambda name: QTimer.singleShot(0, self.on_refresh) if name in _WATCHED else None
            )

        outer = QVBoxLayout(self)
        outer.setSpacing(8)

        # ── Summary Bar ──────────────────────────────────────────────────
        summary_bar = QWidget()
        summary_layout = QHBoxLayout(summary_bar)
        summary_layout.setContentsMargins(8, 8, 8, 8)

        self.total_lbl = QLabel("Total Transport Emissions: - kgCO₂e")
        self.vehicle_lbl = QLabel("Vehicles: -")
        self.add_btn = QPushButton("+ Add Delivery")
        self.add_btn.setMinimumHeight(32)
        self.add_btn.clicked.connect(self._open_add_dialog)

        summary_layout.addWidget(self.total_lbl)
        summary_layout.addWidget(_vline())
        summary_layout.addWidget(self.vehicle_lbl)
        summary_layout.addStretch()
        summary_layout.addWidget(self.add_btn)
        outer.addWidget(summary_bar)

        # ── Details breakdown ─────────────────────────────────────────────
        self.details_widget = QWidget()
        details_layout = QHBoxLayout(self.details_widget)
        details_layout.setContentsMargins(8, 0, 8, 8)

        self.foundation_lbl = QLabel("Foundation: -")
        self.sub_lbl = QLabel("Sub-Structure: -")
        self.super_lbl = QLabel("Super-Structure: -")
        self.misc_lbl = QLabel("Misc: -")

        for lbl in [self.foundation_lbl, self.sub_lbl, self.super_lbl, self.misc_lbl]:
            details_layout.addWidget(lbl)
            details_layout.addWidget(_vline())

        details_layout.addStretch()
        outer.addWidget(self.details_widget)

        outer.addWidget(_hline())

        # ── Scroll area for vehicle cards ─────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setSpacing(8)
        scroll.setWidget(self.container)
        outer.addWidget(scroll)

    # ── Refresh ──────────────────────────────────────────────────────────

    def on_refresh(self):
        if not self.controller or not getattr(self.controller, "engine", None):
            return

        # Clear cards
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)

        data = self.controller.engine.fetch_chunk("transport_data") or {}
        vehicles = data.get("vehicles", [])

        mat_index = _build_material_index(self.controller.engine)

        # Auto-clean stale material references (trashed or permanently deleted)
        dirty = False
        for entry in vehicles:
            if entry.get("state", {}).get("in_trash", False):
                continue
            clean = []
            for m in entry.get("materials", []):
                uuid = m.get("uuid") if isinstance(m, dict) else m
                item_data = mat_index.get(uuid)
                if item_data and not item_data[0].get("state", {}).get("in_trash", False):
                    clean.append(m)
                else:
                    dirty = True
            entry["materials"] = clean
        if dirty:
            self.controller.engine.stage_update(chunk_name="transport_data", data=data)

        total_emission = 0.0
        cat_totals = {label: 0.0 for _, label in STRUCTURE_CHUNKS}
        active_count = 0

        for entry in vehicles:
            if entry.get("state", {}).get("in_trash", False):
                continue

            active_count += 1
            emission, mat_results, warnings = calc_vehicle_emission(entry, mat_index)
            total_emission += emission

            # Category breakdown
            for mat in mat_results:
                if mat.get("status") == "ok":
                    cat = mat.get("category", "")
                    if cat in cat_totals:
                        cat_totals[cat] += mat.get("emission", 0)

            entry_id = entry.get("id")
            card = VehicleCard(
                entry=entry,
                mat_results=mat_results,
                warnings=warnings,
                total_emission=emission,
                on_edit=lambda _, eid=entry_id: self._open_edit_dialog(eid),
                on_trash=lambda _, eid=entry_id: self._trash_vehicle(eid),
                frozen=self._frozen,
            )
            self.container_layout.addWidget(card)

        self.container_layout.addStretch()

        # Update summary
        self.total_lbl.setText(
            f"Total Transport Emissions: {fmt_comma(total_emission)} kgCO₂e"
        )
        self.vehicle_lbl.setText(f"Vehicles: {active_count}")
        self.foundation_lbl.setText(
            f"Foundation: {fmt_comma(cat_totals.get('Foundation', 0))}"
        )
        self.sub_lbl.setText(
            f"Sub-Structure: {fmt_comma(cat_totals.get('Sub-Structure', 0))}"
        )
        self.super_lbl.setText(
            f"Super-Structure: {fmt_comma(cat_totals.get('Super-Structure', 0))}"
        )
        self.misc_lbl.setText(f"Misc: {fmt_comma(cat_totals.get('Misc', 0))}")

    # ── Actions ──────────────────────────────────────────────────────────

    def _get_assigned_uuids(self, exclude_entry_id: str = None) -> set:
        data = self.controller.engine.fetch_chunk("transport_data") or {}
        vehicles = data.get("vehicles", [])
        assigned = set()
        for entry in vehicles:
            if entry.get("state", {}).get("in_trash", False):
                continue
            if entry.get("id") == exclude_entry_id:
                continue
            for m in entry.get("materials", []):
                if isinstance(m, dict):
                    assigned.add(m.get("uuid"))
                else:
                    assigned.add(m)  # fallback for plain uuid strings
        return assigned

    def _write_back_kg_factors(self, entry: dict):
        """
        Persist kg_factor for non-mass materials back into each material's
        values dict (transport_kg_factor key) so the next delivery dialog
        pre-fills the factor automatically.
        """
        for m in entry.get("materials", []):
            if not isinstance(m, dict):
                continue
            uid = m.get("uuid")
            kf  = m.get("kg_factor", 0.0)
            if not uid or not kf:
                continue
            for chunk_id, _ in STRUCTURE_CHUNKS:
                chunk_data = self.controller.engine.fetch_chunk(chunk_id) or {}
                changed = False
                for comp_items in chunk_data.values():
                    for item in comp_items:
                        if item.get("id") == uid:
                            item.setdefault("values", {})["transport_kg_factor"] = kf
                            changed = True
                if changed:
                    self.controller.engine.stage_update(chunk_name=chunk_id, data=chunk_data)
                    break

    def _open_add_dialog(self):
        assigned = self._get_assigned_uuids()
        dialog = TransportDialog(self.controller, assigned, parent=self)
        if dialog.exec():
            entry = dialog.get_vehicle_entry()
            self._write_back_kg_factors(entry)
            data = self.controller.engine.fetch_chunk("transport_data") or {}
            data.setdefault("vehicles", []).append(entry)
            self.controller.engine.stage_update(chunk_name="transport_data", data=data)
            self._mark_dirty()
            QTimer.singleShot(0, self.on_refresh)

    def _open_edit_dialog(self, entry_id: str):
        data = self.controller.engine.fetch_chunk("transport_data") or {}
        vehicles = data.get("vehicles", [])
        entry = next((v for v in vehicles if v.get("id") == entry_id), None)
        if not entry:
            return

        assigned = self._get_assigned_uuids(exclude_entry_id=entry_id)
        dialog = TransportDialog(self.controller, assigned, data=entry, parent=self)
        if dialog.exec():
            updated = dialog.get_vehicle_entry()
            self._write_back_kg_factors(updated)
            vehicles = [updated if v.get("id") == entry_id else v for v in vehicles]
            data["vehicles"] = vehicles
            self.controller.engine.stage_update(chunk_name="transport_data", data=data)
            self._mark_dirty()
            QTimer.singleShot(0, self.on_refresh)

    def _trash_vehicle(self, entry_id: str):
        confirm = QMessageBox.question(
            self,
            "Remove Delivery",
            "Remove this delivery entry? Materials will be available for reassignment.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        data = self.controller.engine.fetch_chunk("transport_data") or {}
        vehicles = data.get("vehicles", [])
        for v in vehicles:
            if v.get("id") == entry_id:
                v.setdefault("state", {})["in_trash"] = True
                v.setdefault("meta", {})["updated_at"] = datetime.datetime.now().isoformat()
                break

        data["vehicles"] = vehicles
        self.controller.engine.stage_update(chunk_name="transport_data", data=data)
        self._mark_dirty()
        QTimer.singleShot(0, self.on_refresh)

    def _mark_dirty(self):
        if self.controller and self.controller.engine:
            eng = self.controller.engine
            eng._last_keystroke_time = time.time()
            eng._has_unsaved_changes = True
            try:
                eng.on_dirty(True)
            except Exception as e:
                print(f"[TransportEmissions] _mark_dirty: {e}")

    def _compute(self) -> dict:
        """
        Core calculation logic shared by on_refresh(), validate(), and get_data().
        Returns raw computed data without touching any UI.
        """
        cat_totals = {label: 0.0 for _, label in STRUCTURE_CHUNKS}
        entries = []
        all_warnings = []
        total_emission = 0.0
        active_count = 0

        if not self.controller or not getattr(self.controller, "engine", None):
            return {
                "total_emission": 0.0,
                "cat_totals": cat_totals,
                "active_count": 0,
                "entries": [],
                "all_warnings": [],
            }

        data = self.controller.engine.fetch_chunk("transport_data") or {}
        vehicles = data.get("vehicles", [])
        mat_index = _build_material_index(self.controller.engine)

        for entry in vehicles:
            if entry.get("state", {}).get("in_trash", False):
                continue
            active_count += 1
            emission, mat_results, warnings = calc_vehicle_emission(entry, mat_index)
            total_emission += emission
            for mat in mat_results:
                if mat.get("status") == "ok":
                    cat = mat.get("category", "")
                    if cat in cat_totals:
                        cat_totals[cat] += mat.get("emission", 0)
            all_warnings.extend(warnings)
            entries.append({
                "entry": entry,
                "emission": emission,
                "mat_results": mat_results,
                "warnings": warnings,
            })

        return {
            "total_emission": total_emission,
            "cat_totals": cat_totals,
            "active_count": active_count,
            "entries": entries,
            "all_warnings": all_warnings,
        }

    def validate(self) -> dict:
        result = self._compute()
        warnings = []

        if result["active_count"] == 0:
            warnings.append(
                "No active vehicle entries found - add at least one vehicle and its transport details in the Transportation/Equipment Emissions tab to calculate transport carbon emissions"
            )
        elif result["total_emission"] == 0.0:
            warnings.append(
                "Total transport carbon emission is 0 kgCO₂e - "
                "one or more required inputs (distance, payload, or emission factor) may be zero; review each vehicle entry to ensure all values are complete"
            )

        if result["all_warnings"]:
            for w in result["all_warnings"]:
                warnings.append(w)

        return {"errors": [], "warnings": warnings}

    def get_data(self) -> dict:
        result = self._compute()
        entries_out = [
            {
                "vehicle_name": e["entry"].get("vehicle", {}).get("name", ""),
                "from-to": e["entry"].get("route", {}).get("origin", ""),
                "distance_km": e["entry"].get("route", {}).get("distance_km", 0),
                "emission_kgCO2e": e["emission"],
                "materials": e["mat_results"],
            }
            for e in result["entries"]
        ]
        return {
            "chunk": "transport_emissions_data",
            "data": {
                "entries": entries_out,
                "cat_totals": result["cat_totals"],
                "total_kgCO2e": result["total_emission"],
                "active_vehicle_count": result["active_count"],
            },
        }

    def freeze(self, frozen: bool = True):
        self._frozen = frozen
        freeze_widgets(frozen, self.add_btn)
        self.on_refresh()  # rebuild cards with updated button states

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self.on_refresh()
            self._loaded = True

    def _on_project_reloaded(self):
        self._loaded = False
        if self.isVisible():
            self.on_refresh()
            self._loaded = True



"""
sys_tracker_window.py — Floating resource monitor window.

Shows live RAM, CPU, open handles, and GC counts.
Opens from Dev > Sys Tracker > Open Monitor.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QGroupBox, QGridLayout,
)

from .sys_tracker import SysTracker
from .themes import get_token


class SysTrackerWindow(QWidget):
    _instance: "SysTrackerWindow | None" = None

    @classmethod
    def open(cls, parent=None):
        if cls._instance is None or not cls._instance.isVisible():
            cls._instance = cls(parent)
        cls._instance.show()
        cls._instance.raise_()
        cls._instance.activateWindow()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.Window | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Resource Monitor")
        self.setMinimumWidth(420)
        self.setMinimumHeight(480)
        self.setStyleSheet(
            f"background-color: {get_token('base')}; color: {get_token('text')};"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # ── Live stats grid ───────────────────────────────────────────────
        group = QGroupBox("Live Stats")
        group.setStyleSheet(f"QGroupBox {{ color: {get_token('text')}; }}")
        grid = QGridLayout(group)
        grid.setSpacing(6)

        def _stat_label(text="—"):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lbl.setFont(QFont("monospace", 10))
            lbl.setStyleSheet(f"color: {get_token('text')};")
            return lbl

        def _key_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color: {get_token('text_secondary')};")
            return lbl

        self._lbl_ram      = _stat_label()
        self._lbl_delta    = _stat_label()
        self._lbl_peak     = _stat_label()
        self._lbl_cpu      = _stat_label()
        self._lbl_handles  = _stat_label()
        self._lbl_gc       = _stat_label()

        for row, (key, val_lbl) in enumerate([
            ("RAM (current)",   self._lbl_ram),
            ("RAM (Δ baseline)", self._lbl_delta),
            ("RAM (peak)",      self._lbl_peak),
            ("CPU %",           self._lbl_cpu),
            ("Open handles",    self._lbl_handles),
            ("GC counts",       self._lbl_gc),
        ]):
            grid.addWidget(_key_label(key), row, 0)
            grid.addWidget(val_lbl, row, 1)

        layout.addWidget(group)

        # ── Buttons ───────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self._btn_snapshot = QPushButton("Snapshot")
        self._btn_snapshot.clicked.connect(self._do_snapshot)

        self._btn_toggle = QPushButton("Stop Auto")
        self._btn_toggle.clicked.connect(self._toggle_auto)

        self._btn_clear = QPushButton("Clear Log")
        self._btn_clear.clicked.connect(lambda: self._log.clear())

        for btn in (self._btn_snapshot, self._btn_toggle, self._btn_clear):
            btn.setMinimumHeight(30)
            btn_row.addWidget(btn)

        layout.addLayout(btn_row)

        # ── Log ───────────────────────────────────────────────────────────
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Consolas", 9))
        self._log.setStyleSheet(
            f"background-color: {get_token('surface')}; "
            f"color: {get_token('text')}; "
            "border-radius: 4px;"
        )
        layout.addWidget(self._log, stretch=1)

        # ── Wire tracker ──────────────────────────────────────────────────
        self._tracker = SysTracker.instance()
        self._tracker.updated.connect(self._on_update)

        # Refresh display every second (local QTimer — doesn't affect tracker interval)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(self._do_snapshot)
        self._refresh_timer.start()

        self._do_snapshot()

    # ── Slots ─────────────────────────────────────────────────────────────

    def _do_snapshot(self):
        self._tracker.snapshot("monitor")

    def _toggle_auto(self):
        if self._tracker._timer.isActive():
            self._tracker.stop()
            self._btn_toggle.setText("Start Auto")
        else:
            self._tracker.start()
            self._btn_toggle.setText("Stop Auto")

    def _on_update(self, stats: dict):
        ram   = stats["ram_mb"]
        delta = stats["ram_delta_mb"]
        peak  = stats["peak_ram_mb"]
        cpu   = stats["cpu_pct"]
        hdl   = stats["open_handles"]
        gc    = stats["gc"]

        sign = "+" if delta >= 0 else ""

        self._lbl_ram.setText(f"{ram:.1f} MB")
        self._lbl_delta.setText(f"{sign}{delta:.1f} MB")
        self._lbl_peak.setText(f"{peak:.1f} MB")
        self._lbl_cpu.setText(f"{cpu:.1f} %")
        self._lbl_handles.setText(str(hdl) if hdl >= 0 else "n/a")
        self._lbl_gc.setText(gc)

        # Colour RAM delta
        if delta > 50:
            color = get_token("danger")
        elif delta > 20:
            color = get_token("warning")
        else:
            color = get_token("success", "default") if hasattr(get_token, "__call__") else get_token("text")
        self._lbl_delta.setStyleSheet(f"color: {color};")

        label = stats.get("label", "")
        if label != "monitor":
            self._log.append(
                f"<span style='color:{get_token('text_secondary')};font-size:9px;'>"
                f"[{label}]</span> "
                f"RAM={ram:.1f} MB ({sign}{delta:.1f})  "
                f"CPU={cpu:.1f}%  hdl={hdl}  {gc}"
            )
            # Keep log from growing too large
            doc = self._log.document()
            while doc.blockCount() > 200:
                cursor = self._log.textCursor()
                cursor.movePosition(cursor.Start)
                cursor.select(cursor.LineUnderCursor)
                cursor.removeSelectedText()
                cursor.deleteChar()

    def closeEvent(self, event):
        self._refresh_timer.stop()
        self._tracker.updated.disconnect(self._on_update)
        super().closeEvent(event)

"""
sys_tracker.py — System resource monitor for 3psLCCA.

Tracks RAM, CPU, open file handles, and Qt object counts consumed by
this process. Logs periodically and on-demand snapshots.

Usage:
    from .sys_tracker import SysTracker

    # Start once at app launch (main.py):
    SysTracker.instance().start()

    # On-demand snapshot anywhere:
    SysTracker.instance().snapshot("after project load")

    # Stop (optional, e.g. on app exit):
    SysTracker.instance().stop()
"""

from __future__ import annotations

import gc
import logging
import os

from PySide6.QtCore import QObject, QTimer, Signal

log = logging.getLogger("sys_tracker")

try:
    import psutil
    _proc = psutil.Process(os.getpid())
    _PSUTIL = True
except ImportError:
    _proc = None
    _PSUTIL = False
    log.warning("[SysTracker] psutil not installed — resource tracking limited")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ram_mb() -> float:
    if not _PSUTIL:
        return 0.0
    try:
        return _proc.memory_info().rss / 1_048_576
    except Exception:
        return 0.0


def _cpu_percent() -> float:
    if not _PSUTIL:
        return 0.0
    try:
        return _proc.cpu_percent(interval=None)
    except Exception:
        return 0.0


def _open_handles() -> int:
    if not _PSUTIL:
        return -1
    try:
        return _proc.num_handles() if hasattr(_proc, "num_handles") else _proc.num_fds()
    except Exception:
        return -1


def _qt_object_count() -> int:
    try:
        from PySide6.QtCore import QObject as _QO
        return len(gc.get_referrers(_QO))
    except Exception:
        return -1


def _gc_counts() -> str:
    g = gc.get_count()
    return f"gen0={g[0]} gen1={g[1]} gen2={g[2]}"


# ── Tracker ───────────────────────────────────────────────────────────────────

class SysTracker(QObject):
    """
    Singleton resource monitor.

    Signals:
        updated(dict)  — emitted on every tick/snapshot with latest stats
    """

    updated = Signal(dict)

    _inst: "SysTracker | None" = None

    def __init__(self, interval_ms: int = 10_000):
        super().__init__()
        self._interval_ms = interval_ms
        self._baseline_ram: float = _ram_mb()
        self._peak_ram: float = self._baseline_ram
        self._tick_count: int = 0

        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._on_tick)

        # Prime CPU percent (first call always returns 0.0)
        _cpu_percent()

    @classmethod
    def instance(cls, interval_ms: int = 10_000) -> "SysTracker":
        if cls._inst is None:
            cls._inst = cls(interval_ms)
        return cls._inst

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self):
        self._baseline_ram = _ram_mb()
        self._peak_ram     = self._baseline_ram
        log.info(
            "[SysTracker] started  |  baseline RAM=%.1f MB  |  interval=%ds",
            self._baseline_ram, self._interval_ms // 1000,
        )
        self._timer.start()

    def stop(self):
        self._timer.stop()
        log.info("[SysTracker] stopped  |  peak RAM=%.1f MB", self._peak_ram)

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def snapshot(self, label: str = "") -> dict:
        ram    = _ram_mb()
        cpu    = _cpu_percent()
        handles= _open_handles()
        delta  = ram - self._baseline_ram
        sign   = "+" if delta >= 0 else ""

        if ram > self._peak_ram:
            self._peak_ram = ram

        stats = {
            "label":       label or "snapshot",
            "ram_mb":      ram,
            "ram_delta_mb": delta,
            "peak_ram_mb": self._peak_ram,
            "cpu_pct":     cpu,
            "open_handles": handles,
            "gc":          _gc_counts(),
        }

        log.info(
            "[SysTracker] %-35s  RAM=%6.1f MB (%s%.1f)  peak=%6.1f MB  "
            "CPU=%4.1f%%  handles=%d  gc=[%s]",
            stats["label"],
            ram, sign, abs(delta),
            self._peak_ram,
            cpu,
            handles,
            _gc_counts(),
        )

        self.updated.emit(stats)
        return stats

    # ── Internal ──────────────────────────────────────────────────────────────

    def _on_tick(self):
        self._tick_count += 1
        self.snapshot(f"tick #{self._tick_count}")

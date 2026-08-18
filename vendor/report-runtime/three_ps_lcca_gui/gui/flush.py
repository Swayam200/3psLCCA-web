"""
flush.py — Safe project window teardown.

Principles:
- Never force-delete anything Qt still owns
- Swallow all errors and warnings silently
- Run once per window (double-call safe)
- Log what it does, never crash the app
"""

from __future__ import annotations

import gc
import logging
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .project_window import ProjectWindow

log = logging.getLogger("flush")


def _try(fn, label=""):
    """Call fn(), silently swallow any exception or RuntimeWarning."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        try:
            fn()
        except Exception as e:
            log.debug("[flush] %s: %s", label, e)


def _disconnect(sig, slot=None):
    """Disconnect a specific slot or all slots from a signal."""
    if slot is not None:
        _try(lambda: sig.disconnect(slot), f"disconnect slot from {sig!r}")
    else:
        _try(lambda: sig.disconnect(), f"disconnect all from {sig!r}")


def flush_project_window(window: "ProjectWindow"):
    """
    Gently release resources held by a ProjectWindow before it closes.
    Safe to call multiple times — only runs once per window.
    """
    if getattr(window, "_flushed", False):
        return
    window._flushed = True

    pid = getattr(window, "project_id", "?")
    log.info("[flush] start — project=%s", pid)

    ctrl = getattr(window, "controller", None)

    # 1. Disconnect controller → window signals (named slots)
    if ctrl is not None:
        _disconnect(ctrl.fault_occurred, getattr(window, "_on_fault", None))
        _disconnect(ctrl.project_loaded, getattr(window, "_on_project_loaded", None))
        # Lambda-connected — disconnect all
        _disconnect(ctrl.sync_completed)
        _disconnect(ctrl.dirty_changed)

    # 2. Disconnect SaveStatusBar → controller signals (all lambdas)
    ssb = getattr(window, "save_status_bar", None)
    if ssb is not None and ctrl is not None:
        _disconnect(ctrl.project_loaded)
        _disconnect(ctrl.sync_completed)
        _disconnect(ctrl.dirty_changed)
        _disconnect(ctrl.status_message)
        _disconnect(ctrl.fault_occurred)

    # 3. Disconnect outputs_page signals
    op = getattr(window, "outputs_page", None)
    if op is not None:
        for sig_name in ("navigate_requested", "calculation_completed",
                         "validate_requested", "compare_requested"):
            sig = getattr(op, sig_name, None)
            if sig is not None:
                _disconnect(sig)

        # Request calc thread stop — don't block or force
        thread = getattr(op, "_calc_thread", None)
        if thread is not None:
            try:
                if thread.isRunning():
                    log.info("[flush] requesting calc thread stop…")
                    _try(thread.quit, "calc_thread.quit")
            except RuntimeError:
                pass  # C++ object already gone

    # 4. Disconnect theme manager — only this window's slot
    try:
        from .themes import theme_manager
        tm = theme_manager()
        slot = getattr(window, "_refresh_theme", None)
        if slot is not None:
            _disconnect(tm.theme_changed, slot)
        else:
            # No specific slot known — skip to avoid disconnecting other windows
            pass
    except Exception:
        pass

    # 5. Null engine callbacks (breaks circular refs without forcing anything)
    if ctrl is not None:
        engine = getattr(ctrl, "engine", None)
        if engine is not None:
            for attr in ("on_sync", "on_status", "on_fault", "on_dirty"):
                _try(lambda e=engine, a=attr: setattr(e, a, None), f"null {attr}")

    # 6. Remove page widgets from content stack (let Qt manage lifetime)
    cs = getattr(window, "content_stack", None)
    wm = getattr(window, "widget_map", {})

    # Named pages not in widget_map
    for attr in ("outputs_page", "logs_page"):
        w = getattr(window, attr, None)
        if w is not None and cs is not None:
            _try(lambda ww=w: cs.removeWidget(ww), attr)

    # Lazily created pages in widget_map
    count = 0
    for name, widget in list(wm.items()):
        if cs is not None:
            _try(lambda w=widget: cs.removeWidget(w), f"removeWidget {name}")
        count += 1
    wm.clear()
    if count:
        log.info("[flush] removed %d widgets from widget_map", count)

    # 7. Close the engine cleanly
    if ctrl is not None and getattr(ctrl, "engine", None):
        _try(ctrl.close_project, "close_project")

    # 8. Nudge GC
    gc.collect()

    log.info("[flush] done — project=%s", pid)

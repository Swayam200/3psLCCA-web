"""Compatibility layer that lets the desktop app's report modules run
outside the desktop app — under Pyodide in a browser worker, or under plain
CPython in tests.

Proven by the R0 spike (docs/report-latex-web-plan.md): with this layer the
desktop builder produced a PDF with zero text differences and byte-identical
images vs the GUI, and the same .tex under Pyodide as under CPython.

Everything here replaces a *runtime environment* concern, never report
logic: Qt widget scaffolding, the storage engine, threads, matplotlib's GUI
backend. The report content itself comes 100% from the vendored desktop
modules.
"""
from __future__ import annotations

import sys
import types

_installed = False


class _AnyMeta(type):
    def __getattr__(cls, name):
        return _Any

    def __iter__(cls):
        return iter(())


class _Any(metaclass=_AnyMeta):
    """Permissive stand-in for Qt classes used only as scaffolding."""

    def __init__(self, *a, **k): pass
    def __call__(self, *a, **k): return self
    def __getattr__(self, name): return _Any()
    def __iter__(self): return iter(())
    def __bool__(self): return False
    def __len__(self): return 0


class QColor:
    """Functional QColor: theme code does real color math (hex → RGB,
    luminance) and plot colors depend on it, so this one is not a dummy."""

    def __init__(self, spec="", *a):
        s = str(spec).lstrip("#")
        if len(s) == 8:
            s = s[2:]  # AARRGGBB → RRGGBB
        try:
            self._r, self._g, self._b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
            self._valid = True
        except (ValueError, IndexError):
            self._r = self._g = self._b = 0
            self._valid = False

    def isValid(self): return self._valid
    def red(self): return self._r
    def green(self): return self._g
    def blue(self): return self._b
    def redF(self): return self._r / 255
    def greenF(self): return self._g / 255
    def blueF(self): return self._b / 255
    def name(self): return f"#{self._r:02x}{self._g:02x}{self._b:02x}"


class _SyncFuture:
    def __init__(self, fn, *a, **k):
        try:
            self._result, self._error = fn(*a, **k), None
        except Exception as exc:  # noqa: BLE001 — mirror Future semantics
            self._result, self._error = None, exc

    def result(self, timeout=None):
        if self._error:
            raise self._error
        return self._result

    def add_done_callback(self, cb): cb(self)
    def done(self): return True
    def cancel(self): return False


class _SyncExecutor:
    """WASM has no threads; plot export's ThreadPoolExecutor runs inline."""

    def __init__(self, *a, **k): pass
    def submit(self, fn, *a, **k): return _SyncFuture(fn, *a, **k)
    def map(self, fn, *iterables, **k): return list(map(fn, *iterables))
    def shutdown(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False


def _stub_module(name):
    mod = types.ModuleType(name)
    mod.__getattr__ = lambda attr: type(attr, (_Any,), {})
    sys.modules[name] = mod
    return mod


def install():
    """Install all environment stubs. Idempotent; call before any
    three_ps_lcca_gui import."""
    global _installed
    if _installed:
        return
    _installed = True

    qt = _stub_module("PySide6")
    for sub in ("QtWidgets", "QtCore", "QtGui", "QtSvg", "QtSvgWidgets",
                "QtPrintSupport", "QtCharts"):
        setattr(qt, sub, _stub_module(f"PySide6.{sub}"))
    sys.modules["PySide6.QtGui"].QColor = QColor

    # The desktop storage engine (and psutil) is replaced by ChunkController;
    # report modules import ProjectController only as scaffolding/typing.
    pc = _stub_module("three_ps_lcca_gui.gui.project_controller")
    pc.ProjectController = _Any

    import concurrent.futures
    concurrent.futures.ThreadPoolExecutor = _SyncExecutor
    concurrent.futures.ProcessPoolExecutor = _SyncExecutor

    import matplotlib
    matplotlib.use("Agg")
    # Plot helpers call matplotlib.use("QtAgg") and import the Qt canvas at
    # module scope (GUI display concerns) — pin Agg, satisfy the imports.
    matplotlib.use = lambda *a, **k: None
    _stub_module("matplotlib.backends.backend_qtagg")
    _stub_module("matplotlib.backends.backend_qt")


class ChunkController:
    """The entire 'engine': desktop report code reads project data through
    get_fresh_chunk/get_chunk (see common_requested_data), so a dict of
    desktop-shaped chunks is a complete controller."""

    def __init__(self, chunks):
        self._chunks = chunks or {}

    def get_fresh_chunk(self, name):
        return self._chunks.get(name, {})

    def get_chunk(self, name):
        return self._chunks.get(name, {})


def generate_report_tex(chunks, config=None, work_dir="/report_out"):
    """Desktop-identical report generation: returns the .tex text plus the
    plot/asset files it references, from desktop-shaped chunk dicts.

    Mirrors the pre-compile half of desktop's compile_lcca_report_pdf —
    compilation itself is the caller's job (TeX-WASM in the browser).
    """
    install()
    from pathlib import Path

    from three_ps_lcca_gui.gui.components.utils.common_requested_data import set_controller
    from three_ps_lcca_gui.code_to_latex.pdf_generation_v3.lcca_report_builder import (
        _chunk,
        _copy_static_assets,
        _valid_result_cache,
        build_structured_code_to_latex_report_document,
    )
    from three_ps_lcca_gui.report.plot_exporter import generate_plots
    import three_ps_lcca_gui

    controller = ChunkController(chunks)
    set_controller(controller)

    out = Path(work_dir)
    out.mkdir(parents=True, exist_ok=True)
    _copy_static_assets(out)

    plot_paths = {}
    plot_error = ""
    try:
        cache = _valid_result_cache(controller)
        if cache.get("results"):
            currency = (
                cache.get("currency")
                or _chunk(controller, "general_info").get("project_currency")
                or "INR"
            )
            plot_paths = generate_plots(cache["results"], str(out), str(currency)) or {}
    except Exception as exc:  # noqa: BLE001 — report still renders without plots
        plot_error = f"{type(exc).__name__}: {exc}"

    pkg_root = Path(three_ps_lcca_gui.__file__).resolve().parent
    logo_path = (pkg_root / "gui" / "assets" / "logo" / "3pslcca_header.png").as_posix()

    tex = build_structured_code_to_latex_report_document(
        controller,
        plot_paths,
        config=config,
        logo_path=logo_path,
    )

    # Everything the .tex references that the LaTeX compiler will need.
    files = {}
    for name in plot_paths.values():
        p = out / name if not str(name).startswith("/") else Path(name)
        if p.exists():
            files[p.name] = p.as_posix()
    for extra in [
        pkg_root / "gui" / "assets" / "logo" / "3pslcca_header.png",
        pkg_root / "code_to_latex" / "pdf_generation_v3" / "images" / "image_1.png",
    ]:
        if extra.exists():
            files[extra.name] = extra.as_posix()

    return {"tex": tex, "files": files, "plot_error": plot_error}

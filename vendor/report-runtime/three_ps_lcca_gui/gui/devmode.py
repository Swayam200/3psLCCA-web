import os
from PySide6.QtWidgets import QMenu, QMessageBox
from PySide6.QtGui import QAction
from three_ps_lcca_gui.gui._CONFIG import DEV_MODE

def setup_dev_menu(parent_window, menubar):
    """
    Sets up the 'Dev' menu in the provided menubar if DEV_MODE is active.
    
    Args:
        parent_window: The QMainWindow instance (usually ProjectWindow).
        menubar: The QMenuBar instance where the menu should be added.
    """
    if not DEV_MODE:
        return None

    dev_menu = QMenu("&Dev", menubar)
    
    # --- Pesticide Debugger Submenu ---
    pesticide_menu = QMenu("Pesticide Debugger", dev_menu)
    
    def set_pesticide(mode):
        try:
            from three_ps_lcca_gui.gui.themes.PESTICIDE import paraside
            paraside(mode)
        except ImportError:
            QMessageBox.warning(parent_window, "Pesticide", "Pesticide module not found.")

    action_p_rainbow = QAction("Mode: Rainbow", parent_window)
    action_p_rainbow.triggered.connect(lambda: set_pesticide("rainbow"))
    pesticide_menu.addAction(action_p_rainbow)

    action_p_beast = QAction("Mode: Beast", parent_window)
    action_p_beast.triggered.connect(lambda: set_pesticide("beast"))
    pesticide_menu.addAction(action_p_beast)

    pesticide_menu.addSeparator()

    action_p_off = QAction("Turn OFF", parent_window)
    action_p_off.triggered.connect(lambda: set_pesticide("off"))
    pesticide_menu.addAction(action_p_off)

    dev_menu.addMenu(pesticide_menu)
    
    # --- Live Inspector Toggle ---
    action_inspector = QAction("Toggle Inspector", parent_window)
    action_inspector.triggered.connect(lambda: set_pesticide("beast"))
    dev_menu.addAction(action_inspector)

    # --- Project Inspector ---
    dev_menu.addSeparator()

    def _open_project_inspector():
        try:
            import sys, importlib.util
            from pathlib import Path

            _devtools_dir = Path(__file__).resolve()
            for _p in _devtools_dir.parents:
                _candidate = _p / "devtools"
                if _candidate.is_dir():
                    _devtools_dir = _candidate
                    break

            if str(_devtools_dir) not in sys.path:
                sys.path.insert(0, str(_devtools_dir))

            _spec = importlib.util.spec_from_file_location(
                "devtools_window", _devtools_dir / "devtools_window.py"
            )
            _mod = importlib.util.module_from_spec(_spec)
            sys.modules.setdefault("devtools_window", _mod)
            _spec.loader.exec_module(_mod)
            DevToolsWindow = _mod.DevToolsWindow

            ctrl = parent_window.controller
            engine = getattr(ctrl, "engine", None)
            project_dir = (
                getattr(ctrl, "project_path", None)
                or getattr(engine, "project_path", None)
            )
            if not project_dir or not Path(project_dir).exists():
                QMessageBox.warning(parent_window, "Project Inspector",
                                    "Could not resolve current project folder.")
                return

            win = DevToolsWindow()
            win._load_from_dir(Path(project_dir), label=Path(project_dir).name)
            win.show()
            parent_window._devtools_win = win
        except Exception as exc:
            QMessageBox.critical(parent_window, "Project Inspector", str(exc))

    action_open_inspector = QAction("Open in Project Inspector", parent_window)
    action_open_inspector.triggered.connect(_open_project_inspector)
    dev_menu.addAction(action_open_inspector)

    dev_menu.addSeparator()

    # --- LaTeX Submenu ---
    # Each entry: (menu label, module path, function name, output filename)
    _LATEX_ENTRIES = [
        ("Bridge Data",    "three_ps_lcca_gui.code_to_latex.bridge_data_latex",    "bridge_data_to_latex",    "bridge_data.tex"),
        ("Financial Data",    "three_ps_lcca_gui.code_to_latex.financial_data_latex",    "financial_data_to_latex",    "financial_data.tex"),
        ("Maintenance Data", "three_ps_lcca_gui.code_to_latex.maintenance_data_latex", "maintenance_data_to_latex", "maintenance_data.tex"),
        ("Vehicle Traffic Data",  "three_ps_lcca_gui.code_to_latex.traffic_data_latex",                                "vehicle_traffic_data_to_latex",  "vehicle_traffic_data.tex"),
        ("Material Emissions",    "three_ps_lcca_gui.code_to_latex.material_emissions_latex",                          "material_emissions_to_latex",    "material_emissions.tex"),
        ("Transport Emissions",   "three_ps_lcca_gui.code_to_latex.transport_emissions_latex",                         "transport_emissions_to_latex",   "transport_emissions.tex"),
        ("Machinery Emissions",   "three_ps_lcca_gui.code_to_latex.machinery_emissions_latex",                         "machinery_emissions_to_latex",   "machinery_emissions.tex"),
        ("Social Cost Data",     "three_ps_lcca_gui.code_to_latex.social_cost_data_latex",                             "social_cost_data_to_latex",      "social_cost_data.tex"),
        ("Recycling",            "three_ps_lcca_gui.code_to_latex.recycling_latex",                                   "recycling_to_latex",             "recycling.tex"),
        ("Final Report",         "three_ps_lcca_gui.code_to_latex.final_report",                           "final_report_to_latex",          "final_report.tex"),
        ("LCCA Results",         "three_ps_lcca_gui.code_to_latex.results_latex",                          "results_to_latex",               "results.tex"),
        ("Structure Work Data",  "three_ps_lcca_gui.code_to_latex.structure_work_data_latex",              "structure_work_data_to_latex",   "structure_work_data.tex"),
        ("Traffic & Road Data",   "three_ps_lcca_gui.code_to_latex.traffic_and_road_data_latex.get_all_data", "traffic_and_road_data_to_latex", "traffic_and_road_data.tex"),
        ("Traffic Fields",        "three_ps_lcca_gui.code_to_latex.traffic_and_road_data_latex.get_all_data", "traffic_fields_to_latex",        "traffic_fields.tex"),
        ("Peak Hour Distribution","three_ps_lcca_gui.code_to_latex.traffic_and_road_data_latex.get_all_data", "peak_hour_distribution_to_latex","peak_hour_distribution.tex"),
        ("Diversion Emissions", "three_ps_lcca_gui.code_to_latex.traffic_and_road_data_latex.get_all_data", "diversion_emissions_to_latex", "diversion_emissions.tex"),
        ("Vehicle Data",         "three_ps_lcca_gui.code_to_latex.traffic_and_road_data_latex.get_all_data", "vehicle_data_to_latex",          "vehicle_data.tex"),
        ("WPI Combined",         "three_ps_lcca_gui.code_to_latex.traffic_and_road_data_latex.get_all_data", "wpi_tables_to_latex",            "wpi_tables.tex"),
        ("WPI Base Factors",     "three_ps_lcca_gui.code_to_latex.traffic_and_road_data_latex.get_all_data", "wpi_base_to_latex",              "wpi_base.tex"),
        ("WPI Selected Factors", "three_ps_lcca_gui.code_to_latex.traffic_and_road_data_latex.get_all_data", "wpi_selected_to_latex",          "wpi_selected.tex"),
        ("WPI Ratios",           "three_ps_lcca_gui.code_to_latex.traffic_and_road_data_latex.get_all_data", "wpi_ratio_to_latex",             "wpi_ratio.tex"),
        
    ]
    _PDF_ENTRIES = [
    (
        "LCCA PDF Report",
        "three_ps_lcca_gui.code_to_latex.pdf_generation_v3.lcca_report_builder",
        "compile_lcca_report_pdf",
        "structured_code_to_latex_report",
    ),
]

    def _make_save_latex(module_path, fn_name, filename):
        def _handler():
            try:
                from pathlib import Path
                import importlib
                import three_ps_lcca_gui.gui.components.utils.common_requested_data as crd
                # Force engine save + clear cache (the same way "Save All Chunks" does)
                crd.get_all_data()
                
                mod = importlib.import_module(module_path)
                fn = getattr(mod, fn_name)
                tests_dir = Path(__file__).parent.parent / "code_to_latex" / "tests"
                tests_dir.mkdir(exist_ok=True)
                out_path = tests_dir / filename
                from three_ps_lcca_gui.code_to_latex.final_report import build_document
                doc = build_document(fn(parent_window.controller))
                out_path.write_text(doc, encoding="utf-8")
                QMessageBox.information(parent_window, "LaTeX", f"Saved to:\n{out_path}")
            except Exception as exc:
                QMessageBox.critical(parent_window, "LaTeX Error", str(exc))
        return _handler

    def _make_compile_pdf(module_path, fn_name, filename):
        def _handler():
            try:
                from pathlib import Path
                import importlib
                import three_ps_lcca_gui.gui.components.utils.common_requested_data as crd

                crd.get_all_data()

                mod = importlib.import_module(module_path)
                fn = getattr(mod, fn_name)

                tests_dir = Path(__file__).parent.parent / "code_to_latex" / "tests"
                tex_path, pdf_path = fn(
                    parent_window.controller,
                    output_dir=tests_dir,
                    filename=filename,
                    keep_artifacts=True,
                )

                QMessageBox.information(
                    parent_window,
                    "PDF",
                    f"Saved to:\n{tex_path}\n{pdf_path}",
                )
            except Exception as exc:
                QMessageBox.critical(parent_window, "PDF Error", str(exc))
        return _handler

    latex_menu = QMenu("LaTeX", dev_menu)

    for label, module_path, fn_name, filename in _LATEX_ENTRIES:
        action = QAction(f"Save {label} (tests/)", parent_window)
        action.triggered.connect(_make_save_latex(module_path, fn_name, filename))
        latex_menu.addAction(action)

    for label, module_path, fn_name, filename in _PDF_ENTRIES:
        action = QAction(f"Generate {label} (tests/)", parent_window)
        action.triggered.connect(_make_compile_pdf(module_path, fn_name, filename))
        latex_menu.addAction(action)
    dev_menu.addMenu(latex_menu)

    # --- Save All Chunks ---
    def _save_all_chunks():
        try:
            import json
            from pathlib import Path
            import three_ps_lcca_gui.gui.components.utils.common_requested_data as crd

            raw = crd.get_all_data()

            helpers = {
                # general_info
                "get_general_info":                  crd.get_general_info(),
                "get_currency":                      crd.get_currency(),
                "get_project_country":               crd.get_project_country(),
                "get_project_name":                  crd.get_project_name(),
                # bridge_data
                "get_bridge_data":                   crd.get_bridge_data(),
                "get_design_life":                   crd.get_design_life(),
                "get_analysis_period":               crd.get_analysis_period(),
                "get_construction_duration_months":  crd.get_construction_duration_months(),
                # financial_data
                "get_financial_data":                crd.get_financial_data(),
                "get_discount_rate":                 crd.get_discount_rate(),
                # maintenance_data
                "get_maintenance_data":              crd.get_maintenance_data(),
                # demolition_data
                "get_demolition_data":               crd.get_demolition_data(),
                # traffic_and_road_data
                "get_traffic_and_road_data":         crd.get_traffic_and_road_data(),
                # str_foundation
                "get_str_foundation":                crd.get_str_foundation(),
                # str_sub_structure
                "get_str_sub_structure":             crd.get_str_sub_structure(),
                # str_super_structure
                "get_str_super_structure":           crd.get_str_super_structure(),
                # str_misc
                "get_str_misc":                      crd.get_str_misc(),
                # transport_data
                "get_transport_data":                crd.get_transport_data(),
                # machinery_emissions_data
                "get_machinery_emissions_data":      crd.get_machinery_emissions_data(),
                # social_cost_data
                "get_social_cost_data":              crd.get_social_cost_data(),
                "get_social_cost_mode":              crd.get_social_cost_mode(),
                "get_social_cost":                   crd.get_social_cost(),
                "get_social_cost_ricke":             crd.get_social_cost_ricke(),
                "get_social_cost_usd_to_local_rate": crd.get_social_cost_usd_to_local_rate(),
                "get_social_cost_cpi_ratio":         crd.get_social_cost_cpi_ratio(),
                "get_social_cost_custom_scc_value":  crd.get_social_cost_custom_scc_value(),
                # diversion_emissions
                "get_diversion_emissions_data":      crd.get_diversion_emissions_data(),
                "get_diversion_emissions_cost":      list(crd.get_diversion_emissions_cost()),
                # str_summary
                "get_str_summary":                   crd.get_str_summary(),
                "get_str_summary_grand_total":       crd.get_str_summary_grand_total(),
            }

            out = {"chunks": raw, "helpers": helpers}

            tests_dir = Path(__file__).parent.parent / "code_to_latex" / "tests" / "chunks"
            tests_dir.mkdir(parents=True, exist_ok=True)
            out_path = tests_dir / "chunk.json"
            out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
            print(f"[Dev] Chunks saved to: {out_path}")
            QMessageBox.information(parent_window, "Chunks", f"Saved to:\n{out_path}")
        except Exception as exc:
            QMessageBox.critical(parent_window, "Chunk Error", str(exc))

    action_chunks = QAction("Save All Chunks (tests/chunks/)", parent_window)
    action_chunks.triggered.connect(_save_all_chunks)
    dev_menu.addAction(action_chunks)

    # --- Sys Tracker ---
    dev_menu.addSeparator()

    action_tracker = QAction("Resource Monitor", parent_window)
    action_tracker.triggered.connect(
        lambda: __import__(
            "three_ps_lcca_gui.gui.sys_tracker_window",
            fromlist=["SysTrackerWindow"]
        ).SysTrackerWindow.open(parent_window)
    )
    dev_menu.addAction(action_tracker)

    # --- Add to Menubar ---
    menubar.addMenu(dev_menu)
    return dev_menu

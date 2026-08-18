import os
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from three_ps_lcca_gui.gui.project_window import ProjectWindow
from three_ps_lcca_gui.gui.project_controller import ProjectController
from three_ps_lcca_gui.gui.components.utils.common_requested_data import set_controller
from three_ps_lcca_gui.gui.components.new_project_dialog import NewProjectDialog
from three_ps_lcca_gui.gui.api import tokens

import three_ps_lcca_gui.core.start_manager as sm

# All chunk names used by page widgets and their sub-widgets.
# Reading them once populates the controller cache so every subsequent
# get_chunk() call during preloading (and after window opens) is instant.
_CHUNKS_TO_WARM = [
    "general_info",
    "bridge_data",
    "financial_data",
    "maintenance_data",
    "demolition_data",
    "traffic_and_road_data",
    "str_foundation",
    "str_sub_structure",
    "str_super_structure",
    "str_misc",
    "str_component_registry",
    "transport_data",
    "machinery_emissions_data",
    "social_cost_data",
    "diversion_emissions",
]


def _warm_cache(target):
    """Read all known chunks into the controller cache (disk I/O happens here,
    during the loading phase, before any widget is built)."""
    for chunk in _CHUNKS_TO_WARM:
        target.controller.get_chunk(chunk)


class ProjectManager:
    def __init__(self):
        self.windows = []

    # --------------------------------------------------------------------------
    # WINDOW HELPERS
    # --------------------------------------------------------------------------

    def _create_window(self):
        new_controller = ProjectController()
        set_controller(new_controller)
        win = ProjectWindow(manager=self, controller=new_controller)
        self.windows.append(win)
        return win

    def _find_empty_window(self):
        for win in self.windows:
            if not win.has_project_loaded():
                return win
        return None

    def _find_window_for_project(self, project_id: str):
        for win in self.windows:
            if win.project_id == project_id:
                return win
        return None

    # --------------------------------------------------------------------------
    # PUBLIC API
    # --------------------------------------------------------------------------

    def open_project(self, project_id=None, is_new=False):
        # No project specified - show home screen
        if not project_id and not is_new:
            target = self._find_empty_window() or self._create_window()
            target.show_home()
            target.show()
            target.activateWindow()
            return

        # Project already open - just focus it
        if project_id:
            existing = self._find_window_for_project(project_id)
            if existing:
                existing.show_project_view()
                existing.raise_()
                existing.activateWindow()
                return

        if is_new:
            dialog = NewProjectDialog()

            def _on_loading_started(display_name, country, currency, unit_system):
                target = self._find_empty_window() or self._create_window()
                if not target.isVisible():
                    target.show()

                def _do_init():
                    if self._init_new_project(
                        target, display_name, country, currency, unit_system
                    ):
                        def _on_complete():
                            dialog.finish_loading()
                            target.show_project_view()
                            target.show()
                            target.activateWindow()
                            QTimer.singleShot(0, self.refresh_all_home_screens)

                        target.preload_all(_on_complete)
                    else:
                        dialog.finish_loading()
                        target.show_home()
                        target.show()

                # Yield one tick so dialog paints its locked/cycling state first
                QTimer.singleShot(0, _do_init)

            dialog.loading_started.connect(_on_loading_started)
            dialog.exec()
            return

        # Existing project
        if project_id:
            target = self._find_empty_window() or self._create_window()
            if not target.isVisible():
                target.show()

            # Mark card as loading on all visible home screens
            for win in self.windows:
                win.home_widget.set_card_loading(project_id)

            def _do_open():
                success = target.controller.init_project(project_id, is_new=False)
                if success:
                    target.project_id = target.controller.active_project_id
                    sm.record_open(target.project_id)

                    # Pre-warm controller chunk cache before any widget is built
                    _warm_cache(target)

                    def _on_complete():
                        for win in self.windows:
                            win.home_widget.clear_card_loading()
                        target.show_project_view()
                        target.show()
                        target.activateWindow()
                        QTimer.singleShot(0, self.refresh_all_home_screens)

                    target.preload_all(_on_complete)
                else:
                    for win in self.windows:
                        win.home_widget.clear_card_loading()
                    target.show_home()
                    target.show()

            # Yield one tick so card loading state paints before heavy work
            QTimer.singleShot(0, _do_open)

    def _init_new_project(
        self, target, display_name: str, country: str, currency: str, unit_system: str
    ) -> str | None:
        """Shared core of new-project creation (dialog flow and local API):
        engine init, default chunks, token, cache warm-up. Returns the new
        project_id, or None if engine init failed. Caller drives preload/UI."""
        new_id = f"proj_{os.urandom(4).hex()}"
        if not target.controller.init_project(
            new_id, is_new=True, display_name=display_name
        ):
            return None

        import copy
        from three_ps_lcca_gui.gui.components.structure.widgets.defaults import STRUCTURE_DEFAULTS
        engine = target.controller.engine
        engine.stage_update(
            {
                "project_name": display_name,
                "project_country": country,
                "project_currency": currency,
                "unit_system": unit_system or "metric",
            },
            "general_info",
        )
        engine.stage_update({"project_country": country}, "bridge_data")
        engine.stage_update(copy.deepcopy(STRUCTURE_DEFAULTS), "str_component_registry")
        # Force flush so chunks exist before widgets load
        engine.force_sync()
        target.project_id = target.controller.active_project_id
        sm.record_open(target.project_id)
        tokens.ensure_token(target.project_id)

        # Pre-warm controller chunk cache so all widget refresh_from_engine
        # calls during preload are cache hits - no disk I/O after this point.
        _warm_cache(target)
        return target.project_id

    def create_project(
        self, display_name: str, country: str, currency: str, unit_system: str = "metric"
    ) -> str | None:
        """Programmatic project creation (local API) - same steps as the New
        Project dialog flow, without the dialog. Returns the new project_id,
        or None if creation failed. Must be called on the Qt main thread."""
        target = self._find_empty_window() or self._create_window()
        if not target.isVisible():
            target.show()

        project_id = self._init_new_project(
            target, display_name, country, currency, unit_system
        )
        if project_id is None:
            target.show_home()
            target.show()
            return None

        def _on_complete():
            target.show_project_view()
            target.show()
            target.activateWindow()
            QTimer.singleShot(0, self.refresh_all_home_screens)

        target.preload_all(_on_complete)
        return project_id

    def is_project_open(self, project_id: str) -> bool:
        return self._find_window_for_project(project_id) is not None

    def remove_window(self, win):
        if win in self.windows:
            self.windows.remove(win)
        if not self.windows:
            from three_ps_lcca_gui.gui.components.utils.doc_handler import close_glossary
            close_glossary()
            QApplication.quit()

    def refresh_all_home_screens(self):
        for win in self.windows:
            win.home_widget.refresh_project_list()



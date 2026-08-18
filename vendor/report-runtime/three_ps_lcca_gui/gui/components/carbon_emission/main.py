from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette
from three_ps_lcca_gui.gui.components.carbon_emission.widgets.material_emissions import MaterialEmissions
from three_ps_lcca_gui.gui.components.carbon_emission.widgets.transport_emissions import (
    TransportEmissions,
)
from three_ps_lcca_gui.gui.components.carbon_emission.widgets.machinery_emissions import (
    MachineryEmissions,
)
from three_ps_lcca_gui.gui.components.carbon_emission.widgets.traffic_emissions import TrafficEmissions
from three_ps_lcca_gui.gui.components.carbon_emission.widgets.scc_widget import SCCWidget


class CarbonEmissionTabView(QWidget):
    tab_changed = Signal(str)  # emits the tab name when user clicks a tab

    def __init__(self, controller=None):
        super().__init__()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.tab_view = QTabWidget()

        # QTabWidget's content pane paints using the Base palette role, which
        # differs from Window in dark mode (gray vs black).
        # Fix: copy the Window color into the Base role so both paint identically,
        # no QSS needed - this follows the active theme automatically.
        palette = self.tab_view.palette()
        palette.setColor(QPalette.Base, palette.color(QPalette.Window))
        self.tab_view.setPalette(palette)

        self.tab_view.addTab(SCCWidget(controller=controller), "Social Cost of Carbon")
        self.tab_view.addTab(
            MaterialEmissions(controller=controller), "Material Emissions"
        )
        self.tab_view.addTab(
            TransportEmissions(controller=controller), "Transportation Emissions"
        )
        self.tab_view.addTab(
            MachineryEmissions(controller=controller), "Machinery/Equipment Emissions"
        )
        self.tab_view.addTab(
            TrafficEmissions(controller=controller), "Traffic Rerouting Emissions"
        )

        main_layout.addWidget(self.tab_view)
        self.tab_view.currentChanged.connect(self._on_tab_changed)

    def freeze(self, frozen: bool = True):
        for i in range(self.tab_view.count()):
            tab = self.tab_view.widget(i)
            if hasattr(tab, "freeze"):
                tab.freeze(frozen)

    def validate(self) -> dict:
        all_errors = []
        all_warnings = []
        for i in range(self.tab_view.count()):
            tab = self.tab_view.widget(i)
            if not hasattr(tab, "validate"):
                continue
            result = tab.validate()
            name = self.tab_view.tabText(i)
            if isinstance(result, dict):
                all_errors.extend(f"{name}: {msg}" for msg in result.get("errors", []))
                all_warnings.extend(f"{name}: {msg}" for msg in result.get("warnings", []))
            else:
                from three_ps_lcca_gui.gui.components.utils.form_builder.form_definitions import ValidationStatus
                status, issues = result
                if status == ValidationStatus.ERROR:
                    all_errors.extend(f"{name}: {msg}" for msg in issues)
                elif status == ValidationStatus.WARNING:
                    all_warnings.extend(f"{name}: {msg}" for msg in issues)
        return {"errors": all_errors, "warnings": all_warnings}

    def get_data(self) -> dict:
        data = {}
        for i in range(self.tab_view.count()):
            tab = self.tab_view.widget(i)
            if hasattr(tab, "get_data"):
                result = tab.get_data()
                data[result["chunk"]] = result["data"]
        return {"chunk": "carbon_emission_data", "data": data}

    def _on_tab_changed(self, index: int):
        self.tab_changed.emit(self.tab_view.tabText(index))

    def select_tab(self, name):
        tabs = [
            "Social Cost of Carbon",
            "Material Emissions",
            "Transportation Emissions",
            "Machinery/Equipment Emissions",
            "Traffic Rerouting Emissions",
        ]
        if name in tabs:
            self.tab_view.setCurrentIndex(tabs.index(name))



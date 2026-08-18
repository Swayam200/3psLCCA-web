"""
gui/components/outputs/calc_logic.py
"""

import traceback

from PySide6.QtCore import QObject, Signal

from three_ps_lcca_core.core.main import run_full_lcc_analysis
from .data_preparer import DataPreparer


class _LCCAWorker(QObject):
    """Runs the full LCC analysis on a background thread."""

    finished = Signal(object, object, object)
    errored = Signal(object, str)

    def __init__(self, all_data: dict, analysis_period_years: int):
        super().__init__()
        self._all_data = all_data
        self._analysis_period_years = analysis_period_years
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            all_data = self._all_data
            if self._cancel:
                return
            is_global, data_object = DataPreparer.prepare_data_object(
                all_data, self._analysis_period_years
            )
            if self._cancel:
                return
            wpi_metadata = None
            if not is_global:
                wpi_metadata = DataPreparer.prepare_wpi_object(all_data)
            if self._cancel:
                return
            lcc_breakdown = DataPreparer.prepare_life_cycle_construction_cost(all_data)
            if self._cancel:
                return
            results = run_full_lcc_analysis(
                data_object, lcc_breakdown, wpi=wpi_metadata, debug=True
            )
            self.finished.emit(results, all_data, lcc_breakdown)
        except Exception as exc:
            self.errored.emit(exc, traceback.format_exc())

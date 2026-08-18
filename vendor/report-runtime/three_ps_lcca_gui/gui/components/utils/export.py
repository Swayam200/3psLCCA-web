"""
gui/components/utils/export.py
Serialisation logic for exporting project data to JSON (and later Excel).
"""
from __future__ import annotations

import json
import datetime as _dt
from pathlib import Path


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _serialise_default(obj):
    """json.dumps default handler for types the stdlib encoder cannot handle."""
    try:
        import numpy as np
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    return str(obj)


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def collect_inputs(widget_map: dict) -> dict:
    """
    Gather chunk data from every page widget that exposes get_data().
    Returns {chunk_key: data_dict}.  Silently skips pages that fail.
    """
    inputs: dict = {}
    for page in widget_map.values():
        if hasattr(page, "get_data"):
            try:
                res = page.get_data()
                inputs[res["chunk"]] = res["data"]
            except Exception:
                pass
    return inputs


# ---------------------------------------------------------------------------
# Public export functions
# ---------------------------------------------------------------------------

def export_inputs_json(
    widget_map: dict,
    path: str,
    project_name: str = "",
) -> int:
    """
    Write all input chunks from *widget_map* to *path* as JSON.
    Returns the number of chunks written.
    """
    inputs = collect_inputs(widget_map)
    payload = {
        "export_meta": {
            "type": "inputs",
            "project_name": project_name,
            "exported_at": _dt.date.today().isoformat(),
        },
        "inputs": inputs,
    }
    Path(path).write_text(
        json.dumps(payload, indent=2, default=_serialise_default),
        encoding="utf-8",
    )
    return len(inputs)


def export_results_json(
    export_data: dict,
    path: str,
    project_name: str = "",
) -> None:
    """
    Write lcc_breakdown + results to *path*.
    *export_data* must be the dict returned by OutputsPage.get_export_data().
    """
    payload = {
        "export_meta": {
            "type": "results",
            "project_name": project_name,
            "analysis_period": export_data.get("analysis_period"),
            "currency": export_data.get("currency"),
            "exported_at": _dt.date.today().isoformat(),
        },
        "lcc_breakdown": export_data.get("lcc_breakdown", {}),
        "results": export_data.get("results", {}),
    }
    Path(path).write_text(
        json.dumps(payload, indent=2, default=_serialise_default),
        encoding="utf-8",
    )


def export_all_data_json(
    export_data: dict,
    path: str,
    project_name: str = "",
) -> None:
    """
    Write the complete project dataset (inputs + lcc_breakdown + results) to *path*.
    *export_data* must be the dict returned by OutputsPage.get_export_data().
    """
    payload = {
        "export_meta": {
            "type": "all_data",
            "project_name": project_name,
            "analysis_period": export_data.get("analysis_period"),
            "currency": export_data.get("currency"),
            "exported_at": _dt.date.today().isoformat(),
        },
        "inputs": export_data.get("all_data", {}),
        "lcc_breakdown": export_data.get("lcc_breakdown", {}),
        "results": export_data.get("results", {}),
    }
    Path(path).write_text(
        json.dumps(payload, indent=2, default=_serialise_default),
        encoding="utf-8",
    )

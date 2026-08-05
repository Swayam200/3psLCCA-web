"""Browser-side bridge between JavaScript and the web->core adapter.

This module is executed inside the Pyodide runtime booted by the published
3psLCCA-core browser engine. It loads the *same* adapter source the FastAPI
backend uses (backend/app/adapters/web_to_core.py) so both paths produce
identical results, and exposes JSON-in/JSON-out functions to JavaScript that
mirror the backend's /api/lcca/{validate,calculate} responses.
"""

from __future__ import annotations

import json
import sys
import types


# The adapter derives a repository root from its own __file__. Give it a path
# with the same depth as the real checkout so that resolution stays sane; the
# paths never have to exist because the WPI database is injected directly.
_ADAPTER_VIRTUAL_PATH = "/home/pyodide/3psLCCA-web/backend/app/adapters/web_to_core.py"

_adapter = None


def initialize(adapter_source: str, wpi_database_json: str) -> str:
    """Install the adapter module and hand it the WPI database."""
    global _adapter

    module = types.ModuleType("lcca_web_adapter")
    module.__file__ = _ADAPTER_VIRTUAL_PATH
    sys.modules["lcca_web_adapter"] = module
    exec(compile(adapter_source, _ADAPTER_VIRTUAL_PATH, "exec"), module.__dict__)

    module.configure_wpi_database(json.loads(wpi_database_json))
    _adapter = module
    return json.dumps({"status": "ready"})


def _unpack(request_json: str):
    request = json.loads(request_json)
    project = request.get("project") or {}
    analysis_period_years = int(request.get("analysis_period_years") or 50)
    debug = bool(request.get("debug"))
    return project, analysis_period_years, debug


def _failure(errors, warnings=None) -> str:
    return json.dumps({
        "status": "error",
        "results": {},
        "computed": {},
        "validation": {"errors": list(errors), "warnings": list(warnings or [])},
    })


def validate(request_json: str) -> str:
    project, analysis_period_years, _ = _unpack(request_json)
    try:
        validation = _adapter.validate_project(project, analysis_period_years)
        return json.dumps({
            "status": "success" if not validation["errors"] else "error",
            "results": {},
            "computed": {},
            "validation": validation,
        }, allow_nan=False)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as an error
        return _failure([str(exc)])


def calculate(request_json: str) -> str:
    project, analysis_period_years, debug = _unpack(request_json)
    try:
        calculation = _adapter.calculate_project(project, analysis_period_years, debug=debug)
        return json.dumps({"status": "success", **calculation}, allow_nan=False)
    except _adapter.AdapterValidationError as exc:
        return _failure(exc.errors, exc.warnings)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user as an error
        return _failure([str(exc)])

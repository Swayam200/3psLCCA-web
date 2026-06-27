from __future__ import annotations

import json
import traceback
from typing import Any

from lcca_web_adapter import (
    AdapterValidationError,
    calculate_project,
    configure_wpi_database,
    validate_project,
)


def initialize(wpi_database_json: str) -> str:
    configure_wpi_database(json.loads(wpi_database_json))
    return json.dumps({"status": "ready"})


def validate(request_json: str) -> str:
    request = json.loads(request_json)
    validation = validate_project(
        request.get("project", {}),
        int(request.get("analysis_period_years", 50)),
    )
    return json.dumps(
        {
            "status": "success" if not validation["errors"] else "error",
            "results": {},
            "computed": {},
            "validation": validation,
        },
        allow_nan=False,
    )


def calculate(request_json: str) -> str:
    request: dict[str, Any] = json.loads(request_json)
    try:
        calculation = calculate_project(
            request.get("project", {}),
            int(request.get("analysis_period_years", 50)),
            debug=False,
        )
        return json.dumps(
            {"status": "success", **calculation},
            allow_nan=False,
        )
    except AdapterValidationError as exc:
        return json.dumps(
            {
                "status": "error",
                "results": {},
                "computed": {},
                "validation": {
                    "errors": exc.errors,
                    "warnings": exc.warnings,
                },
            },
            allow_nan=False,
        )
    except Exception as exc:
        return json.dumps(
            {
                "status": "error",
                "results": {},
                "computed": {},
                "validation": {
                    "errors": [str(exc)],
                    "warnings": [],
                },
                "runtime_error": {
                    "type": type(exc).__name__,
                    "traceback": traceback.format_exc(),
                },
            },
            allow_nan=False,
        )

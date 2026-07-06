"""Compatibility wrapper for the removable FastAPI development backend."""

from __future__ import annotations

import sys
from pathlib import Path


WEB_SRC = Path(__file__).resolve().parents[3] / "src"
if str(WEB_SRC) not in sys.path:
    sys.path.insert(0, str(WEB_SRC))

from wasm.python.web_to_core import (  # noqa: E402,F401
    AdapterValidationError,
    PreparedCorePayload,
    calculate_project,
    configure_wpi_database,
    prepare_for_core,
    validate_project,
)

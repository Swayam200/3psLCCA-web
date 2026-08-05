"""The browser bridge must behave exactly like the HTTP API.

src/lib/lccaEngine/bridge.py runs inside Pyodide in the browser, loading the
same adapter this backend uses. These tests execute that bridge here, in plain
CPython, and assert its JSON responses match the backend's for the same input.
"""

from __future__ import annotations

import json
import sys
import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REPO_ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = REPO_ROOT / "src" / "lib" / "lccaEngine" / "bridge.py"
ADAPTER_PATH = REPO_ROOT / "backend" / "app" / "adapters" / "web_to_core.py"
WPI_DB_PATH = REPO_ROOT / "src" / "data" / "wpi_db.json"



@pytest.fixture(scope="module")
def bridge() -> types.ModuleType:
    module = types.ModuleType("lcca_web_bridge_under_test")
    module.__file__ = str(BRIDGE_PATH)
    exec(compile(BRIDGE_PATH.read_text(encoding="utf-8"), str(BRIDGE_PATH), "exec"), module.__dict__)
    module.initialize(
        ADAPTER_PATH.read_text(encoding="utf-8"),
        WPI_DB_PATH.read_text(encoding="utf-8"),
    )
    return module


def _request(project: dict, years: int = 50) -> str:
    return json.dumps({"project": project, "analysis_period_years": years, "debug": False})


def test_bridge_calculation_matches_the_api(bridge, global_project) -> None:
    from_bridge = json.loads(bridge.calculate(_request(global_project)))
    from_api = client.post(
        "/api/lcca/calculate",
        json={"project": global_project, "analysis_period_years": 50, "debug": False},
    ).json()

    assert from_bridge["status"] == "success"
    assert from_bridge == from_api


def test_bridge_validation_matches_the_api(bridge, global_project) -> None:
    from_bridge = json.loads(bridge.validate(_request(global_project)))
    from_api = client.post(
        "/api/lcca/validate",
        json={"project": global_project, "analysis_period_years": 50},
    ).json()

    assert from_bridge == from_api


def test_bridge_calculation_matches_the_api_in_india_mode(bridge, india_project) -> None:
    """India mode is the path that needs the WPI database."""
    from_bridge = json.loads(bridge.calculate(_request(india_project)))
    from_api = client.post(
        "/api/lcca/calculate",
        json={"project": india_project, "analysis_period_years": 50, "debug": False},
    ).json()

    assert from_bridge["status"] == "success"
    assert from_bridge["computed"]["wpi_required"] is True
    assert from_bridge == from_api


def test_bridge_reports_validation_errors_like_the_api(bridge) -> None:
    from_bridge = json.loads(bridge.calculate(_request({})))
    from_api = client.post(
        "/api/lcca/calculate",
        json={"project": {}, "analysis_period_years": 50, "debug": False},
    ).json()

    assert from_bridge["status"] == "error"
    assert from_bridge["validation"]["errors"]
    assert from_bridge == from_api


def test_bridge_uses_the_injected_wpi_database(bridge) -> None:
    """The browser has no filesystem: the WPI database must come from JS."""
    adapter = sys.modules["lcca_web_adapter"]
    base = adapter._load_base_wpi()

    expected = json.loads(WPI_DB_PATH.read_text(encoding="utf-8"))
    expected_2019 = next(
        entry["data"]
        for entry in expected["entries"]
        if entry["metadata"]["year"] == 2019
    )
    assert base == expected_2019


def test_bridge_never_raises_into_javascript(bridge) -> None:
    """Bad input must come back as a JSON error, not a Python exception."""
    for payload in ('{"project": null}', '{"project": {"bridge_data": 5}}'):
        response = json.loads(bridge.calculate(payload))
        assert response["status"] == "error"
        assert isinstance(response["validation"]["errors"], list)
        assert response["validation"]["errors"]

from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_validate_returns_structured_errors(global_project: dict) -> None:
    global_project["financial_data"] = {}

    response = client.post(
        "/api/lcca/validate",
        json={"project": global_project, "analysis_period_years": 50},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "error"
    assert payload["results"] == {}
    assert "financial_data.discount_rate is required." in payload["validation"]["errors"]


def test_calculate_returns_core_results(global_project: dict) -> None:
    response = client.post(
        "/api/lcca/calculate",
        json={"project": global_project, "analysis_period_years": 50},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["results"]
    assert payload["validation"]["errors"] == []


@pytest.mark.parametrize("endpoint", ["validate", "calculate"])
@pytest.mark.parametrize("invalid_project", [None, [], "invalid"])
def test_non_object_project_is_rejected(endpoint: str, invalid_project) -> None:
    response = client.post(f"/api/lcca/{endpoint}", json={"project": invalid_project})
    assert response.status_code == 422
    assert any(error["loc"] == ["body", "project"] for error in response.json()["detail"])


def test_calculation_validation_error_keeps_the_response_contract() -> None:
    response = client.post("/api/lcca/calculate", json={"project": {}})
    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "error"
    assert payload["results"] == {}
    assert payload["computed"] == {}
    assert payload["validation"]["errors"]


def test_unexpected_engine_error_is_returned_as_structured_validation(monkeypatch, global_project) -> None:
    def fail(*args, **kwargs):
        raise RuntimeError("Engine test failure")

    monkeypatch.setattr("app.main.calculate_project", fail)
    response = client.post("/api/lcca/calculate", json={"project": global_project})
    assert response.status_code == 200
    assert response.json() == {
        "status": "error",
        "results": {},
        "computed": {},
        "validation": {"errors": ["Engine test failure"], "warnings": []},
    }


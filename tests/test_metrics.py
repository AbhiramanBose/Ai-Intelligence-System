# PROMPT:
# Generate pytest tests for store metrics endpoint with valid events and zero-store edge case.
# CHANGES MADE:
# Added assertions for zero-visitor behavior and stable JSON contract.

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_metrics_returns_valid_json_for_empty_store():
    response = client.get("/stores/UNKNOWN_STORE/metrics")
    assert response.status_code == 200
    body = response.json()
    assert body["unique_visitors"] == 0
    assert body["conversion_rate"] == 0.0
    assert body["current_queue_depth"] == 0

# PROMPT:
# Generate pytest tests for health endpoint response contract.
# CHANGES MADE:
# Checked database status and warning list shape.

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_contract():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["database"] == "connected"
    assert isinstance(body["warnings"], list)

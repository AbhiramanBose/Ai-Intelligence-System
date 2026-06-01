# PROMPT:
# Generate pytest tests ensuring the funnel endpoint returns session-based stages.
# CHANGES MADE:
# Added required stage order from the challenge statement.

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_funnel_stage_order():
    response = client.get("/stores/ST1008/funnel")
    assert response.status_code == 200
    stages = [item["stage"] for item in response.json()["funnel"]]
    assert stages == ["ENTRY", "PRODUCT_ZONE_VISIT", "BILLING_QUEUE", "PURCHASE"]

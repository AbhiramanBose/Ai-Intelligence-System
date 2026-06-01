# PROMPT:
# Generate pytest tests for zero-traffic store behavior in a Store Intelligence API.
# The API should not crash or return null values when a store has no customer events.
#
# CHANGES MADE:
# Used a unique empty store ID and verified metrics, funnel, heatmap, anomalies, and conversion-debug responses.

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_empty_store_metrics_are_zero_safe():
    store_id = "EMPTY_STORE_EDGE_CASE"

    response = client.get(f"/stores/{store_id}/metrics")

    assert response.status_code == 200

    payload = response.json()

    assert payload["store_id"] == store_id
    assert payload["unique_visitors"] == 0
    assert payload["conversion_rate"] == 0.0
    assert payload["avg_dwell_per_zone"] == {}
    assert payload["current_queue_depth"] == 0
    assert payload["abandonment_rate"] == 0.0


def test_empty_store_funnel_is_zero_safe():
    store_id = "EMPTY_STORE_EDGE_CASE"

    response = client.get(f"/stores/{store_id}/funnel")

    assert response.status_code == 200

    payload = response.json()

    assert payload["store_id"] == store_id

    stages = {item["stage"]: item for item in payload["funnel"]}

    assert stages["ENTRY"]["count"] == 0
    assert stages["PRODUCT_ZONE_VISIT"]["count"] == 0
    assert stages["BILLING_QUEUE"]["count"] == 0
    assert stages["PURCHASE"]["count"] == 0


def test_empty_store_heatmap_is_empty_list():
    store_id = "EMPTY_STORE_EDGE_CASE"

    response = client.get(f"/stores/{store_id}/heatmap")

    assert response.status_code == 200

    payload = response.json()

    assert payload["store_id"] == store_id
    assert payload["zones"] == []


def test_empty_store_anomalies_are_safe():
    store_id = "EMPTY_STORE_EDGE_CASE"

    response = client.get(f"/stores/{store_id}/anomalies")

    assert response.status_code == 200

    payload = response.json()

    assert payload["store_id"] == store_id
    assert isinstance(payload["anomalies"], list)
    assert payload["anomalies"][0]["type"] == "NO_EVENTS"


def test_empty_store_conversion_debug_is_zero_safe():
    store_id = "EMPTY_STORE_EDGE_CASE"

    response = client.get(f"/stores/{store_id}/conversion-debug")

    assert response.status_code == 200

    payload = response.json()

    assert payload["store_id"] == store_id
    assert payload["entry_count"] == 0
    assert payload["product_count"] == 0
    assert payload["billing_count"] == 0
    assert payload["converted_count"] == 0
    assert payload["abandoned_count"] == 0
    assert payload["transaction_count"] == 0

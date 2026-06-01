# PROMPT:
# Generate pytest tests for staff exclusion in a Store Intelligence API.
# Staff movement should be stored but excluded from customer-facing metrics, funnel, heatmap, and conversion counts.
#
# CHANGES MADE:
# Created all-staff events through the ingestion API and verified they do not affect customer metrics.

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def make_event(store_id: str, event_type: str, zone_id: str | None = None) -> dict:
    return {
        "event_id": str(uuid4()),
        "store_id": store_id,
        "camera_id": "CAM_STAFF_TEST",
        "visitor_id": "STAFF_VISITOR_001",
        "event_type": event_type,
        "timestamp": "2026-04-10T14:00:00Z",
        "zone_id": zone_id,
        "dwell_ms": 30000 if event_type == "ZONE_DWELL" else 0,
        "is_staff": True,
        "confidence": 0.88,
        "metadata": {
            "track_id": 1,
            "session_seq": 1,
        },
    }


def test_all_staff_events_do_not_affect_customer_metrics():
    store_id = f"STAFF_ONLY_STORE_{uuid4()}"

    events = [
        make_event(store_id, "ENTRY", None),
        make_event(store_id, "ZONE_ENTER", "ZONE_FOH"),
        make_event(store_id, "ZONE_DWELL", "ZONE_FOH"),
        make_event(store_id, "BILLING_QUEUE_JOIN", "ZONE_BILLING_QUEUE"),
    ]

    ingest_response = client.post("/events/ingest", json={"events": events})

    assert ingest_response.status_code == 200
    assert ingest_response.json()["accepted_count"] == len(events)

    metrics_response = client.get(f"/stores/{store_id}/metrics")
    metrics = metrics_response.json()

    assert metrics_response.status_code == 200
    assert metrics["unique_visitors"] == 0
    assert metrics["conversion_rate"] == 0.0
    assert metrics["avg_dwell_per_zone"] == {}
    assert metrics["current_queue_depth"] == 0
    assert metrics["abandonment_rate"] == 0.0

    funnel_response = client.get(f"/stores/{store_id}/funnel")
    funnel = funnel_response.json()["funnel"]
    stages = {item["stage"]: item for item in funnel}

    assert stages["ENTRY"]["count"] == 0
    assert stages["PRODUCT_ZONE_VISIT"]["count"] == 0
    assert stages["BILLING_QUEUE"]["count"] == 0
    assert stages["PURCHASE"]["count"] == 0

    heatmap_response = client.get(f"/stores/{store_id}/heatmap")
    assert heatmap_response.status_code == 200
    assert heatmap_response.json()["zones"] == []

    debug_response = client.get(f"/stores/{store_id}/conversion-debug")
    debug = debug_response.json()

    assert debug["entry_count"] == 0
    assert debug["billing_count"] == 0
    assert debug["converted_count"] == 0

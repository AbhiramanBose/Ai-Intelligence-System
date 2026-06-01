# PROMPT:
# Generate pytest tests to verify that REENTRY events do not double-count a visitor in the funnel.
# The funnel should be session-aware and count the same visitor only once.
#
# CHANGES MADE:
# Used same visitor_id for ENTRY, EXIT, REENTRY, product visit, and billing events to validate deduplication.

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def make_event(
    store_id: str,
    visitor_id: str,
    event_type: str,
    timestamp: str,
    zone_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "event_id": str(uuid4()),
        "store_id": store_id,
        "camera_id": "CAM_REENTRY_TEST",
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "zone_id": zone_id,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.91,
        "metadata": metadata or {"session_seq": 1},
    }


def test_reentry_does_not_double_count_funnel_entry():
    store_id = f"REENTRY_STORE_{uuid4()}"
    visitor_id = "VIS_REENTRY_001"

    events = [
        make_event(store_id, visitor_id, "ENTRY", "2026-04-10T14:00:00Z"),
        make_event(store_id, visitor_id, "EXIT", "2026-04-10T14:02:00Z"),
        make_event(store_id, visitor_id, "REENTRY", "2026-04-10T14:05:00Z"),
        make_event(
            store_id,
            visitor_id,
            "ZONE_ENTER",
            "2026-04-10T14:06:00Z",
            "ZONE_CENTER_MAKEUP_UNIT",
        ),
        make_event(
            store_id,
            visitor_id,
            "BILLING_QUEUE_JOIN",
            "2026-04-10T14:08:00Z",
            "ZONE_BILLING_QUEUE",
            {"queue_depth": 1, "session_seq": 5},
        ),
    ]

    ingest_response = client.post("/events/ingest", json={"events": events})

    assert ingest_response.status_code == 200
    assert ingest_response.json()["accepted_count"] == len(events)

    response = client.get(f"/stores/{store_id}/funnel")

    assert response.status_code == 200

    payload = response.json()
    stages = {item["stage"]: item for item in payload["funnel"]}

    assert stages["ENTRY"]["count"] == 1
    assert stages["PRODUCT_ZONE_VISIT"]["count"] == 1
    assert stages["BILLING_QUEUE"]["count"] == 1
    assert stages["PURCHASE"]["count"] == 0

    debug_response = client.get(f"/stores/{store_id}/conversion-debug")
    debug = debug_response.json()

    assert debug["entry_count"] == 1
    assert debug["product_count"] == 1
    assert debug["billing_count"] == 1

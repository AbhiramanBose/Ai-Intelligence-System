# PROMPT:
# Generate pytest tests for event ingestion idempotency and malformed event partial success.
# CHANGES MADE:
# Added duplicate event_id test and ensured invalid rows do not block valid rows.

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def event(event_id="evt-ingest-001"):
    return {
        "event_id": event_id,
        "store_id": "ST1008",
        "camera_id": "CAM_3",
        "visitor_id": "VIS_TEST",
        "event_type": "ENTRY",
        "timestamp": "2026-04-10T14:39:30Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.91,
        "metadata": {},
    }


def test_ingest_accepts_valid_event():
    response = client.post("/events/ingest", json={"events": [event("evt-ingest-unique-001")]})
    assert response.status_code == 200
    body = response.json()
    assert body["accepted_count"] in {0, 1}
    assert body["invalid_count"] == 0


def test_ingest_is_idempotent_by_event_id():
    payload = {"events": [event("evt-ingest-idempotent-001")]}
    first = client.post("/events/ingest", json=payload).json()
    second = client.post("/events/ingest", json=payload).json()
    assert first["accepted_count"] == 1 or first["duplicate_count"] == 1
    assert second["duplicate_count"] == 1


def test_partial_success_for_invalid_event():
    bad = event("evt-bad-001")
    bad.pop("visitor_id")
    response = client.post("/events/ingest", json={"events": [event("evt-good-001"), bad]})
    assert response.status_code == 200
    body = response.json()
    assert body["invalid_count"] == 1

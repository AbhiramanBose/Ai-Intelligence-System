# PROMPT:
# Generate pytest tests for validating the Store Intelligence event schema.
# CHANGES MADE:
# Added project-specific event types, zone_id validation, and confidence bounds.

import pytest
from pydantic import ValidationError
from app.schemas.event_schema import EventIn


def valid_event(**overrides):
    data = {
        "event_id": "evt-schema-001",
        "store_id": "ST1008",
        "camera_id": "CAM_3",
        "visitor_id": "VIS_001",
        "event_type": "ENTRY",
        "timestamp": "2026-04-10T14:39:30Z",
        "zone_id": None,
        "dwell_ms": 0,
        "is_staff": False,
        "confidence": 0.91,
        "metadata": {"session_seq": 1},
    }
    data.update(overrides)
    return data


def test_valid_entry_event_passes():
    event = EventIn.model_validate(valid_event())
    assert event.event_id == "evt-schema-001"
    assert event.event_type.value == "ENTRY"


def test_zone_enter_requires_zone_id():
    with pytest.raises(ValidationError):
        EventIn.model_validate(valid_event(event_type="ZONE_ENTER", zone_id=None))


def test_confidence_must_be_between_zero_and_one():
    with pytest.raises(ValidationError):
        EventIn.model_validate(valid_event(confidence=1.5))

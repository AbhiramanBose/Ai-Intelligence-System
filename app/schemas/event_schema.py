from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, field_validator


class EventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    ZONE_DWELL = "ZONE_DWELL"
    BILLING_QUEUE_JOIN = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY = "REENTRY"


class EventIn(BaseModel):
    event_id: str = Field(..., min_length=8, max_length=128)
    store_id: str = Field(..., min_length=2, max_length=64)
    camera_id: str = Field(..., min_length=2, max_length=64)
    visitor_id: str = Field(..., min_length=2, max_length=128)
    event_type: EventType
    timestamp: datetime
    zone_id: str | None = None
    dwell_ms: int = Field(default=0, ge=0)
    is_staff: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("zone_id")
    @classmethod
    def zone_required_for_zone_events(cls, value: str | None, info):
        event_type = info.data.get("event_type")
        zone_required = {
            EventType.ZONE_ENTER,
            EventType.ZONE_EXIT,
            EventType.ZONE_DWELL,
            EventType.BILLING_QUEUE_JOIN,
            EventType.BILLING_QUEUE_ABANDON,
        }
        if event_type in zone_required and not value:
            raise ValueError("zone_id is required for zone and billing events")
        return value


class EventOut(EventIn):
    id: int

    class Config:
        from_attributes = True

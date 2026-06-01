from typing import Any
from pydantic import BaseModel, Field
from app.schemas.event_schema import EventIn


class IngestRequest(BaseModel):
    events: list[EventIn] = Field(..., min_length=1, max_length=500)


class InvalidEvent(BaseModel):
    index: int
    event_id: str | None = None
    error: str
    raw: dict[str, Any] | None = None


class IngestResponse(BaseModel):
    accepted_count: int
    duplicate_count: int
    invalid_count: int
    stored_event_ids: list[str]
    duplicate_event_ids: list[str]
    invalid_events: list[InvalidEvent]

from typing import Any
from fastapi import APIRouter, Depends
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.event_schema import EventIn
from app.schemas.ingest_schema import IngestResponse, InvalidEvent
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/ingest", response_model=IngestResponse)
def ingest_events(payload: dict[str, Any], db: Session = Depends(get_db)):
    raw_events = payload.get("events", [])
    valid_events: list[EventIn] = []
    invalid: list[InvalidEvent] = []

    if not isinstance(raw_events, list):
        return IngestResponse(
            accepted_count=0,
            duplicate_count=0,
            invalid_count=1,
            stored_event_ids=[],
            duplicate_event_ids=[],
            invalid_events=[InvalidEvent(index=-1, error="events must be a list", raw=payload)],
        )

    if len(raw_events) > 500:
        raw_events = raw_events[:500]
        invalid.append(InvalidEvent(index=500, error="batch truncated: max 500 events accepted"))

    for index, raw in enumerate(raw_events):
        try:
            valid_events.append(EventIn.model_validate(raw))
        except ValidationError as exc:
            invalid.append(
                InvalidEvent(
                    index=index,
                    event_id=raw.get("event_id") if isinstance(raw, dict) else None,
                    error=str(exc.errors()[0].get("msg", "invalid event")),
                    raw=raw if isinstance(raw, dict) else None,
                )
            )

    result = IngestionService(db).ingest(valid_events)
    result.invalid_count = len(invalid)
    result.invalid_events = invalid
    return result

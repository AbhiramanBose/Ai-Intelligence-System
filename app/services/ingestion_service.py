import json
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.event import Event
from app.schemas.event_schema import EventIn
from app.schemas.ingest_schema import IngestResponse


class IngestionService:
    def __init__(self, db: Session):
        self.db = db

    def ingest(self, events: list[EventIn]) -> IngestResponse:
        stored_ids: list[str] = []
        duplicate_ids: list[str] = []

        for event_in in events:
            exists = self.db.query(Event).filter(Event.event_id == event_in.event_id).first()
            if exists:
                duplicate_ids.append(event_in.event_id)
                continue

            row = Event(
                event_id=event_in.event_id,
                store_id=event_in.store_id,
                camera_id=event_in.camera_id,
                visitor_id=event_in.visitor_id,
                event_type=event_in.event_type.value,
                timestamp=event_in.timestamp,
                zone_id=event_in.zone_id,
                dwell_ms=event_in.dwell_ms,
                is_staff=event_in.is_staff,
                confidence=event_in.confidence,
                metadata_json=json.dumps(event_in.metadata),
            )
            self.db.add(row)
            try:
                self.db.commit()
                stored_ids.append(event_in.event_id)
            except IntegrityError:
                self.db.rollback()
                duplicate_ids.append(event_in.event_id)

        return IngestResponse(
            accepted_count=len(stored_ids),
            duplicate_count=len(duplicate_ids),
            invalid_count=0,
            stored_event_ids=stored_ids,
            duplicate_event_ids=duplicate_ids,
            invalid_events=[],
        )

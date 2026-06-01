from collections import defaultdict
import json

from sqlalchemy.orm import Session

from app.models.event import Event
from app.services.pos_correlation_service import PosCorrelationService


class MetricsService:
    def __init__(self, db: Session):
        self.db = db

    def get_metrics(self, store_id: str) -> dict:
        events = (
            self.db.query(Event)
            .filter(Event.store_id == store_id, Event.is_staff.is_(False))
            .order_by(Event.timestamp.asc())
            .all()
        )

        correlation = PosCorrelationService(self.db).get_summary(store_id)

        unique_visitors = correlation["entry_count"]
        converted_count = correlation["converted_count"]
        billing_count = correlation["billing_count"]
        abandoned_count = correlation.get("abandoned_count", 0)

        conversion_rate = (
            round(converted_count / unique_visitors, 4)
            if unique_visitors
            else 0.0
        )

        conversion_rate = min(conversion_rate, 1.0)

        dwell_by_zone: dict[str, list[int]] = defaultdict(list)

        for event in events:
            if event.event_type == "ZONE_DWELL" and event.zone_id:
                dwell_by_zone[event.zone_id].append(event.dwell_ms)

        avg_dwell = {
            zone: round(sum(values) / len(values), 2)
            for zone, values in dwell_by_zone.items()
            if values
        }

        queue_events = [
            event for event in events if event.event_type == "BILLING_QUEUE_JOIN"
        ]

        current_queue_depth = 0

        if queue_events:
            latest_queue_event = queue_events[-1]
            try:
                metadata = json.loads(latest_queue_event.metadata_json or "{}")
                current_queue_depth = int(metadata.get("queue_depth") or 0)
            except Exception:
                current_queue_depth = 0

        abandonment_rate = (
            round(abandoned_count / billing_count, 4)
            if billing_count
            else 0.0
        )

        return {
            "store_id": store_id,
            "unique_visitors": unique_visitors,
            "conversion_rate": conversion_rate,
            "avg_dwell_per_zone": avg_dwell,
            "current_queue_depth": current_queue_depth,
            "abandonment_rate": abandonment_rate,
        }

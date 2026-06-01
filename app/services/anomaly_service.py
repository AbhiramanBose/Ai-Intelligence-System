from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.event import Event
from app.services.pos_correlation_service import NON_PRODUCT_ZONES


QUEUE_SPIKE_THRESHOLD = 3
STALE_FEED_MINUTES = 10
DEAD_ZONE_MINUTES = 30


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


class AnomalyService:
    def __init__(self, db: Session):
        self.db = db

    def get_anomalies(self, store_id: str) -> dict:
        events = (
            self.db.query(Event)
            .filter(Event.store_id == store_id, Event.is_staff.is_(False))
            .order_by(Event.timestamp.asc())
            .all()
        )

        anomalies: list[dict] = []

        if not events:
            return {
                "store_id": store_id,
                "anomalies": [
                    {
                        "type": "NO_EVENTS",
                        "severity": "INFO",
                        "message": "No customer events are available for this store.",
                        "suggested_action": "Check whether the detection pipeline has produced events and replay them into the API.",
                    }
                ],
            }

        latest_event = events[-1]
        latest_event_time = as_utc(latest_event.timestamp)
        now = datetime.now(timezone.utc)

        if now - latest_event_time > timedelta(minutes=STALE_FEED_MINUTES):
            anomalies.append(
                {
                    "type": "STALE_FEED",
                    "severity": "WARN",
                    "message": "No event received in the last 10 minutes.",
                    "suggested_action": "Check camera feed, detection process, and event replay pipeline.",
                }
            )

        latest_queue_depth = self._latest_queue_depth(events)

        if latest_queue_depth >= QUEUE_SPIKE_THRESHOLD:
            anomalies.append(
                {
                    "type": "BILLING_QUEUE_SPIKE",
                    "severity": "WARN",
                    "message": f"Billing queue depth is {latest_queue_depth}.",
                    "suggested_action": "Assign one additional staff member to the billing counter.",
                }
            )

        anomalies.extend(self._dead_zone_anomalies(events, latest_event_time))

        anomalies.append(
            {
                "type": "CONVERSION_BASELINE_UNAVAILABLE",
                "severity": "INFO",
                "message": "Seven-day conversion baseline is unavailable for the single-day challenge dataset.",
                "suggested_action": "Load historical daily conversion aggregates to enable conversion-drop detection.",
            }
        )

        return {
            "store_id": store_id,
            "anomalies": anomalies,
        }

    def _latest_queue_depth(self, events: list[Event]) -> int:
        queue_depth = 0

        for event in events:
            if event.event_type != "BILLING_QUEUE_JOIN":
                continue

            try:
                metadata = json.loads(event.metadata_json or "{}")
                queue_depth = int(metadata.get("queue_depth") or 0)
            except Exception:
                queue_depth = 0

        return queue_depth

    def _dead_zone_anomalies(self, events: list[Event], reference_time: datetime) -> list[dict]:
        product_zone_last_visit: dict[str, datetime] = {}

        for event in events:
            if event.event_type not in {"ZONE_ENTER", "ZONE_DWELL"}:
                continue

            if event.zone_id in NON_PRODUCT_ZONES:
                continue

            if not event.zone_id:
                continue

            product_zone_last_visit[event.zone_id] = as_utc(event.timestamp)

        anomalies = []

        for zone_id, last_visit_time in sorted(product_zone_last_visit.items()):
            if reference_time - last_visit_time > timedelta(minutes=DEAD_ZONE_MINUTES):
                anomalies.append(
                    {
                        "type": "DEAD_ZONE",
                        "severity": "INFO",
                        "message": f"{zone_id} has had no customer visit in the last 30 minutes of observed footage.",
                        "suggested_action": "Review merchandising, staff assistance, or camera-zone calibration for this area.",
                    }
                )

        return anomalies
